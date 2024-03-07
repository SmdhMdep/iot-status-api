import functools
import json

from aws_lambda_powertools.logging.correlation_paths import API_GATEWAY_HTTP
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.utilities.typing import LambdaContext

from . import repo
from .auth import Auth
from .config import config
from .errors import AppError
from .utils import logger, get_query_integer_value, parse_date_range_or_default


cors = CORSConfig(allow_origin=config.cors_allowed_origin, max_age=300, allow_credentials=True)
app = APIGatewayHttpResolver(strip_prefixes=['/api'], cors=cors, debug=config.is_offline)


@app.exception_handler(AppError)
def route_exception_handler(error: AppError):
    return Response(
        status_code=error.status_code,
        content_type=content_types.TEXT_PLAIN,
        body=json.dumps({'message': error.args[0]}),
    )


def cache_in_context(app: APIGatewayHttpResolver, key: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            value = app.context.get(key)
            if value is None:
                value = func(*args, **kwargs)
                app.context[key] = value
            return value

        return wrapper
    return decorator


@cache_in_context(app, 'auth')
def get_auth(app: APIGatewayHttpResolver) -> Auth:
    """Returns the `Auth` object for the current event context."""
    return Auth(app.current_event)


@cache_in_context(app, 'provider')
def get_request_provider(app: APIGatewayHttpResolver) -> str | None:
    """Returns the provider associated with the current user for the request."""
    auth = get_auth(app)
    requested_provider = app.current_event.get_query_string_value('provider')

    if auth.is_admin():
        provider = requested_provider
    else:
        groups = auth.group_memberships()
        if not groups:
            raise AppError.invalid_argument('missing groups')

        provider = requested_provider or groups[0]
        if provider not in groups:
            raise AppError.invalid_argument(f"provider not in groups: {provider}")

    return provider


def _offline_pass_provider(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        requested_provider = app.current_event.get_query_string_value('provider')
        is_admin = app.current_event.get_query_string_value('admin', 'false') == 'true'
        return route(*args, **kwargs, provider=requested_provider if not is_admin else None)

    return wrapper


def pass_provider(route):
    """Decorator for passing the selected provider to a route based on the current event.

    The decorated route must accept a keyword argument named `provider`.
    """
    if config.is_offline:
        return _offline_pass_provider(route)

    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        provider = get_request_provider(app)
        logger.info("request for provider %s", provider)
        logger.append_keys(provider=provider)
        return route(*args, **kwargs, provider=provider)

    return wrapper


@app.get('/devices')
@pass_provider
def list_devices(provider: str):
    query, organization, page = (
        app.current_event.get_query_string_value("query"),
        app.current_event.get_query_string_value("organization"),
        app.current_event.get_query_string_value("page"),
    )
    return repo.list_devices(provider=provider, organization=organization, name_like=query, page=page)


@app.get('/devices/export')
@pass_provider
def export_devices(provider: str):
    requested_format, compress = (
        app.current_event.get_query_string_value("format", "csv"),
        app.current_event.get_query_string_value("compress", "1") == "1",
    )

    if requested_format == "csv":
        from .csv_serializer import serialize_devices as serialize
    elif requested_format == "json":
        from json import dumps as serialize # type: ignore
    else:
        raise AppError.invalid_argument(f"expected format to be 'csv' or 'json' got '{requested_format}'")

    filename = f"devices_export.{requested_format}"
    body = serialize(repo.export_devices(provider=provider))

    return Response(
        status_code=200,
        content_type='text/csv' if requested_format == 'csv' else 'application/json',
        headers={'Content-Disposition': f'attachment;filename={filename}'},
        body=body,
        compress=compress,
    )


@app.get('/devices/<device_name>')
@pass_provider
def get_device(device_name: str, provider: str):
    return repo.get_device(provider=provider, device_name=device_name)


def check_device_access(func):
    """Check that the current user has access to the device"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        provider = get_request_provider(app)
        # make sure the provider has access to this device
        device_name = kwargs['device_name']
        _ = repo.get_device(provider, device_name, brief_repr=True)
        return func(*args, **kwargs)

    return wrapper


@app.get('/devices/<device_name>/monitoring/activity')
@check_device_access
def device_activity(device_name):
    from .data_sources import metrics

    range_query = app.current_event.get_query_string_value("range")
    date_range = parse_date_range_or_default(range_query)

    return metrics.get_activity_metric(device_name, date_range)


@app.get('/devices/<device_name>/monitoring/connectivity')
@check_device_access
def device_connectivity(device_name):
    from .data_sources import metrics

    range_query, page = (
        app.current_event.get_query_string_value("range"),
        app.current_event.get_query_string_value("page"),
    )
    date_range = parse_date_range_or_default(range_query)

    return metrics.get_connectivity_metric(device_name, date_range, page=page)


@app.get('/providers')
def list_providers():
    auth = get_auth(app)
    query, page = (
        app.current_event.get_query_string_value("query"),
        get_query_integer_value(app.current_event, "page"),
    )

    if not auth.is_admin():
        raise AppError.unauthorized("unauthorized")

    return repo.list_providers(name_like=query, page=page)


@app.get('/organizations')
def list_organizations():
    return repo.list_organizations(
        name_like=app.current_event.get_query_string_value("query"),
        page=get_query_integer_value(app.current_event, "page"),
    )


@logger.inject_lambda_context(correlation_id_path=API_GATEWAY_HTTP)
def handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
