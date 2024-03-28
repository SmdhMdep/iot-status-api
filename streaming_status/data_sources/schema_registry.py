import base64
import json
from typing import Iterable

import boto3

from ..errors import AppError
from ..config import config
from ..utils import logger


dynamodb = boto3.resource("dynamodb", region_name=config.schema_registry_table_region)
schemas_table = dynamodb.Table(config.schema_registry_table_name)

def list_schemas(
    provider: str | None,
    page: str | None = None,
    page_size: int | None = None
) -> tuple[str | None, Iterable[dict]]:
    logger.info("page parameter: %s", page)
    try:
        decoded_page = (
            json.loads(base64.decodebytes(page.encode()).decode())
            if page else None
        )
    except:
        raise AppError.invalid_argument("invalid page key")

    params: dict = {}
    if decoded_page:
        params["ExclusiveStartKey"] = decoded_page
    if page_size:
        params["Limit"] = page_size
    if provider is not None:
        params['ScanFilter'] = {
            "jwtGroup": {
                "ComparisonOperator": "EQ",
                "AttributeValueList": [provider],
            },
        }

    result = schemas_table.scan(IndexName="jwtGroup-title-index", **params)
    next_page = result.get("LastEvaluatedKey")
    next_page_encoded = (
        base64.encodebytes(json.dumps(next_page).encode()).decode()
        if next_page else None
    )

    return next_page_encoded, sorted(
        result["Items"],
        key=lambda item: (item["title"], -item["version"])
    )


def get_schema(provider: str | None, id: str) -> dict | None:
    item = schemas_table.get_item(Key={"id": id}).get("Item")

    if item is not None:
        if provider is None or item.get("jwtGroup") == provider:
            return item
    return None
