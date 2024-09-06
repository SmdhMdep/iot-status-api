import re

import boto3

from ..config import config
from ..errors import AppError
from ..utils import logger
from .constants import ThingAttributeNames

device_name_regex = re.compile(r"[a-zA-Z0-9:_-]+")

iot_client = boto3.client("iot", region_name=config.fleet_index_iot_region_name)

DEACTIVATED_THINGS_GROUP_NAME = "deactivated"


def list_devices(
    provider: str | None,
    *,
    organization: str | None = None,
    name_like: str | None = None,
    page: str | None = None,
    page_size: int | None = None,
    active_only: bool = True,
) -> tuple[str | None, list[dict]]:
    query = f"attributes.{ThingAttributeNames.REGISTRATION_WAY}:*"

    provider_quoted = provider.replace('"', '\\"') if provider else None
    if provider_quoted is not None:
        query = f'{query} AND attributes.{ThingAttributeNames.SENSOR_PROVIDER}:"{provider_quoted}"'

    organization_quoted = organization.replace('"', '\\"') if organization else None
    if organization_quoted:
        query = f'{query} AND attributes.{ThingAttributeNames.SENSOR_ORGANIZATION}:"{organization_quoted}"'

    if name_like is not None:
        if not device_name_regex.fullmatch(name_like):
            raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")
        name_like_attr = name_like.replace(":", "\:")
        query = f"{query} AND thingName:{name_like_attr}*"

    if active_only:
        query = f"{query} AND NOT thingGroupNames:{DEACTIVATED_THINGS_GROUP_NAME}"

    request_params: dict = {}
    if page is not None:
        request_params["nextToken"] = page
    if page_size is not None:
        request_params["maxResults"] = page_size

    logger.debug("search index query: %s", query)
    fleet_result = iot_client.search_index(queryString=query, **request_params)

    things: list[dict] = fleet_result.get("things") # type: ignore
    return fleet_result.get("nextToken"), things or []


def find_device(provider: str | None, organization: str | None, device_name: str) -> dict | None:
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")
    if (provider is not None and '"' in provider) or (organization is not None and '"' in organization):
        raise AppError.invalid_argument("provider and organization must not contain double quotes")

    query = f'thingName:"{device_name}"'
    if provider is not None:
        query = f'{query} AND attributes.{ThingAttributeNames.SENSOR_PROVIDER}:"{provider}"'
    if organization is not None:
        query = f'{query} AND attributes.{ThingAttributeNames.SENSOR_ORGANIZATION}:"{organization}"'

    result = iot_client.search_index(maxResults=1, queryString=query)
    if not result["things"]:
        return None

    return result["things"][0] # type: ignore


def update_device_active_state(device_name: str, active: bool):
    if not active:
        iot_client.add_thing_to_thing_group(
            thingGroupName=DEACTIVATED_THINGS_GROUP_NAME,
            thingName=device_name,
        )
    else:
        iot_client.remove_thing_from_thing_group(
            thingGroupName=DEACTIVATED_THINGS_GROUP_NAME,
            thingName=device_name,
        )
