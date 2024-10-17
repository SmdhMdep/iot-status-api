from logging import getLogger
import boto3

from streaming_status.repo import _maybe_canonicalize_group_name

from ..config import config
from ..utils import AppError, logger

sns_client = boto3.client("sns", region_name=config.schema_registry_table_region)
dynamodb = boto3.resource("dynamodb", region_name=config.schema_registry_table_region)
schema_notifications_subscription_table = dynamodb.Table(config.schema_notifications_table)

def get_subscription_status(email: str) -> str:
    record = _get_user_subscription_record_if_exists(email) or {}
    sub_arn = record.get("subscription_arn")
    subscription = _get_subscription_status(sub_arn) if sub_arn is not None else None

    if subscription is None:
        return "NOT_SUBSCRIBED"
    elif subscription["PendingConfirmation"] == "true":
        return "PENDING_CONFIRMATION"
    else:
        return "SUBSCRIBED"

def _get_user_subscription_record_if_exists(email: str):
    response = schema_notifications_subscription_table.get_item(Key={"user": email})
    return response.get("Item")

def _get_subscription_status(subscription_arn):
    try:
        response = sns_client.get_subscription_attributes(SubscriptionArn=subscription_arn)
        return response["Attributes"]
    except sns_client.exceptions.NotFoundException:
        return None

def subscribe_to_notifications(email, group_name) -> None:
    provider = _maybe_canonicalize_group_name(group_name)
    topic = _generate_topic_name(provider)
    topic_arn = _create_topic_if_not_exists(topic)
    subscription_arn = _subscribe_to_topic(topic_arn, email) 
    _put_subscription_record(subscription_arn, email, provider)
    logger.info(f"{email} from group {group_name} has subscribed to schema notifications.")

def _generate_topic_name(provider_name) -> str:
    topic_name = f"{config.schema_notifications_sns_prefix}_{provider_name}"
    return topic_name

def _create_topic_if_not_exists(topic_name):
    try:
        response = sns_client.create_topic(Name=topic_name)
    except sns_client.exceptions.InvalidParameterException:
        logger.exception("unable to create SNS topic with name %s", topic_name)
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

def unsubscribe_from_notifications(email, group):
    subscription_arn = _get_subscription_arn(email)
    _unsubscribe_to_topic(subscription_arn)
    _remove_subscription_record(email)
    # TODO: Replace with userid
    logger.info(f"{email} from {group} is unsubscribing from schema notifications")

def _get_subscription_arn(email):
    response = schema_notifications_subscription_table.get_item(
        Key={
        'user':email
        }
    )
    item = response.get('Item')
    return item.get('subscription_arn')

def _unsubscribe_to_topic(subscription_arn):
    try:
        sns_client.unsubscribe(SubscriptionArn=subscription_arn)
    except sns_client.exceptions.InvalidParameterException as e:
        raise AppError.invalid_argument("pending subscriptions cannot be cancelled")

def _remove_subscription_record(email):
    schema_notifications_subscription_table.delete_item(Key={'user':email})

def _put_subscription_record(subscription_arn, email, provider_name):
    schema_notifications_subscription_table.put_item(
        Item={
            "user": email,
            "subscribed_installer": provider_name,
            "subscription_arn": subscription_arn,
        }
    )
