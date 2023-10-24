import re
from datetime import datetime

from .errors import AppError
from .data_sources import device_ledger, fleet_index


device_name_regex = re.compile(r'[a-zA-Z0-9:_-]+')

DEVICES_PAGE_SIZE = 20

LedgerPage = str | None
FleetPage = str | None


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

def list_devices(provider: str, name_like: str | None = None, page: str | None = None):
    provider = _canonicalize_provider_name(provider)
    ledger_page, fleet_page = _load_page(page)
    ledger_items, fleet_items, next_page = [], [], None # type: ignore

    is_first_page = not ledger_page and not fleet_page
    if ledger_page or is_first_page:
        next_page, ledger_items = device_ledger.list_unprovisioned_devices(
            provider, name_like=name_like, page=ledger_page, page_size=DEVICES_PAGE_SIZE
        )
        if next_page:
            next_page = _dump_page(LedgerPage, next_page)

    is_partial_page = not next_page and len(ledger_items) < DEVICES_PAGE_SIZE
    if fleet_page or is_partial_page:
        page_size = DEVICES_PAGE_SIZE - len(ledger_items)
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

def get_device(provider, device_name):
    provider = _canonicalize_provider_name(provider)
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")

    ledger_device = device_ledger.find_device(provider, device_name)
    if not ledger_device:
        raise AppError.not_found(f'device with name {device_name} is not registered')

    fleet_device = fleet_index.find_device(provider, device_name)

    return _model_to_dto(fleet_model=fleet_device, ledger_model=ledger_device)

def _search_result_to_dto(*, ledger_items, fleet_items, next_page):
    return {
        'nextPage': next_page,
        'devices': [
            *(_model_to_dto(ledger_model=device) for device in ledger_items),
            *(_model_to_dto(fleet_model=device) for device in fleet_items),
        ]
    }

def _model_to_dto(*, fleet_model=None, ledger_model=None):
    if not fleet_model:
        return {
            "name": ledger_model["serialNumber"],
            "connectivity": {
                "connected": False,
                "timestamp": None,
                "disconnectReason": "NOT_PROVISIONED", # custom reason
                "disconnectReasonDescription": "The client has not been provisioned yet."
            },
            "deviceInfo": _device_info_to_dto(ledger_model),
        }
    else:
        model_connectivity = fleet_model['connectivity']
        dto = {
            "name": fleet_model['thingName'],
            "connectivity": {
                'connected': model_connectivity['connected'],
                'timestamp': model_connectivity['timestamp'] / 1000.0,
                'disconnectReason': (disconnect_reason := model_connectivity.get('disconnectReason')),
                'disconnectReasonDescription': (
                    fleet_index.get_disconnect_description(disconnect_reason)
                    if disconnect_reason is not None else None
                )
            },
        }
        if ledger_model:
            dto["deviceInfo"] = _device_info_to_dto(ledger_model)

        return dto

def _iso_to_timestamp_or_none(iso_formatted: str | None):
    if iso_formatted is None:
        return None

    if iso_formatted.endswith('Z'):
        iso_formatted = f"{iso_formatted[:-1]}+00:00"
    return datetime.fromisoformat(iso_formatted).timestamp()

def _device_info_to_dto(device_info):
    return {
        "organization": device_info["org"],
        "project": device_info["proj"],
        "provisioningStatus": device_info.get("provStatus"),
        "provisioningTimestamp": _iso_to_timestamp_or_none(device_info.get("provTimestamp")),
        "registrationStatus": device_info.get("regStatus"),
        "registrationTimestamp": _iso_to_timestamp_or_none(device_info.get("regTimestamp")),
    }
