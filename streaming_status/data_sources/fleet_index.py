import re

import boto3

from ..errors import AppError
from ..config import config
from ..utils import logger


device_name_regex = re.compile(r'[a-zA-Z0-9:_-]+')

# attribute names
REGISTRATION_WAY = 'RegistrationWay'
SENSOR_PROVIDER = 'SensorProvider'

iot_client = boto3.client("iot", region_name=config.fleet_index_iot_region_name)


def list_devices(provider: str, *, name_like: str | None = None, page: str | None = None, page_size: int):
    provider_quoted = provider.replace('"', '\\"')
    query = f'attributes.{REGISTRATION_WAY}:* AND attributes.{SENSOR_PROVIDER}:"{provider_quoted}"'
    if name_like is not None:
        if not device_name_regex.fullmatch(name_like):
            raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")
        name_like_attr = name_like.replace(":", "\:")
        query = f'{query} AND thingName:{name_like_attr}*'

    request_params = {}
    if page is not None:
        request_params['nextToken'] = page
    # sample: samples/search_index_query_sample.json
    logger.info("search index query: %s", query)
    fleet_result = iot_client.search_index(maxResults=page_size, queryString=query, **request_params)

    return fleet_result.get('nextToken'), fleet_result.get("things") or []

def find_device(provider, device_name):
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")

    query = f'attributes.SensorProvider:"{provider}" AND thingName:"{device_name}"'
    result = iot_client.search_index(maxResults=1, queryString=query)
    if not result['things']:
        return None

    return result['things'][0]

def get_disconnect_description(reason: str) -> str:
    return _DISCONNECT_REASONS[reason]


_DISCONNECT_REASONS = {
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
