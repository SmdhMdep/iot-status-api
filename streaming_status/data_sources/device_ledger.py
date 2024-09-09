import base64
import json
from typing import Callable

import boto3
from boto3.dynamodb.conditions import Attr, ConditionBase, Key

from ..config import config
from ..errors import AppError
from ..model import DeviceCustomLabel
from ..utils import logger

dynamodb = boto3.resource("dynamodb", region_name=config.device_ledger_table_region)


def _decode_page(page: str | None) -> dict | None:
    try:
        return json.loads(base64.decodebytes(page.encode()).decode()) if page else None
    except:
        raise AppError.invalid_argument("invalid page key")


def _encode_page(page: dict | None) -> str | None:
    return base64.encodebytes(json.dumps(page).encode()).decode() if page else None


def list_devices(
    provider: str | None,
    *,
    organization: str | None = None,
    name_like: str | None = None,
    label: DeviceCustomLabel | None = None,
    page: str | None = None,
    page_size: int | None = None,
    unprovisioned_only: bool = False,
) -> tuple[str | None, list[dict]]:
    decoded_page = _decode_page(page)

    params = _build_scan_params(
        provider,
        organization=organization,
        name_like=name_like,
        label=label,
        unprovisioned_only=unprovisioned_only,
    )

    items = []

    def collect_items(result):
        items.extend(result.get("Items", []))
        return len(items)

    next_page = _scan_table(params, page=decoded_page, page_size=page_size, collector=collect_items)

    return _encode_page(next_page), items


def _build_scan_params(
    provider: str | None,
    *,
    organization: str | None,
    name_like: str | None,
    label: DeviceCustomLabel | None,
    unprovisioned_only: bool,
) -> dict:
    scan_filter: dict = {}
    if provider is not None:
        scan_filter["jwtGroup"] = {
            "ComparisonOperator": "EQ",
            "AttributeValueList": [provider],
        }
    if organization is not None:
        scan_filter["org"] = {
            "ComparisonOperator": "EQ",
            "AttributeValueList": [organization],
        }
    if name_like:
        scan_filter["serialNumber"] = {
            "ComparisonOperator": "BEGINS_WITH",
            "AttributeValueList": [name_like],
        }
    if label:
        scan_filter["customLabel"] = {
            "ComparisonOperator": "EQ",
            "AttributeValueList": [label.value],
        }
    if not label:
        scan_filter["customLabel"] = {
            "ComparisonOperator": "NE",
            "AttributeValueList": [DeviceCustomLabel.deactivated.value],
        }
    if unprovisioned_only:
        scan_filter["provStatus"] = {"ComparisonOperator": "NULL"}

    params: dict = {"ScanFilter": scan_filter}
    if config.device_ledger_index_name:
        params["IndexName"] = config.device_ledger_index_name

    return params


def find_device(provider: str | None, organization: str | None, device_name: str) -> dict | None:
    key = {"serialNumber": device_name}
    device_info = dynamodb.Table(config.device_ledger_table_name).get_item(Key=key).get("Item", {})
    device_provider: str = device_info.get("jwtGroup")  # type: ignore
    device_organization: str = device_info.get("org")  # type: ignore

    if device_info.get("jsonSchema") == "{}":
        device_info["jsonSchema"] = None

    return (
        device_info
        if (
            (not provider or not device_provider or device_provider == provider)
            and (not organization or not device_organization or device_organization == organization)
        )
        else None
    )


def update_device_label(
    provider: str | None = None,
    organization: str | None = None,
    *,
    device_name: str,
    expected_label: DeviceCustomLabel | None,
    label: DeviceCustomLabel | None,
):
    conditions: list[str] = []
    additional_attribute_values: dict = {}
    if provider is not None:
        conditions.append("jwtGroup=:provider")
        additional_attribute_values[":provider"] = provider
    if organization is not None:
        conditions.append("org=:organization")
        additional_attribute_values[":organization"] = organization
    if expected_label is not None:
        conditions.append("customLabel=:expectedCustomLabel")
        additional_attribute_values[":expectedCustomLabel"] = expected_label.value if expected_label else None

    if conditions:
        kwargs = {"ConditionExpression": " AND ".join(conditions)}
    else:
        kwargs = {}

    dynamodb.Table(config.device_ledger_table_name).update_item(
        Key={"serialNumber": device_name},
        UpdateExpression="SET customLabel=:customLabel",
        ExpressionAttributeValues={
            ":customLabel": label.value if label else None,
            **additional_attribute_values,
        },
        **kwargs,  # type: ignore
    )


def list_providers(
    organization: str | None,
    name_like: str | None,
    page: str | None = None,
    page_size: int | None = None,
) -> tuple[str | None, list[str]]:
    assert config.device_ledger_groups_index_name is not None

    condition: ConditionBase | None = None
    if organization:
        condition = _combine_condition(condition, Attr("org").eq(organization))
    if name_like:
        condition = _combine_condition(condition, Attr("jwtGroup").begins_with(name_like))

    params: dict = {"IndexName": config.device_ledger_groups_index_name}
    if condition:
        params["FilterExpression"] = condition
    if page:
        decoded_page = _decode_page(page)
        params["ExclusiveStartKey"] = decoded_page
    if page_size:
        params["Limit"] = page_size

    items: set[str] = set()

    def collect_items(result):
        items.update(item["jwtGroup"] for item in result.get("Items", []))
        return len(items)

    decoded_page = _decode_page(page)
    next_page = _scan_table(params, page=decoded_page, page_size=page_size, collector=collect_items)

    return _encode_page(next_page), list(items)


def _list_organizations_for_provider(
    provider: str,
    name_like: str | None,
    page: str | None = None,
    page_size: int | None = None,
) -> tuple[str | None, list[str]]:
    assert config.device_ledger_groups_index_name is not None

    condition: ConditionBase = Key("jwtGroup").eq(provider)
    if name_like:
        condition = _combine_condition(condition, Key("org").begins_with(name_like))

    params: dict = {}
    if page:
        decoded_page = _decode_page(page)
        params["ExclusiveStartKey"] = decoded_page
    if page_size:
        params["Limit"] = page_size

    result = dynamodb.Table(config.device_ledger_table_name).query(
        IndexName=config.device_ledger_groups_index_name,
        KeyConditionExpression=condition,
        **params,
    )

    return (
        _encode_page(result.get("LastEvaluatedKey")),
        list({item["org"] for item in result.get("Items", [])}),  # type: ignore
    )


def list_organizations(
    provider: str | None,
    name_like: str | None,
    page: str | None = None,
    page_size: int | None = None,
) -> tuple[str | None, list[str]]:
    assert config.device_ledger_groups_index_name is not None

    if provider is not None:
        return _list_organizations_for_provider(provider, name_like)

    condition = Attr("org").begins_with(name_like) if name_like else None

    params: dict = {"IndexName": config.device_ledger_groups_index_name}
    if condition:
        params["FilterExpression"] = condition
    if page_size:
        params["Limit"] = page_size

    items: set[str] = set()

    def collect_items(result):
        items.update(item["org"] for item in result.get("Items", []))
        return len(items)

    decoded_page = _decode_page(page)
    next_page = _scan_table(params, page=decoded_page, page_size=page_size, collector=collect_items)

    return _encode_page(next_page), list(items)


def list_projects(
    provider: str | None,
    organization: str | None,
    name_like: str | None,
    page: str | None = None,
    page_size: int | None = None,
):
    condition: ConditionBase | None = None
    if provider is not None:
        condition = _combine_condition(condition, Attr("jwtGroup").eq(provider))
    if organization is not None:
        condition = _combine_condition(condition, Attr("org").eq(organization))
    if name_like is not None:
        condition = _combine_condition(condition, Attr("proj").begins_with(name_like))

    params: dict = {"IndexName": config.device_ledger_org_proj_index_name}
    if condition:
        params["FilterExpression"] = condition
    if page_size:
        params["Limit"] = page_size

    items: list[dict] = list()
    seen_org_project = set()

    def collect_items(result):
        for item in result.get("Items", []):
            if (item["org"], item["proj"]) in seen_org_project:
                continue

            seen_org_project.add((item["org"], item["proj"]))
            items.append(
                {
                    "organization": item.get("org", "UNKNOWN"),
                    "project": item.get("proj", "-"),
                }
            )

        return len(items)

    decoded_page = _decode_page(page)
    next_page = _scan_table(params, page=decoded_page, page_size=page_size, collector=collect_items)

    return _encode_page(next_page), list(items)


def _scan_table(
    parameters: dict,
    *,
    page: dict | None,
    page_size: int | None,
    collector: Callable[[dict], int],
):
    scan_page, result_size = page, 0
    while True:
        if scan_page:
            parameters["ExclusiveStartKey"] = scan_page
        if page_size:
            parameters["Limit"] = page_size

        logger.debug("running scan on table %s with params %s", config.device_ledger_table_name, parameters)
        result = dynamodb.Table(config.device_ledger_table_name).scan(**parameters)
        result_size += collector(result)  # type: ignore

        next_page = result.get("LastEvaluatedKey")
        if (page_size is None or result_size < page_size) and next_page is not None:
            scan_page = next_page  # type: ignore
        else:
            break

    return next_page


def _combine_condition(condition: ConditionBase | None, predicate: ConditionBase):
    return condition & predicate if condition is not None else predicate
