from csv import DictWriter
from io import StringIO, TextIOBase
from typing import Any

from .model import Device

DEVICE_DTO_KEYS = [
    "name",
    "connectivity.connected",
    "connectivity.timestamp",
    "connectivity.disconnectReason",
    "connectivity.disconnectReasonDescription",
    "provider",
    "deviceInfo.organization",
    "deviceInfo.project",
    "deviceInfo.provisioningStatus",
    "deviceInfo.provisioningTimestamp",
    "deviceInfo.registrationStatus",
    "deviceInfo.registrationTimestamp",
    "label",
]


def serialize_devices(data: list[Device]) -> str:
    """Serialize list of device DTO into a CSV format"""
    with StringIO() as file:
        _write_csv(file, DEVICE_DTO_KEYS, data)
        file.seek(0)
        return file.read()


def _write_csv(file: TextIOBase, keys: list[str], data: list[Device]):
    writer = DictWriter(file, keys)
    writer.writeheader()
    for datum in data:
        writer.writerow({key: _read_value(datum, key) for key in keys})


def _read_value(data: Device, key: str):
    segments = key.split(".")
    value: Any = data

    for segment in segments:
        value = value.get(segment)
        if value is None:
            return None

    return value
