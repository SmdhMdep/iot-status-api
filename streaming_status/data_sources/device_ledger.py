import base64
import json

import boto3

from ..errors import AppError
from ..config import config


dynamodb = boto3.resource("dynamodb", region_name=config.device_ledger_table_region)


def list_unprovisioned_devices(
    provider: str | None,
    *,
    name_like: str | None = None,
    page: str | None = None,
    page_size: int,
) -> tuple[str | None, list[dict]]:
    scan_filter = {
        **(
            {"jwtGroup": {"ComparisonOperator": "EQ", "AttributeValueList": [provider]}}
            if provider is not None
            else {}
        ),
        "provStatus": {"ComparisonOperator": "NULL"}
    }

    if name_like:
        scan_filter["serialNumber"] = {
            "ComparisonOperator": "BEGINS_WITH",
            "AttributeValueList": [name_like]
        }

    pagination_kwargs = {}
    if page:
        try:
            page = json.loads(base64.decodebytes(page.encode()).decode())
        except:
            raise AppError.invalid_argument("invalid page key")
        pagination_kwargs['ExclusiveStartKey'] = page

    result = dynamodb.Table(config.device_ledger_table_name).scan(
        Limit=page_size,
        ScanFilter=scan_filter, # type: ignore
        **pagination_kwargs, # type: ignore
    )

    next_page = result.get('LastEvaluatedKey') if result["Count"] == page_size else None
    next_page_encoded = (
        base64.encodebytes(json.dumps(next_page).encode()).decode()
        if next_page else None
    )
    return next_page_encoded, result["Items"]

def find_device(provider: str | None, device_name: str):
    key = {"serialNumber": device_name}
    device_info = dynamodb.Table(config.device_ledger_table_name).get_item(Key=key).get('Item')
    device_provider = device_info.get('jwtGroup') # type: ignore

    return (
        device_info
        if not provider or not device_provider or device_provider == provider
        else None
    )
