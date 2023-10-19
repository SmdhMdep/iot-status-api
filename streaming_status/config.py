import os

class _Config:
    @property
    def enable_debug(self) -> bool:
        return os.environ['STAGE'] == 'dev'

    @property
    def cors_allowed_origin(self) -> str:
        return os.environ['CORS_ALLOWED_ORIGIN']


config = _Config()
