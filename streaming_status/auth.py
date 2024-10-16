from enum import StrEnum

from aws_lambda_powertools.utilities.data_classes import APIGatewayProxyEventV2

from .config import config
from .data_sources import keycloak_api
from .utils import AppError


class Role(StrEnum):
    admin = "admin"
    installer = "installer"
    external_installer = "external-installer"
    data_scientist = "data-scientist"
    organization_member = "org-member"
    optional_schema = "optional-schema"


class Permission(StrEnum):
    providers_read = "providers:read"
    organizations_read = "organizations:read"
    devices_create = "devices:create"
    devices_update = "devices:update"
    device_label_update = "device_label:update"
    optional_schema = "optional_schema"
    schema_notifications_subscribe = "schema_notifications:subscribe"

    @staticmethod
    def merge_inplace(into: dict["Permission", bool], from_: dict["Permission", bool]):
        for permission in from_:
            into[permission] = into.get(permission, False) or from_[permission]
        return into


_role_permissions = {
    Role.admin.value: {
        Permission.providers_read: True,
        Permission.organizations_read: True,
        Permission.devices_create: True,
        Permission.devices_update: True,
        Permission.device_label_update: True,
        Permission.schema_notifications_subscribe: True,
    },
    Role.installer.value: {
        Permission.providers_read: False,
        Permission.organizations_read: True,
        Permission.devices_create: True,
        Permission.devices_update: True,
        Permission.device_label_update: True,
        Permission.schema_notifications_subscribe: True,
    },
    Role.external_installer.value: {
        Permission.providers_read: False,
        Permission.organizations_read: False,
        Permission.devices_create: True,
        Permission.devices_update: True,
        Permission.device_label_update: True,
        Permission.schema_notifications_subscribe: True,
    },
    Role.data_scientist.value: {
        Permission.providers_read: True,
        Permission.organizations_read: True,
        Permission.devices_create: False,
        Permission.device_label_update: False,
        Permission.schema_notifications_subscribe: False,
    },
    Role.organization_member.value: {
        Permission.providers_read: False,
        Permission.organizations_read: False,
        Permission.devices_create: False,
        Permission.device_label_update: False,
        Permission.schema_notifications_subscribe: False,
    },
    Role.optional_schema.value: {
        Permission.optional_schema: True,
    },
}


class Auth:
    def __init__(self, event: APIGatewayProxyEventV2):
        self._event = event
        auth_header = self._event.get_header_value("Authorization") or ""
        self.token = auth_header.removeprefix("Bearer ")
        self._introspected_token: dict | None = None
        self._groups: list[str] | None = None

    def email(self) -> str:
        return self._introspect_token()["email"]

    def user_id(self) -> str | None:
        return self._introspect_token().get("sub")

    def name(self) -> str:
        token = self._introspect_token()
        return token.get("name") or token["email"]

    def group_memberships(self) -> list[str]:
        return self._introspect_token().get("groups", [])

    def _roles(self) -> list[str]:
        roles = self._introspect_token().get("resource_access", {}).get(config.oidc_client_id, {}).get("roles", [])

        if Role.external_installer in roles:
            # special case for external installers as they have the installer role as well.
            # NOTE: device registration API does not recognize external installer role and so requires the installer role.
            if Role.installer in roles:
                roles.remove(Role.installer)
            # A user cannot be both an admin and an external installer. Assume least privilege.
            if Role.admin in roles:
                roles.remove(Role.admin)
        return roles

    def is_admin(self) -> bool:
        return Role.admin in self._roles()

    def is_provider(self) -> bool:
        roles = self._roles()
        return Role.installer in roles or Role.external_installer in roles

    def has_permission(self, *permissions: Permission) -> bool:
        current_permissions = self.get_permissions()
        return all(current_permissions[permission] for permission in permissions)

    def get_permissions(self) -> dict[Permission, bool]:
        permissions: dict[Permission, bool]
        roles = self._roles()

        permissions = {}
        for ps in (_role_permissions[r] for r in roles if r in _role_permissions):
            Permission.merge_inplace(permissions, ps)

        return permissions

    def has_auto_warehouse_opt_out(self) -> bool:
        return bool(self._introspect_token().get("auto_warehouse_opt_out", False))

    def _introspect_token(self) -> dict:
        self._introspected_token = self._introspected_token or keycloak_api.introspect_oidc_token(self.token)

        if not self._introspected_token.get("active", True):
            raise AppError.unauthorized("inactive token")

        return self._introspected_token
