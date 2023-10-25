import os

class _Config:
    @property
    def enable_debug(self) -> bool:
        return os.environ['STAGE'] == 'dev'

    @property
    def iot_region_name(self) -> str:
        return os.environ['AWS_IOT_REGION']

    @property
    def s3_bucket_name(self) -> str:
        return os.environ['S3_BUCKET_NAME']

    @property
    def s3_bucket_region(self) -> str:
        return os.environ['S3_BUCKET_REGION']

    @property
    def mdep_url(self) -> str:
        return os.environ['MDEP_URL']

    @property
    def mdep_api_key(self) -> str:
        return os.environ['MDEP_API_KEY']

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
