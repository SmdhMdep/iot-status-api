import base64
import json

import boto3

from ..errors import AppError
from ..config import config


dynamodb = boto3.resource("dynamodb", region_name=config.device_ledger_table_region)


def list_devices(
    provider: str | None,
    *,
    name_like: str | None = None,
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

    next_page, items = _scan_table(
        provider=provider,
        name_like=name_like,
        page=decoded_page,
        page_size=page_size,
        unprovisioned_only=unprovisioned_only,
    )

    next_page_encoded = (
        base64.encodebytes(json.dumps(next_page).encode()).decode()
        if next_page else None
    )
    return next_page_encoded, items

def _build_scan_params(
    provider: str | None,
    *,
    name_like: str | None,
    page: dict | None,
    page_size: int | None,
    unprovisioned_only: bool,
):
    scan_filter: dict = {}
    if provider is not None:
        scan_filter["jwtGroup"] = {
            "ComparisonOperator": "EQ",
            "AttributeValueList": [provider],
        }
    if name_like:
        scan_filter["serialNumber"] = {
            "ComparisonOperator": "BEGINS_WITH",
            "AttributeValueList": [name_like]
        }
    if unprovisioned_only:
        scan_filter["provStatus"] = {"ComparisonOperator": "NULL"}

    params: dict = {
        "ScanFilter": scan_filter,
        **({"ExclusiveStartKey": page} if page else {}),
        **({"Limit": page_size} if page_size else {}),
    }
    return params

def _scan_table(
    provider: str | None,
    *,
    name_like: str | None,
    page: dict | None,
    page_size: int | None,
    unprovisioned_only: bool,
):
    scan_page, items = page, []
    while True:
        params = _build_scan_params(
            provider,
            name_like=name_like,
            page=scan_page,
            page_size=page_size,
            unprovisioned_only=unprovisioned_only,
        )
        result = dynamodb.Table(config.device_ledger_table_name).scan(**params)
        items.extend(result["Items"])

        next_page = result.get("LastEvaluatedKey")
        if (page_size is None or len(items) < page_size) and next_page is not None:
            scan_page = next_page # type: ignore
        else:
            break

    return next_page, items


def find_device(provider: str | None, device_name: str):
    key = {"serialNumber": device_name}
    device_info = dynamodb.Table(config.device_ledger_table_name).get_item(Key=key).get("Item")
    device_provider = device_info.get("jwtGroup") # type: ignore

    return (
        device_info
        if not provider or not device_provider or device_provider == provider
        else None
    )
