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

    scan_params = _build_scan_params(provider, name_like=name_like, unprovisioned_only=unprovisioned_only)
    next_page, items = _scan_table(scan_params, page=decoded_page, page_size=page_size)

    next_page_encoded = (
        base64.encodebytes(json.dumps(next_page).encode()).decode()
        if next_page else None
    )
    return next_page_encoded, items

def _build_scan_params(
    provider: str | None,
    *,
    name_like: str | None,
    unprovisioned_only: bool,
) -> dict:
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

    return {"ScanFilter": scan_filter}

def _scan_table(
    parameters: dict,
    *,
    page: dict | None,
    page_size: int | None,
):
    scan_page, items = page, []
    while True:
        params = {
            **parameters,
            **({"ExclusiveStartKey": scan_page} if scan_page else {}),
            **({"Limit": page_size} if page_size else {}),
        }
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
