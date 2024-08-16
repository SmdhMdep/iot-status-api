import base64
import json

import boto3

from ..errors import AppError
from ..config import config
from ..model import DeviceCustomLabel


dynamodb = boto3.resource("dynamodb", region_name=config.device_ledger_table_region)


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
    try:
        decoded_page = (
            json.loads(base64.decodebytes(page.encode()).decode())
            if page else None
        )
    except:
        raise AppError.invalid_argument("invalid page key")

    scan_params = _build_scan_params(
        provider,
        organization=organization,
        name_like=name_like,
        label=label,
        unprovisioned_only=unprovisioned_only,
    )
    next_page, items = _scan_table(scan_params, page=decoded_page, page_size=page_size)

    next_page_encoded = (
        base64.encodebytes(json.dumps(next_page).encode()).decode()
        if next_page else None
    )
    return next_page_encoded, items

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

def _scan_table(
    parameters: dict,
    *,
    page: dict | None,
    page_size: int | None,
):
    scan_page, items = page, []
    while True:
        if scan_page:
            parameters["ExclusiveStartKey"] = scan_page
        if page_size:
            parameters["Limit"] = page_size

        result = dynamodb.Table(config.device_ledger_table_name).scan(**parameters)
        items.extend(result["Items"])

        next_page = result.get("LastEvaluatedKey")
        if (page_size is None or len(items) < page_size) and next_page is not None:
            scan_page = next_page # type: ignore
        else:
            break

    return next_page, items


def find_device(provider: str | None, organization: str | None, device_name: str):
    key = {"serialNumber": device_name}
    device_info = dynamodb.Table(config.device_ledger_table_name).get_item(Key=key).get("Item", {})
    device_provider = device_info.get("jwtGroup") # type: ignore
    device_organization = device_info.get("org") # type: ignore

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
        **kwargs, # type: ignore
    )
