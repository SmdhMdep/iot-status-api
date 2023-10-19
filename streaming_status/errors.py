class AppError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code

    @classmethod
    def not_found(cls, message):
        return cls(404, message)

    @classmethod
    def invalid_argument(cls, message):
        return cls(400, message)

    @classmethod
    def unauthorized(cls, message):
        return cls(401, message)
