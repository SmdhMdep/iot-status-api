import os


class _Config:
    @property
    def is_offline(self) -> bool:
        return os.environ.get("IS_OFFLINE") == "true"

    @property
    def oidc_client_id(self) -> str:
        return os.environ["OIDC_CLIENT_ID"]

    @property
    def oidc_client_secret(self) -> str:
        return os.environ["OIDC_CLIENT_SECRET"]

    @property
    def oidc_jwt_issuer_url(self) -> str:
        return os.environ["OIDC_JWT_ISSUER_URL"]

    @property
    def keycloak_admin_api_url(self) -> str:
        return os.environ["KEYCLOAK_ADMIN_API_BASE_URL"]

    @property
    def cors_allowed_origin(self) -> str:
        return os.environ["CORS_ALLOWED_ORIGIN"]

    @property
    def fleet_index_iot_region_name(self) -> str:
        return os.environ["FLEET_INDEX_IOT_REGION_NAME"]

    @property
    def device_ledger_table_name(self) -> str:
        return os.environ["DEVICE_LEDGER_TABLE_NAME"]

    @property
    def device_ledger_index_name(self) -> str | None:
        return os.environ.get("DEVICE_LEDGER_INDEX_NAME")

    @property
    def device_ledger_groups_index_name(self) -> str | None:
        return os.environ.get("DEVICE_LEDGER_GROUPS_INDEX_NAME")

    @property
    def device_ledger_org_proj_index_name(self) -> str:
        return os.environ["DEVICE_LEDGER_ORG_PROJ_INDEX_NAME"]

    @property
    def device_ledger_table_region(self) -> str:
        return os.environ["DEVICE_LEDGER_TABLE_REGION"]

    @property
    def schema_registry_table_name(self) -> str:
        return os.environ["SCHEMA_REGISTRY_TABLE_NAME"]

    @property
    def schema_registry_table_region(self) -> str:
        return os.environ["SCHEMA_REGISTRY_TABLE_REGION"]

    @property
    def stream_data_bucket_name(self) -> str:
        return os.environ["STREAM_DATA_BUCKET_NAME"]

    @property
    def stream_data_bucket_region(self) -> str:
        return os.environ["STREAM_DATA_BUCKET_REGION"]

    @property
    def mdep_url(self) -> str:
        return os.environ["MDEP_URL"]

    @property
    def mdep_api_key(self) -> str:
        return os.environ["MDEP_API_KEY"]

    @property
    def device_alarms_dest_sns_topic_name_prefix(self) -> str:
        arn = os.environ["DEVICE_ALARMS_DEST_SNS_TOPIC_ARN_PREFIX"]
        return arn.rsplit(":", maxsplit=1)[-1]

    @property
    def device_alarms_table_name(self) -> str:
        return os.environ["DEVICE_ALARMS_TABLE_NAME"]

    @property
    def device_alarms_table_region(self) -> str:
        return os.environ["DEVICE_ALARMS_TABLE_REGION"]

    @property
    def schema_notifications_table(self) -> str:
        return os.environ["SCHEMA_NOTIFICATIONS_TABLE"]

    @property
    def schema_notifications_sns_prefix(self) -> str:
        return os.environ["SCHEMA_NOTIFICATIONS_SNS_TOPIC_PREFIX"]

    @property
    def schema_notifications_region(self) -> str:
        return os.environ["SCHEMA_NOTIFICATIONS_REGION"]


config = _Config()
