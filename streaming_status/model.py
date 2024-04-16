from datetime import datetime
from typing import TypedDict, NotRequired

from .data_sources import fleet_index


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

Device = TypedDict("Device", {
    "name": str,
    "provider": str | None,
    "connectivity": DeviceConnectivity,
    "deviceInfo": NotRequired[DeviceInfo],
    # a JSONL file preview
    "streamPreview": NotRequired[str],
    "streamLastBatchTimestamp": Timestamp | None,
})


def entity_to_model(
    *,
    fleet_entity=None,
    ledger_entity=None,
    stream_preview: tuple[str, datetime | None] | None = None,
) -> Device:
    assert fleet_entity is not None or ledger_entity is not None

    provider = (
        ledger_entity["jwtGroup"] if ledger_entity and "jwtGroup" in ledger_entity
        else (fleet_entity or {}).get("attributes", {}).get(fleet_index.SENSOR_PROVIDER)
    )
    provider = ' '.join(map(str.capitalize, provider.split("-"))) if provider else None

    last_stream_ts = stream_preview[1] if stream_preview else None

    return {
        "name": fleet_entity['thingName'] if fleet_entity else ledger_entity["serialNumber"],
        "connectivity": _connectivity_to_model(fleet_entity),
        "provider": provider,
        **({ "deviceInfo": _device_info_to_model(ledger_entity) } if ledger_entity else {}),
        **({
            "streamPreview": stream_preview[0],
            "lastStreamBatchTimestamp": last_stream_ts.timestamp() if last_stream_ts else None,
        } if stream_preview else {}),
    }

def _connectivity_to_model(fleet_entity=None) -> DeviceConnectivity:
    connectivity = fleet_entity['connectivity'] if fleet_entity else None
    return {
        'connected': connectivity['connected'],
        'timestamp': timestamp / 1000.0 if (timestamp := connectivity['timestamp']) > 0 else None,
        'disconnectReason': (disconnect_reason := connectivity.get('disconnectReason')),
        'disconnectReasonDescription': (
            fleet_index.DISCONNECT_REASON_DESCRIPTIONS[disconnect_reason]
            if disconnect_reason is not None else None
        ),
    } if connectivity else {
        "connected": False,
        "timestamp": None,
        "disconnectReason": "NOT_PROVISIONED", # custom reason
        "disconnectReasonDescription": "The client has not been provisioned yet.",
    }

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
