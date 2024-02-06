from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import BaseProxyEvent

from .errors import AppError


logger = Logger()


def get_query_integer_value(event: BaseProxyEvent, name: str) -> int:
    arg = event.get_query_string_value(name, "0")

    try:
        return int(arg) if arg else 0
    except ValueError:
        raise AppError.invalid_argument(f"{name} must be an integer")
