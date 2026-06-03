from fastapi import APIRouter

from app.core.contracts import ProviderName, ProviderSecretStatus, ProviderSecretUpsert
from app.security.secrets import get_secret_store

# SEGURANÇA (api-rest-005): estas rotas GRAVAM/APAGAM segredos de provedor
# (API keys) e NÃO têm autenticação — por design local-first (ver AGENTS.md).
# A resposta NUNCA vaza a key (ProviderSecretStatus só expõe configured/source).
# PRESSUPOSTO DE SEGURANÇA: o backend é vinculado APENAS ao loopback. Se algum
# dia for exposto além do loopback (ex.: public_base_url não-loopback / acesso
# mobile via Tailscale/WireGuard anunciado no ServerStatus), estas rotas de
# escrita de segredo precisam ganhar um gate (token local/Origin) ANTES da
# exposição. Mantenha o bind loopback-only enquanto não houver esse gate.
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
