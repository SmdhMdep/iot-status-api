from datetime import datetime
from typing import TypedDict, NotRequired
from enum import StrEnum

from .data_sources.constants import ThingAttributeNames, DISCONNECT_REASON_DESCRIPTIONS


Timestamp = float
"""Seconds since epoch."""

DeviceConnectivity = TypedDict("DeviceConnectivity", {
    "connected": bool,
    "timestamp": Timestamp | None,
    "disconnectReason": str | None,
    "disconnectReasonDescription": str | None,
})

DeviceInfo = TypedDict("DeviceInfo", {
    "organization": str,
    "project": str,
    "provisioningStatus": str | None,
    "provisioningTimestamp": Timestamp | None,
    "registrationStatus": str | None,
    "registrationTimestamp": Timestamp | None,
})


class DeviceCustomLabel(StrEnum):
    deployed = 'DEPLOYED'
    undeployed = 'UNDEPLOYED'
    periodic_batch = 'PERIODIC_BATCH'
    deactivated = 'DEACTIVATED'

    @classmethod
    def from_value(cls, value: str):
        return next((status for status in cls if status.value == value), None)


Device = TypedDict("Device", {
    "name": str,
    "provider": str | None,
    "organization": str | None,
    "connectivity": DeviceConnectivity | None,
    "deviceInfo": NotRequired[DeviceInfo],
    "label": NotRequired[DeviceCustomLabel],
    "dataSchema": NotRequired[str],
    # a JSONL file preview
    "streamPreview": NotRequired[str],
    "streamLastBatchTimestamp": Timestamp | None,
})


def entity_to_model(
    *,
    fleet_entity=None,
    ledger_entity=None,
    stream_preview: tuple[str, datetime | None] | None = None,
    ledger_entity_unprovisioned: bool = True,
) -> Device:
    assert fleet_entity is not None or ledger_entity is not None
    fleet_entity_attrs = (fleet_entity or {}).get("attributes", {})

    provider = (
        ledger_entity["jwtGroup"] if ledger_entity and "jwtGroup" in ledger_entity
        else fleet_entity_attrs.get(ThingAttributeNames.SENSOR_PROVIDER)
    )
    provider = ' '.join(map(str.capitalize, provider.split("-"))) if provider else None
    organization = (
        ledger_entity['org'] if ledger_entity
        else fleet_entity_attrs.get(ThingAttributeNames.SENSOR_ORGANIZATION)
    )
    organization = ' '.join(map(str.capitalize, organization.split("-"))) if organization else None

    last_stream_ts = stream_preview[1] if stream_preview else None
    data_schema = (ledger_entity or {}).get("json_schema")
    label = (ledger_entity or {}).get("customLabel")

    return {
        "name": fleet_entity['thingName'] if fleet_entity else ledger_entity["serialNumber"],
        "connectivity": _connectivity_to_model(fleet_entity, use_default_unprovisioned=ledger_entity_unprovisioned),
        "provider": provider,
        "organization": organization,
        **({ "deviceInfo": _device_info_to_model(ledger_entity) } if ledger_entity else {}),
        **({
            "streamPreview": stream_preview[0],
            "lastStreamBatchTimestamp": last_stream_ts.timestamp() if last_stream_ts else None,
        } if stream_preview else {}),
        **({"dataSchema": data_schema} if data_schema is not None and data_schema != '{}' else {}),
        **({
            'label': DeviceCustomLabel.from_value(label)
        } if ledger_entity is not None and label is not None else {}),
    }

def _connectivity_to_model(fleet_entity=None, use_default_unprovisioned=True) -> DeviceConnectivity | None:
    connectivity = fleet_entity['connectivity'] if fleet_entity else None
    return {
        'connected': connectivity['connected'],
        'timestamp': timestamp / 1000.0 if (timestamp := connectivity['timestamp']) > 0 else None,
        'disconnectReason': (disconnect_reason := connectivity.get('disconnectReason')),
        'disconnectReasonDescription': (
            DISCONNECT_REASON_DESCRIPTIONS[disconnect_reason]
            if disconnect_reason is not None else None
        ),
    } if connectivity else {
        "connected": False,
        "timestamp": None,
        "disconnectReason": "NOT_PROVISIONED", # custom reason
        "disconnectReasonDescription": "The client has not been provisioned yet.",
    } if use_default_unprovisioned else None

def _device_info_to_model(ledger_entity) -> DeviceInfo:
    return {
        "organization": ledger_entity["org"],
        "project": ledger_entity["proj"],
        "provisioningStatus": ledger_entity.get("provStatus"),
        "provisioningTimestamp": _iso_to_timestamp_or_none(ledger_entity.get("provTimestamp")),
        "registrationStatus": ledger_entity.get("regStatus"),
        "registrationTimestamp": _iso_to_timestamp_or_none(ledger_entity.get("regTimestamp")),
    }

def _iso_to_timestamp_or_none(iso_formatted: str | None) -> Timestamp | None:
    if iso_formatted is None:
        return None

    if iso_formatted.endswith('Z'):
        iso_formatted = f"{iso_formatted[:-1]}+00:00"
    return datetime.fromisoformat(iso_formatted).timestamp()
