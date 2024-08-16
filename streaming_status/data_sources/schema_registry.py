import base64
import json
from hashlib import md5
from typing import Iterable, Tuple

import boto3
import boto3.dynamodb.conditions as conditions

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

    result = schemas_table.scan(**params)
    next_page = result.get("LastEvaluatedKey")
    next_page_encoded = (
        base64.encodebytes(json.dumps(next_page).encode()).decode()
        if next_page else None
    )

    return next_page_encoded, sorted(
        result["Items"],
        key=lambda item: (item["jwtGroup"], item["title"], -item["version"])
    )


def get_schema(provider: str | None, id: str) -> dict | None:
    item = schemas_table.get_item(Key={"id": id}).get("Item")

    if item is not None:
        if provider is None or item.get("jwtGroup") == provider:
            return item
    return None


def get_schema_by_hash(provider: str, json_schema: str) -> dict | None:
    schema_hash = md5((json_schema + provider).encode()).hexdigest()
    items = schemas_table.query(
        IndexName='schemaHash-index',
        KeyConditionExpression=conditions.Key('schemaHash').eq(schema_hash)
    ).get('Items')
    item = items[0] if items else None

    if item and item.get('jwtGroup') == provider:
        title, version = item['title'], item['version']
        return {
            'id': item.get('id', None),
            'title': title,
            'version': version,
            'jwtGroup': item.get('jwtGroup'),
            'jsonSchema': json_schema,
        }

    return None
