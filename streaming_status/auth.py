from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2

from .config import config
from .data_sources import keycloak_api


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

    def roles(self) -> list[str]:
        return (
            self._introspect_token()
                .get('resource_access', {})
                # TODO see if we can use the same client instead of using two clients.
                # right now we use this client for the roles and the iot-service client
                # for the service account. This is because the iot-installer-client secret
                # is exposed to providers.
                .get('iot-installer-client', {})
                .get('roles', [])
        )

    def is_admin(self) -> bool:
        return config.admin_role in self.roles()

    def _introspect_token(self) -> dict:
        self._introspected_token = (
            self._introspected_token
            or keycloak_api.introspect_oidc_token(self.token)
        )

        if not self._introspected_token.get('active', True):
            raise AppError.unauthorized("inactive token")

        return self._introspected_token
