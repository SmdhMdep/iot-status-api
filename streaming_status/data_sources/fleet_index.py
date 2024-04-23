import re

import boto3

from ..errors import AppError
from ..config import config
from ..utils import logger


device_name_regex = re.compile(r'[a-zA-Z0-9:_-]+')

# attribute names
REGISTRATION_WAY = 'RegistrationWay'
SENSOR_PROVIDER = 'SensorProvider'
SENSOR_ORGANIZATION = 'SensorOrganization'

iot_client = boto3.client("iot", region_name=config.fleet_index_iot_region_name)


def list_devices(
    provider: str | None,
    *,
    organization: str | None = None,
    name_like: str | None = None,
    page: str | None = None,
    page_size: int | None = None
):
    query = f'attributes.{REGISTRATION_WAY}:*'

    provider_quoted = provider.replace('"', '\\"') if provider else None
    if provider_quoted is not None:
        query = f'{query} AND attributes.{SENSOR_PROVIDER}:"{provider_quoted}"'

    organization_quoted = organization.replace('"', '\\"') if organization else None
    if organization_quoted:
        query = f'{query} AND attributes.{SENSOR_ORGANIZATION}:"{organization_quoted}"'

    if name_like is not None:
        if not device_name_regex.fullmatch(name_like):
            raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")
        name_like_attr = name_like.replace(":", "\:")
        query = f'{query} AND thingName:{name_like_attr}*'

    request_params: dict = {}
    if page is not None:
        request_params['nextToken'] = page
    if page_size is not None:
        request_params['maxResults'] = page_size

    logger.info("search index query: %s", query)
    fleet_result = iot_client.search_index(queryString=query, **request_params)

    return fleet_result.get('nextToken'), fleet_result.get("things") or []

def find_device(provider: str | None, organization: str | None, device_name: str):
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")
    if (provider is not None and '"' in provider) or (organization is not None and '"' in organization):
        raise AppError.invalid_argument("provider and organization must not contain double quotes")

    query = f'thingName:"{device_name}"'
    if provider is not None:
        query = f'{query} AND attributes.{SENSOR_PROVIDER}:"{provider}"'
    if organization is not None:
        query = f'{query} AND attributes.{SENSOR_ORGANIZATION}:"{organization}"'

    result = iot_client.search_index(maxResults=1, queryString=query)
    if not result['things']:
        return None

    return result['things'][0]


DISCONNECT_REASON_DESCRIPTIONS = {
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
