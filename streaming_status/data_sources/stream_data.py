from datetime import datetime
from io import BytesIO

import boto3
import requests
from botocore.exceptions import ClientError

from ..config import config
from ..errors import AppError
from ..utils import logger


s3_client = boto3.client('s3', region_name=config.stream_data_bucket_region)

_PREVIEW_MAX_LINES = 5


def get_stream_preview(topic: str) -> tuple[str, datetime | None] | None:
    # topic name format: ($aws/?)rules/<rule_name>/<version>/<org>/<project>/<resource>
    _, _, org_name, project_name, resource_name = (
        topic.removeprefix('$aws/').removeprefix('rules/').split('/')
    )

    if not (package := _find_package(org_name, project_name)):
        return None

    if not (resource := _find_storage_path(package, resource_name)):
        return None

    cloud_storage_path, last_modified = resource
    with BytesIO() as memory_file:
        try:
            _download_into_file(cloud_storage_path, memory_file)
            return '\n'.join(
                line.decode() for _, line in zip(range(_PREVIEW_MAX_LINES), memory_file)
            ), last_modified
        except (ValueError, IOError, ClientError):
            logger.exception('unable to read file content for path: %s', cloud_storage_path)
            raise AppError.internal_error('service not available')


def _find_storage_path(package: dict, name: str) -> tuple[str, datetime | None] | None:
    for resource in package['resources']:
        if resource['name'] == name:
            try:
                last_modified = datetime.fromisoformat(resource['last_modified'])
            except ValueError:
                last_modified = None

            logger.info("last modified value: %s", last_modified)
            return (
                resource['cloud_storage_key'], last_modified
                if 'cloud_storage_key' in resource else None
            )
    return None


def _find_package(org_name: str, project_name: str):
    response = requests.get(
        f'{config.mdep_url}/api/3/action/cloudstorage_package_show',
        params={'org_name': org_name, 'name': project_name},
        headers={'Authorization': config.mdep_api_key}
    )
    if response.status_code == requests.codes['not_found']:
        return None
    if response.status_code == requests.codes['forbidden']:
        # FIXME: forbidden status code should be treated as an error but for some reason even though
        # the API token being used has admin privileges, the API refuses to allow access to some packages
        # probably error from CKAN. For now we're just logging and ignoring it.
        logger.error('got forbidden status code from MDEP API trying to request cloudstorage_package_show with name %s', project_name)
        return None
    response.raise_for_status()

    body = response.json()
    if not body['success']:
        logger.error("unable to fetch package %s from mdep api", id)
        raise AppError.internal_error('service not available')

    return body['result']

def _download_into_file(key, file: BytesIO):
    s3_client.download_fileobj(
        Bucket=config.stream_data_bucket_name,
        Key=key,
        Fileobj=file,
    )
    file.seek(0)
