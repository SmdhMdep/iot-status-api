import requests
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.event_handler.middlewares import NextMiddleware
from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2

from .config import config


class Auth:
    def __init__(self, event: APIGatewayProxyEventV2):
        self._event = event
        self._introspected_token: dict | None = None

    def group_memberships(self) -> list[str]:
        return self.introspected_token().get('groups', [])

    def introspected_token(self) -> dict:
        if self._introspected_token is not None:
            return self._introspected_token

        bearer_auth = self._event.get_header_value('Authorization') or ''
        token = bearer_auth.removeprefix('Bearer ')

        response = requests.post(
            f'{config.oidc_jwt_issuer_url}/protocol/openid-connect/token/introspect',
            auth=(config.oidc_client_id, config.oidc_client_secret),
            data=f'token={token}',
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()

        self._introspected_token = response.json()
        return self._introspected_token


def get_auth(app: APIGatewayHttpResolver) -> Auth:
    auth = app.context.get('auth')
    if auth is None:
        auth = Auth(app.current_event)
        app.append_context(auth=auth)
    return auth
