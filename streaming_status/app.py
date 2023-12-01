import functools
import json

from aws_lambda_powertools.logging.correlation_paths import API_GATEWAY_HTTP
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.utilities.typing import LambdaContext

from . import repo
from .auth import get_auth
from .config import config
from .errors import AppError
from .utils import logger


cors = CORSConfig(allow_origin=config.cors_allowed_origin, max_age=300, allow_credentials=True)
app = APIGatewayHttpResolver(strip_prefixes=['/api'], cors=cors, debug=config.is_offline)


@app.exception_handler(AppError)
def route_exception_handler(error: AppError):
    return Response(
        status_code=error.status_code,
        content_type=content_types.TEXT_PLAIN,
        body=json.dumps({'message': error.args[0]}),
    )

def pass_provider(route):
    @functools.wraps(route)
    def wrapper(*args, **kwargs):
        requested_provider = app.current_event.get_query_string_value('provider')
        if config.is_offline:
            is_admin = app.current_event.get_query_string_value('admin', 'false') == 'true'
            return route(*args, **kwargs, provider=requested_provider if not is_admin else None)

        is_admin = config.admin_role in get_auth(app).roles()
        if is_admin:
            return route(*args, **kwargs, provider=requested_provider)

        groups = get_auth(app).group_memberships()
        if not groups:
            raise AppError.invalid_argument('missing groups')

        provider = requested_provider or groups[0]
        if provider not in groups:
            raise AppError.invalid_argument('provider not in groups: %s', provider)

        logger.info("request for provider %s", provider)
        logger.append_keys(provider=provider)
        return route(*args, **kwargs, provider=provider)

    return wrapper

@app.get('/devices')
@pass_provider
def list_devices(provider: str):
    query, page = (
        app.current_event.get_query_string_value("query"),
        app.current_event.get_query_string_value("page"),
    )
    return repo.list_devices(provider=provider, name_like=query, page=page)

@app.get('/devices/<device_name>')
@pass_provider
def get_device(device_name: str, provider: str):
    return repo.get_device(provider=provider, device_name=device_name)

@logger.inject_lambda_context(correlation_id_path=API_GATEWAY_HTTP)
def handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
