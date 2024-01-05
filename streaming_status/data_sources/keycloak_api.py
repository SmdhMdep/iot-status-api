import requests

from ..config import config


def introspect_oidc_token(token: str) -> dict:
    return _unwrap(requests.post(
        f'{config.oidc_jwt_issuer_url}/protocol/openid-connect/token/introspect',
        auth=(config.oidc_client_id, config.oidc_client_secret),
        data=f'token={token}',
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ))

def groups(token, name_like: str | None, page: int, page_size: int) -> tuple[int | None, list[str]]:
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
