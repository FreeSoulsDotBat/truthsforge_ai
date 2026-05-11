from fastapi import APIRouter

from app.core.contracts import ProviderName, ProviderSecretStatus, ProviderSecretUpsert
from app.security.secrets import get_secret_store

router = APIRouter()


@router.get("/providers", response_model=list[ProviderSecretStatus])
def provider_statuses() -> list[ProviderSecretStatus]:
    return get_secret_store().all_statuses()


@router.put("/providers/{provider}/api-key", response_model=ProviderSecretStatus)
def upsert_provider_key(
    provider: ProviderName, payload: ProviderSecretUpsert
) -> ProviderSecretStatus:
    store = get_secret_store()
    store.set_api_key(provider, payload.api_key)
    return store.status(provider)


@router.delete("/providers/{provider}/api-key", response_model=ProviderSecretStatus)
def delete_provider_key(provider: ProviderName) -> ProviderSecretStatus:
    store = get_secret_store()
    store.delete_api_key(provider)
    return store.status(provider)
