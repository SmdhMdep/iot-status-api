import json
import os
from datetime import datetime

import boto3
from aws_lambda_powertools.logging import Logger

from .event import DisconnectionNotification


logger = Logger()


SUBJECT_TEMPLATE = "ALARM: {device_name} Device Connectivity Alarm"
MESSAGE_TEMPLATE = """
You are receiving this email because the IoT device {device_name} has been {device_connectivity}.

Device name: {device_name}
Connectivity status: {device_connectivity}
Event date and time: {violation_datetime}
"""

DEVICE_ALARMS_DEST_SNS_TOPIC_ARN_PREFIX = os.environ["DEVICE_ALARMS_DEST_SNS_TOPIC_ARN_PREFIX"]

sns_client = boto3.client('sns')


@logger.inject_lambda_context
def route_alarm_notification(event: dict, _):
    # always a single record
    payload = event['Records'][0]["Sns"]["Message"]
    notification: DisconnectionNotification = json.loads(payload)

    device_name = notification["thingName"]
    device_connectivity = (
        "disconnected" if notification["violationEventType"] == "in-alarm"
        else "connected" if notification["violationEventType"] == "alarm-cleared"
        else "invalidated"
    )
    logger.append_keys(violation_event_details={
        'device_name': device_name,
        'event_type': notification["violationEventType"],
        'event_timestamp': notification["violationEventTime"] / 1000,
    })

    if device_connectivity == 'invalidated':
        logger.warning("skipping routing of invalidated alarm notification")
        return

    date = datetime.fromtimestamp(notification["violationEventTime"] / 1000)
    subject = SUBJECT_TEMPLATE.format(device_name=device_name)
    message = MESSAGE_TEMPLATE.format(
        device_name=device_name,
        device_connectivity=device_connectivity,
        # example Wed, 11 Jan 2024 at 13:42:21 PM
        violation_datetime=date.strftime('%a, %d %b %Y at %R'),
    )
    topic_arn = f"{DEVICE_ALARMS_DEST_SNS_TOPIC_ARN_PREFIX}_{device_name}"

    try:
        sns_client.publish(TopicArn=topic_arn, Subject=subject, Message=message)
        logger.info("routed alarm notification")
    except sns_client.exceptions.NotFoundException:
        logger.info("skipping routing of alarm notification")
