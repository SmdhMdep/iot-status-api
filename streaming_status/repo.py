import re
from datetime import datetime

import boto3

from .errors import AppError
from .config import config
from .utils import logger


device_name_regex = re.compile(r'[a-zA-Z0-9:_-]+')

# attribute names
REGISTRATION_WAY = 'RegistrationWay'
SENSOR_PROVIDER = 'SensorProvider'

iot_client = boto3.client("iot", region_name=config.iot_region_name)

def format_provider_name(provider: str) -> str:
    return '-'.join(provider.lower().split())

def list_devices(provider: str, name_like: str | None = None, page: str | None = None):
    provider = format_provider_name(provider)
    provider = provider.replace('"', '\"')
    query = f'attributes.{REGISTRATION_WAY}:* AND attributes.{SENSOR_PROVIDER}:"{provider}"'
    if name_like is not None:
        if not device_name_regex.fullmatch(name_like):
            raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")
        name_like = name_like.replace(":", "\:")
        query = f'{query} AND thingName:{name_like}*'

    request_params = {}
    if page is not None:
        request_params['nextToken'] = page
    # sample: samples/search_index_query_sample.json
    logger.info("search index query: %s", query)
    result = iot_client.search_index(maxResults=100, queryString=query, **request_params)

    return search_result_to_dto(result)

def get_device(provider, device_name):
    provider = format_provider_name(provider)
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")

    query = f'attributes.SensorProvider:"{provider}" AND thingName:"{device_name}"'
    result = iot_client.search_index(maxResults=1, queryString=query)
    if not result['things']:
        raise AppError.not_found(f'device with name {device_name} is not registered')

    key = {"serialNumber": device_name}
    dynamodb = boto3.resource("dynamodb", region_name=config.iot_region_name)
    device_info = dynamodb.Table("deviceInfo").get_item(Key=key).get('Item')

    thing = result['things'][0]
    if device_info is None:
        return thing_to_device_dto(thing)
    else:
        dto = thing_to_device_dto(thing)
        dto['deviceInfo'] = device_info_to_dto(device_info)
        return dto

def quote_iot_query(value):
    value = value.replace('"', '\\"')
    return f'"{value}"'

def search_result_to_dto(response):
    return {
        'nextPage': response.get('nextToken'),
        'devices': [thing_to_device_dto(device) for device in response['things']]
    }

def thing_to_device_dto(thing):
    thing_connectivity = thing.get('connectivity')
    dto = {
        'name': thing['thingName'],
        'attributes': thing['attributes'],
        'connectivity': {
            'connected': thing_connectivity['connected'],
            'timestamp': thing_connectivity['timestamp'] / 1000.0,
        }
    }

    disconnect_reason = thing_connectivity.get('disconnectReason')
    if disconnect_reason is not None:
        reason_description = DISCONNECT_REASONS[disconnect_reason]
        dto['connectivity']['disconnectReason'] = disconnect_reason
        dto['connectivity']['disconnectReasonDescription'] = reason_description

    return dto

def iso_to_timestamp(iso_formatted: str | None):
    if iso_formatted is None:
        return None

    if iso_formatted.endswith('Z'):
        iso_formatted = f"{iso_formatted[:-1]}+00:00"
    return datetime.fromisoformat(iso_formatted).timestamp()

def device_info_to_dto(device_info):
    return {
        "organization": device_info["org"],
        "project": device_info["proj"],
        "provisioningStatus": device_info.get("provStatus") or "UNKNOWN",
        "provisioningTimestamp": iso_to_timestamp(device_info.get("provTimestamp")),
        "registrationStatus": device_info.get("regStatus") or "UNKNOWN",
        "registrationTimestamp": iso_to_timestamp(device_info.get("regTimestamp")),
    }


DISCONNECT_REASONS = {
    'AUTH_ERROR': 'The client failed to authenticate or authorization failed.',
    'CLIENT_ERROR': 'The client did something wrong that causes it to disconnect. '
                    'For example, a client will be disconnected for sending more '
                    'than 1 MQTT CONNECT packet on the same connection or if the '
                    'client attempts to publish with a payload that exceeds the '
                    'payload limit.',
    'CLIENT_INITIATED_DISCONNECT': 'The client indicates that it will disconnect. '
                                    'The client can do this by sending either a '
                                    'MQTT DISCONNECT control packet or a Close '
                                    'frame if the client is using a WebSocket '
                                    'connection.',
    'CONNECTION_LOST': 'The client-server connection is cut off. This can happen '
                        'during a period of high network latency or when the '
                        'internet connection is lost.',
    'DUPLICATE_CLIENTID': 'The client is using a client ID that is already in '
                        'use. In this case, the client that is already '
                        'connected will be disconnected with this disconnect '
                        'reason.',
    'FORBIDDEN_ACCESS': 'The client is not allowed to be connected. For example, '
                        'a client with a denied IP address will fail to connect.',
    'MQTT_KEEP_ALIVE_TIMEOUT': 'If there is no client-server communication for '
                                "1.5x of the client's keep-alive time, the client "
                                'is disconnected.',
    'SERVER_ERROR': 'Disconnected due to unexpected server issues.',
    'SERVER_INITIATED_DISCONNECT': 'Server intentionally disconnects a client for '
                                    'operational reasons.',
    'THROTTLED': 'The client is disconnected for exceeding a throttling limit.',
    'WEBSOCKET_TTL_EXPIRATION': 'The client is disconnected because a WebSocket '
                                'has been connected longer than its time-to-live '
    'value.'
}
