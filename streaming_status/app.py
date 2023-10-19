import functools
import json

from aws_lambda_powertools.logging.correlation_paths import API_GATEWAY_HTTP
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.utilities.typing import LambdaContext

from .config import config
from .errors import AppError
from .utils import logger


cors = CORSConfig(allow_origin=config.cors_allowed_origin, max_age=300, allow_credentials=True)
app = APIGatewayHttpResolver(strip_prefixes=['/api'], cors=cors, debug=config.enable_debug)


@app.exception_handler(AppError)
def route_exception_handler(error: AppError):
    return Response(
        status_code=error.status_code,
        content_type=content_types.TEXT_PLAIN,
        body=json.dumps({'message': error.args[0]}),
    )

@app.get('/test')
def test():
    import boto3
    session = boto3.Session()
    return {
        'sessionRegion': session.region_name,
        'event': app.current_event.raw_event,
        'jwtClaims': app.current_event.request_context.authorizer.jwt_claim,
    }

@logger.inject_lambda_context(correlation_id_path=API_GATEWAY_HTTP)
def handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
