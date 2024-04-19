from enum import StrEnum

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2

from .config import config
from .data_sources import keycloak_api
from .utils import AppError


class Role(StrEnum):
    admin = 'admin'
    installer = 'installer'
    external_installer = 'external-installer'
    data_scientist = 'data-scientist'
    organization_member = 'org-member'


class Permission(StrEnum):
    providersList = 'providers:list'
    organizationsList = 'organizations:list'
    devicesRegister = 'devices:register'

    @staticmethod
    def merge_inplace(into: dict['Permission', bool], from_: dict['Permission', bool]):
        for permission in from_:
            into[permission] = into.get(permission, False) or from_[permission]
        return into


_role_permissions = {
    Role.admin.value: {
        Permission.providersList: True,
        Permission.organizationsList: True,
        Permission.devicesRegister: True,
    },
    Role.installer.value: {
        Permission.providersList: False,
        Permission.organizationsList: True,
        Permission.devicesRegister: True,
    },
    Role.external_installer.value: {
        Permission.providersList: False,
        Permission.organizationsList: False,
        Permission.devicesRegister: True,
    },
    Role.data_scientist.value: {
        Permission.providersList: True,
        Permission.organizationsList: True,
        Permission.devicesRegister: False,
    },
    Role.organization_member.value: {
        Permission.providersList: False,
        Permission.organizationsList: False,
        Permission.devicesRegister: False,
    },
}


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

    def get_permissions(self) -> dict[Permission, bool]:
        permissions: dict[Permission, bool]
        roles = self._roles()

        # special case for external installers as they have the installer role as well
        # but we don't want them to be able to list organizations/installers
        if Role.external_installer in roles and Role.installer in roles:
            permissions = _role_permissions[Role.external_installer]
        else:
            permissions = {}
            for ps in (_role_permissions[r] for r in roles):
                Permission.merge_inplace(permissions, ps)

        return permissions

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
