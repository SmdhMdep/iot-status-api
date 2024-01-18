class AppError(Exception):
    INTERNAL_ERROR_CODE = 500
    NOT_FOUND_CODE = 404
    INVALID_CODE = 400
    UNAUTHORIZED_CODE = 401

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code

    @classmethod
    def not_found(cls, message):
        return cls(cls.NOT_FOUND_CODE, message)

    @classmethod
    def invalid_argument(cls, message):
        return cls(cls.INVALID_CODE, message)

    @classmethod
    def unauthorized(cls, message):
        return cls(cls.UNAUTHORIZED_CODE, message)

    @classmethod
    def internal_error(cls, message):
        return cls(cls.INTERNAL_ERROR_CODE, message)
