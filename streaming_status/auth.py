from enum import StrEnum

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2

from .config import config
from .data_sources import keycloak_api
from .utils import AppError


class Role(StrEnum):
    admin = 'admin'
    installer = 'installer'
    data_scientist = 'data-scientist'
    organization_member = 'org-member'


class Auth:
    def __init__(self, event: APIGatewayProxyEventV2):
        self._event = event
        auth_header = self._event.get_header_value('Authorization') or ''
        self.token = auth_header.removeprefix('Bearer ')
        self._introspected_token: dict | None = None
        self._groups: list[str] | None = None

    def email(self) -> str:
        return self._introspect_token()['email']

    def group_memberships(self) -> list[str]:
        return self._introspect_token().get('groups', [])

    def _roles(self) -> list[str]:
        return (
            self._introspect_token()
                .get('resource_access', {})
                .get(config.oidc_client_id, {})
                .get('roles', [])
        )

    def has_role(self, *roles: Role) -> bool:
        user_roles = self._roles()
        return any(role in user_roles for role in roles)

    def _introspect_token(self) -> dict:
        self._introspected_token = (
            self._introspected_token
            or keycloak_api.introspect_oidc_token(self.token)
        )

        if not self._introspected_token.get('active', True):
            raise AppError.unauthorized("inactive token")

        return self._introspected_token
