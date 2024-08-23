import boto3

from ..config import config
from ..utils import AppError, logger

dynamodb = boto3.resource("dynamodb", region_name=config.device_alarms_table_region)
device_alarms_subscriptions_table = dynamodb.Table(config.device_alarms_table_name)
sns_client = boto3.client("sns", region_name=config.device_alarms_table_region)


def get_device_alarms_subscription(device_name: str, email: str):
    record = _get_subscription_record(device_name, email) or {}
    sub_arn = record.get("subscription_arn")
    subscription = _get_subscription_status(sub_arn) if sub_arn is not None else None

    if subscription is None:
        status = "disabled"
    elif subscription["PendingConfirmation"] == "true":
        status = "pending"
    else:
        status = "enabled"

    return {"subscriptionStatus": status}


def subscribe_to_device_alarms(device_name: str, email: str):
    # TODO topic name constraints
    topic_name = f"{config.device_alarms_dest_sns_topic_name_prefix}_{device_name}"
    topic_arn = _create_topic_if_not_exists(topic_name)
    subscription_arn = _subscribe_to_topic(topic_arn, email)
    _put_subscription_record(subscription_arn, device_name, email)


def unsubscribe_to_device_alarms(device_name: str, email: str):
    record = _get_subscription_record(device_name, email)
    if record is not None:
        _unsubscribe_to_topic(record["subscription_arn"])


def _create_topic_if_not_exists(name):
    try:
        response = sns_client.create_topic(Name=name)
    except sns_client.exceptions.InvalidParameterException:
        logger.exception("unable to create SNS topic with name %s", name)
        raise AppError.internal_error("parameter error")
    return response["TopicArn"]


def _subscribe_to_topic(topic_arn, email):
    response = sns_client.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=email,
        ReturnSubscriptionArn=True,
    )
    return response["SubscriptionArn"]


def _unsubscribe_to_topic(subscription_arn):
    try:
        sns_client.unsubscribe(SubscriptionArn=subscription_arn)
    except sns_client.exceptions.InvalidParameterException as e:
        raise AppError.invalid_argument("pending subscriptions cannot be cancelled")


def _get_subscription_status(subscription_arn):
    try:
        response = sns_client.get_subscription_attributes(SubscriptionArn=subscription_arn)
        return response["Attributes"]
    except sns_client.exceptions.NotFoundException:
        return None


def _put_subscription_record(subscription_arn, device_name, email):
    device_alarms_subscriptions_table.put_item(
        Item={
            "device_name": device_name,
            "subscription_endpoint": email,
            "subscription_arn": subscription_arn,
        }
    )


def _get_subscription_record(device_name, email):
    response = device_alarms_subscriptions_table.get_item(
        Key={
            "device_name": device_name,
            "subscription_endpoint": email,
        }
    )

    return response.get("Item")
