import functools
import requests

from ..config import config


def _get_service_account_token() -> str:
    return _unwrap(requests.post(
        f'{config.oidc_jwt_issuer_url}/protocol/openid-connect/token',
        data=dict(
            client_id=config.oidc_client_id,
            client_secret=config.oidc_client_secret,
            grant_type='client_credentials',
        ),
    ))['access_token']


_cached_token = None


def _use_service_token(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        global _cached_token
        if _cached_token is not None:
            try:
                return function(*args, **kwargs, token=_cached_token)
            except requests.HTTPError as e:
                if e.response.status_code != 401: # unauthorized, probably token expired
                    raise

        _cached_token = _get_service_account_token()
        return function(*args, **kwargs, token=_cached_token)

    return wrapper

def introspect_oidc_token(token: str) -> dict:
    return _unwrap(requests.post(
        f'{config.oidc_jwt_issuer_url}/protocol/openid-connect/token/introspect',
        auth=(config.oidc_client_id, config.oidc_client_secret),
        data=dict(token=token),
    ))

@_use_service_token
def groups(name_like: str | None, page: int, page_size: int, *, token) -> tuple[int | None, list[str]]:
    params: dict = {'max': page_size, 'first': page * page_size}
    if name_like is not None:
        params['search'] = name_like

    # schema: { "id": string, "name": string, "path": string, "subGroups": array }
    groups = _unwrap(requests.get(
        f'{config.keycloak_admin_api_url}/groups',
        headers={"Authorization": f"Bearer {token}"},
        params=params
    ))
    return (
        page + 1 if len(groups) >= page_size else None,
        [group['name'] for group in groups]
    )

def _unwrap(response):
    response.raise_for_status()
    return response.json()
