from io import BytesIO

import boto3
import requests

from ..config import config
from ..errors import AppError
from ..utils import logger


s3_client = boto3.client('s3', region_name=config.s3_bucket_region)


def get_stream_preview(topic: str) -> str | None:
    # topic name format: ($aws/?)rules/<rule_name>/<version>/<org>/<project>/<resource>
    _, _, org_name, project_name, resource_name = (
        topic.removeprefix('$aws/').removeprefix('rules/').split('/')
    )
    package_name = '--'.join((org_name, project_name))

    if not (package := _find_package(id=package_name)):
        return None

    if not (cloud_storage_path := _find_storage_path(package, resource_name)):
        return None

    with BytesIO() as memory_file:
        _download_into_file(cloud_storage_path, memory_file)
        try:
            return memory_file.readline().decode()
        except (ValueError, IOError) as e:
            logger.exception('unable to read file content for path: %s', cloud_storage_path)
            raise AppError(500, 'service not available')

def _find_storage_path(package: dict, name: str) -> str | None:
    for resource in package['resources']:
        if resource['name'] == name:
            return resource['cloud_storage_key'] if 'cloud_storage_key' in resource else None
    return None

def _find_package(id: str):
    response = requests.get(
        f'{config.mdep_url}/api/3/action/package_show',
        params={'id': id},
        headers={'Authorization': config.mdep_api_key}
    )
    if response.status_code == requests.codes['not_found']:
        return None
    response.raise_for_status()

    body = response.json()
    if not body['success']:
        logger.error("unable to fetch package %s from mdep api", id)
        raise AppError(500, 'service not available')

    return body['result']

def _download_into_file(key, file: BytesIO):
    s3_client.download_fileobj(
        Bucket=config.s3_bucket_name,
        Key=key,
        Fileobj=file,
    )
    file.seek(0)
