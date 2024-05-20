from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.api_gateway import BaseProxyEvent

from .errors import AppError
from .model import DeviceCustomLabel


logger = Logger()


def get_query_integer_value(event: BaseProxyEvent, name: str, default: int = 0) -> int:
    arg = event.get_query_string_value(name)

    try:
        return int(arg) if arg is not None else default
    except ValueError:
        raise AppError.invalid_argument(f"{name} must be an integer")


def parse_date_range_or_default(range_value):
    from datetime import datetime, timedelta

    if range_value is not None:
        try:
            start, end = range_value.split(',')
            start_date, end_date = (
                datetime.fromtimestamp(int(start)),
                datetime.fromtimestamp(int(end))
            )
        except (ValueError, OverflowError):
            raise AppError.invalid_argument("invalid date range format")
    else:
        current_date = datetime.now()
        start_date = current_date - timedelta(days=1)
        end_date = current_date

    return (start_date, end_date)


def parse_device_custom_label(raw_label: str) -> DeviceCustomLabel:
    label = None
    if isinstance(raw_label, str):
        label = DeviceCustomLabel.from_value(raw_label)
    if label is None:
        names = [label.value for label in DeviceCustomLabel]
        raise AppError.invalid_argument(f'label must be one of: {", ".join(names)}')

    return label
