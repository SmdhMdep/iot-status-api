import os

class _Config:
    @property
    def enable_debug(self) -> bool:
        return os.environ['STAGE'] == 'dev'

    @property
    def iot_region_name(self) -> str:
        return os.environ['AWS_IOT_REGION']

    @property
    def oidc_client_id(self) -> str:
        return os.environ['OIDC_CLIENT_ID']

    @property
    def oidc_client_secret(self) -> str:
        return os.environ['OIDC_CLIENT_SECRET']

    @property
    def oidc_introspection_endpoint(self) -> str:
        return os.environ['OIDC_INTROSPECTION_ENDPOINT']

    @property
    def cors_allowed_origin(self) -> str:
        return os.environ['CORS_ALLOWED_ORIGIN']


config = _Config()
