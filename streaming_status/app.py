import functools
import json

from aws_lambda_powertools.logging.correlation_paths import API_GATEWAY_HTTP
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.utilities.typing import LambdaContext

from . import repo
from .auth import Auth, Permission
from .config import config
from .errors import AppError
from .utils import logger, get_query_integer_value, parse_date_range_or_default, parse_device_custom_label


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

    if auth.has_permission(Permission.providers_read):
        provider = requested_provider
    else:
        groups = auth.group_memberships()
        if not groups:
            raise AppError.invalid_argument('missing groups')

        provider = requested_provider or groups[0]
        if provider not in groups:
            raise AppError.invalid_argument(f"provider not in groups: {provider}")

    return provider


@cache_in_context(app, 'organization')
def get_request_organization(app: APIGatewayHttpResolver) -> str | None:
    """Returns the organization associated with the current user for the request."""
    auth = get_auth(app)
    requested_organization = app.current_event.get_query_string_value('organization')

    if auth.has_permission(Permission.organizations_read):
        organization = requested_organization
    else:
        groups = auth.group_memberships()
        if not groups:
            raise AppError.invalid_argument('missing groups')

        organization = requested_organization or groups[0]
        if organization not in groups:
            raise AppError.invalid_argument(f"organization not in groups: {organization}")

    return organization


def _offline_pass_provider(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        requested_provider = app.current_event.get_query_string_value('provider')
        return route(*args, **kwargs, provider=requested_provider)

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


def require_permission(permission: Permission):
    """Guard a route with a required permission.

    The current user must have the required `permission` to access the route.
    No-op in offline mode.
    """
    def decorator(func):
        if config.is_offline:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if get_auth(app).has_permission(permission):
                return func(*args, **kwargs)
            raise AppError.unauthorized()

        return wrapper
    return decorator


@app.get('/devices')
@pass_provider
def list_devices(provider: str | None):
    organization, raw_label, query, page = (
        get_request_organization(app),
        app.current_event.get_query_string_value("label"),
        app.current_event.get_query_string_value("query"),
        app.current_event.get_query_string_value("page"),
    )

    label = parse_device_custom_label(raw_label) if raw_label else None
    return repo.list_devices(provider=provider, organization=organization, name_like=query, label=label, page=page)


@app.get('/devices/export')
@pass_provider
def export_devices(provider: str | None):
    organization = get_request_organization(app)
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
    body = serialize(repo.export_devices(provider=provider, organization=organization))

    return Response(
        status_code=200,
        content_type='text/csv' if requested_format == 'csv' else 'application/json',
        headers={'Content-Disposition': f'attachment;filename={filename}'},
        body=body,
        compress=compress,
    )


@app.get('/devices/<device_name>')
@pass_provider
def get_device(device_name: str, provider: str | None):
    organization = get_request_organization(app)
    return repo.get_device(provider=provider, organization=organization, device_name=device_name)


def check_device_access(func):
    """Check that the current user has access to the device"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        provider = get_request_provider(app)
        organization = get_request_organization(app)
        device_name = kwargs['device_name']
        # make sure the provider/organization has access to this device
        _ = repo.get_device(provider, organization, device_name, brief_repr=True)
        return func(*args, **kwargs)

    return wrapper


@app.put('/devices/<device_name>')
@check_device_access
@require_permission(Permission.device_update)
def update_device(device_name: str):
    body = app.current_event.json_body
    if not isinstance(body, dict):
        raise AppError.invalid_argument('body must be a json object with a label property')

    raw_label = body.get('label')
    label = parse_device_custom_label(raw_label) if raw_label else None

    repo.update_device_label(device_name, label)

    return Response(status_code=204)


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


@app.get('/devices/<device_name>/monitoring/subscription')
@check_device_access
def get_device_alarms_subscription(device_name: str):
    from .data_sources import alarms

    return alarms.get_device_alarms_subscription(device_name, get_auth(app).email())


@app.post('/devices/<device_name>/monitoring/subscription/subscribe')
@check_device_access
def subscribe_device_alarms(device_name: str):
    from .data_sources import alarms

    alarms.subscribe_to_device_alarms(device_name, get_auth(app).email())
    return Response(status_code=204)


@app.post('/devices/<device_name>/monitoring/subscription/unsubscribe')
@check_device_access
def post_device_alarms_unsubscribe(device_name: str):
    from .data_sources import alarms

    alarms.unsubscribe_to_device_alarms(device_name, get_auth(app).email())
    return Response(status_code=204)


@app.get('/providers')
@require_permission(Permission.providers_read)
def list_providers():
    query, page = (
        app.current_event.get_query_string_value("query"),
        get_query_integer_value(app.current_event, "page"),
    )

    return repo.list_providers(name_like=query, page=page)


@app.get('/organizations')
@require_permission(Permission.organizations_read)
def list_organizations():
    return repo.list_organizations(
        name_like=app.current_event.get_query_string_value("query"),
        page=get_query_integer_value(app.current_event, "page"),
    )


@app.get('/me/permissions')
def me_permissions():
    auth = get_auth(app)
    return auth.get_permissions()


@logger.inject_lambda_context(correlation_id_path=API_GATEWAY_HTTP)
def handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
