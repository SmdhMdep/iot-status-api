import re
from typing import TypedDict, TypeVar, Generic, NotRequired

from .auth import Auth
from .errors import AppError
from .model import entity_to_model, Device
from .utils import logger
from .data_sources import device_ledger, fleet_index, stream_data, keycloak_api


device_name_regex = re.compile(r'[a-zA-Z0-9:_-]+')

DEFAULT_PAGE_SIZE = 20

LedgerPage = str | None
FleetPage = str | None

_T = TypeVar('_T')
_P = TypeVar('_P')


class PaginatedResult(Generic[_P, _T], TypedDict):
    nextPage: NotRequired[_P | None]
    items: list[_T]


def list_devices(
    provider: str | None,
    organization: str | None,
    name_like: str | None = None,
    page: str | None = None,
    page_size: int | None = DEFAULT_PAGE_SIZE,
) -> PaginatedResult[str, Device]:
    provider = _canonicalize_group_name(provider)
    organization = _canonicalize_group_name(organization)
    ledger_page, fleet_page = _load_page(page)
    ledger_items, fleet_items, next_page = [], [], None # type: ignore

    is_first_page = not ledger_page and not fleet_page
    if ledger_page or is_first_page:
        next_page, ledger_items = device_ledger.list_devices(
            provider,
            organization=organization,
            name_like=name_like,
            page=ledger_page,
            page_size=page_size,
            unprovisioned_only=True,
        )
        if next_page:
            next_page = _dump_page(LedgerPage, next_page)

    is_partial_page = not next_page and (page_size is None or len(ledger_items) < page_size)
    if fleet_page or is_partial_page:
        cont_page_size = page_size - len(ledger_items) if page_size is not None else None
        next_page, fleet_items = fleet_index.list_devices(
            provider,
            organization=organization,
            name_like=name_like,
            page=fleet_page,
            page_size=cont_page_size,
        )
        if next_page:
            next_page = _dump_page(FleetPage, next_page)

    return _search_result_to_model(
        ledger_items=ledger_items,
        fleet_items=fleet_items,
        next_page=next_page,
    )

def export_devices(provider: str | None, organization: str | None) -> list[Device]:
    provider = _canonicalize_group_name(provider)
    organization = _canonicalize_group_name(organization)
    _, fleet_items = fleet_index.list_devices(provider=provider, organization=organization)
    _, ledger_items = device_ledger.list_devices(provider=provider, organization=organization)
    return _merge_entities_to_models(fleet_items, ledger_items)

def get_device(
    provider: str | None,
    organization: str | None,
    device_name: str,
    brief_repr: bool = False,
) -> Device:
    provider = _canonicalize_group_name(provider)
    organization = _canonicalize_group_name(organization)
    if not device_name_regex.fullmatch(device_name):
        raise AppError.invalid_argument(f"name must match the regex: {device_name_regex.pattern}")

    ledger_device = device_ledger.find_device(provider, organization, device_name)
    if not ledger_device:
        raise AppError.not_found(f'device with name {device_name} is not registered')
    if brief_repr:
        return entity_to_model(ledger_entity=ledger_device)

    fleet_device = fleet_index.find_device(provider, organization, device_name)

    try:
        topic = _get_streaming_topic(ledger_device)
        preview = stream_data.get_stream_preview(topic=topic) if topic else None
    except AppError as e:
        if e.status_code != AppError.INTERNAL_ERROR_CODE:
            raise
        logger.exception("(suppressed) error fetching stream preview")
        preview = "<error fetching preview>", None

    return entity_to_model(fleet_entity=fleet_device, ledger_entity=ledger_device, stream_preview=preview)

def list_providers(
    name_like: str | None = None,
    page: int | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PaginatedResult[int, str]:
    next_page, groups = keycloak_api.groups(
        name_like=name_like, page=page or 0, page_size=page_size
    )
    return {'items': groups, 'nextPage': next_page}

def list_organizations(
    name_like: str | None = None,
    page: int | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    next_page, groups = keycloak_api.groups(
        name_like=name_like, page=page or 0, page_size=page_size
    )
    return {'items': groups, 'nextPage': next_page}

def _canonicalize_group_name(group: str | None) -> str | None:
    return '-'.join(group.lower().split(' ')) if group is not None else None

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
        raise AppError.internal_error("inconsistent state when fetching stream preview")

    return resource.split('topic/', maxsplit=1)[-1]

def _search_result_to_model(
    *,
    ledger_items: list[dict],
    fleet_items: list[dict],
    next_page: str | None,
) -> PaginatedResult[str, Device]:
    """Create a search result based on items from both data sources.

    `ledger_items` and `fleet_items` must form a disjoint set.
    """
    return {
        'nextPage': next_page,
        'items': [
            *(entity_to_model(ledger_entity=entity) for entity in ledger_items),
            *(entity_to_model(fleet_entity=entity) for entity in fleet_items),
        ]
    }

def _merge_entities_to_models(fleet_items, ledger_items) -> list[Device]:
    """Merges device entities from fleet index and device ledger into a list of models.

    Assumes `ledger_items` is a superset of `fleet_items`.
    """
    lookup = {fleet_entity['thingName']: fleet_entity for fleet_entity in fleet_items}
    return [
        entity_to_model(
            fleet_entity=lookup.get(ledger_entity['serialNumber']),
            ledger_entity=ledger_entity,
        )
        for ledger_entity in ledger_items
    ]
