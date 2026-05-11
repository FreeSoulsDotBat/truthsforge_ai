import httpx
from fastapi import APIRouter, HTTPException

from app.core.contracts import ModelConfig, ModelUpsert, ProviderModel, ProviderName
from app.llm_gateway.gateway import LLMGateway
from app.llm_gateway.providers import ProviderConfigurationError
from app.storage.store import get_store

router = APIRouter()


@router.get("", response_model=list[ModelConfig])
def list_models() -> list[ModelConfig]:
    return get_store().list_models()


@router.post("", response_model=ModelConfig)
def upsert_model(payload: ModelUpsert) -> ModelConfig:
    return get_store().upsert_model(payload)


@router.get("/providers/{provider}", response_model=list[ProviderModel])
async def list_provider_models(provider: ProviderName) -> list[ProviderModel]:
    try:
        return await LLMGateway().list_models(provider)
    except ProviderConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Falha ao listar modelos de {provider.value}.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"Falha de rede ao consultar {provider.value}."
        ) from exc
