from io import BytesIO

import boto3
import requests

from ..config import config
from ..errors import AppError
from ..utils import logger


s3_client = boto3.client('s3', region_name=config.stream_data_bucket_region)

_PREVIEW_MAX_LINES = 5


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
            return '\n'.join(
                line.decode() for _, line in zip(range(_PREVIEW_MAX_LINES), memory_file)
            )
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
    if response.status_code == requests.codes['forbidden']:
        # FIXME: forbidden status code should be treated as an error but for some reason even though
        # the API token being used has admin privileges, the API refuses to allow access to some packages
        # probably error from CKAN. For now we're just logging and ignoring it.
        logger.error('got forbidden status code from MDEP API trying to request /api/3/action/package_show with id %s', id)
        return None
    response.raise_for_status()

    body = response.json()
    if not body['success']:
        logger.error("unable to fetch package %s from mdep api", id)
        raise AppError(500, 'service not available')

    return body['result']

def _download_into_file(key, file: BytesIO):
    s3_client.download_fileobj(
        Bucket=config.stream_data_bucket_name,
        Key=key,
        Fileobj=file,
    )
    file.seek(0)
