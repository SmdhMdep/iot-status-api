import re
from datetime import datetime

from .auth import Auth
from .errors import AppError
from .data_sources import device_ledger, fleet_index, stream_data, keycloak_api


device_name_regex = re.compile(r'[a-zA-Z0-9:_-]+')

PAGE_SIZE = 20

LedgerPage = str | None
FleetPage = str | None


def list_devices(provider: str | None, name_like: str | None = None, page: str | None = None):
    provider = _canonicalize_provider_name(provider) if provider is not None else None
    ledger_page, fleet_page = _load_page(page)
    ledger_items, fleet_items, next_page = [], [], None # type: ignore

    is_first_page = not ledger_page and not fleet_page
    if ledger_page or is_first_page:
        next_page, ledger_items = device_ledger.list_unprovisioned_devices(
            provider, name_like=name_like, page=ledger_page, page_size=PAGE_SIZE
        )
        if next_page:
            next_page = _dump_page(LedgerPage, next_page)

    is_partial_page = not next_page and len(ledger_items) < PAGE_SIZE
    if fleet_page or is_partial_page:
        page_size = PAGE_SIZE - len(ledger_items)
        next_page, fleet_items = fleet_index.list_devices(
            provider, name_like=name_like, page=fleet_page, page_size=page_size
        )
        if next_page:
            next_page = _dump_page(FleetPage, next_page)

    return _search_result_to_dto(
        ledger_items=ledger_items,
        fleet_items=fleet_items,
        next_page=next_page
    )

def get_device(provider: str | None, device_name: str):
    provider = _canonicalize_provider_name(provider) if provider is not None else None
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")

    ledger_device = device_ledger.find_device(provider, device_name)
    if not ledger_device:
        raise AppError.not_found(f'device with name {device_name} is not registered')

    fleet_device = fleet_index.find_device(provider, device_name)

    topic = _get_streaming_topic(ledger_device)
    preview = stream_data.get_stream_preview(topic=topic) if topic else None
    dto = _model_to_dto(fleet_model=fleet_device, ledger_model=ledger_device, stream_preview=preview)
    return dto

def list_providers(auth: Auth, name_like: str | None = None, page: int | None = None):
    if auth.is_admin():
        next_page, providers = keycloak_api.groups(
            auth.token, name_like=name_like, page=page or 0, page_size=PAGE_SIZE
        )
        return {'providers': providers, 'nextPage': next_page}
    else:
        name_like = name_like or ''
        providers = [
            group for group in auth.group_memberships()
            if name_like in group
        ]
        return {'providers': providers}

def _canonicalize_provider_name(provider: str) -> str:
    return '-'.join(provider.lower().split(' '))

def _load_page(page: str | None) -> tuple[LedgerPage, FleetPage]:
    if not page:
        return None, None
    elif page.startswith('l'):
        return page[1:], None
    elif page.startswith('f'):
        return None, page[1:]
    else:
        raise AppError.invalid_argument('invalid page key')

def _dump_page(page_type, page: str) -> str:
    return f'l{page}' if page_type is LedgerPage else f'f{page}'

def _get_streaming_topic(ledger_item) -> str | None:
    if ledger_item.get('provStatus') is None:
        return None

    statements = ledger_item.get('policyDoc', {}).get('Statement', [])
    resource = next(
        (stmt["Resource"] for stmt in statements if stmt["Action"] == "iot:Publish"),
        None,
    )
    if not resource:
        raise AppError(500, "inconsistent state when fetching stream preview")

    return resource.split('topic/', maxsplit=1)[-1]

def _search_result_to_dto(*, ledger_items, fleet_items, next_page):
    return {
        'nextPage': next_page,
        'devices': [
            *(_model_to_dto(ledger_model=device) for device in ledger_items),
            *(_model_to_dto(fleet_model=device) for device in fleet_items),
        ]
    }

def _model_to_dto(
    *,
    fleet_model=None,
    ledger_model=None,
    stream_preview: str | None = None,
):
    assert(fleet_model is not None or ledger_model is not None)

    provider = (
        ledger_model["jwtGroup"] if ledger_model and "jwtGroup" in ledger_model
        else (fleet_model or {}).get("attributes", {}).get(fleet_index.SENSOR_PROVIDER)
    )
    provider = ' '.join(map(str.capitalize, provider.split("-"))) if provider else None

    return {
        "name": fleet_model['thingName'] if fleet_model else ledger_model["serialNumber"],
        "connectivity": _connectivity_to_dto(fleet_model),
        "provider": provider,
        **({ "deviceInfo": _device_info_to_dto(ledger_model) } if ledger_model else {}),
        **({ "streamPreview": stream_preview } if stream_preview else {}),
    }

def _connectivity_to_dto(fleet_model=None):
    connectivity = fleet_model['connectivity'] if fleet_model else None
    return {
        'connected': connectivity['connected'],
        'timestamp': timestamp / 1000.0 if (timestamp := connectivity['timestamp']) > 0 else None,
        'disconnectReason': (disconnect_reason := connectivity.get('disconnectReason')),
        'disconnectReasonDescription': (
            fleet_index.get_disconnect_description(disconnect_reason)
            if disconnect_reason is not None else None
        ),
    } if connectivity else {
        "connected": False,
        "timestamp": None,
        "disconnectReason": "NOT_PROVISIONED", # custom reason
        "disconnectReasonDescription": "The client has not been provisioned yet.",
    }

def _device_info_to_dto(ledger_model):
    return {
        "organization": ledger_model["org"],
        "project": ledger_model["proj"],
        "provisioningStatus": ledger_model.get("provStatus"),
        "provisioningTimestamp": _iso_to_timestamp_or_none(ledger_model.get("provTimestamp")),
        "registrationStatus": ledger_model.get("regStatus"),
        "registrationTimestamp": _iso_to_timestamp_or_none(ledger_model.get("regTimestamp")),
    }

def _iso_to_timestamp_or_none(iso_formatted: str | None):
    if iso_formatted is None:
        return None

    if iso_formatted.endswith('Z'):
        iso_formatted = f"{iso_formatted[:-1]}+00:00"
    return datetime.fromisoformat(iso_formatted).timestamp()
