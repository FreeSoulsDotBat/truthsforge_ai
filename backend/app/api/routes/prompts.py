from fastapi import APIRouter

from app.core.contracts import Prompt, PromptCreate
from app.storage.store import get_store

router = APIRouter()


@router.get("", response_model=list[Prompt])
def list_prompts() -> list[Prompt]:
    return get_store().list_prompts()


@router.post("", response_model=Prompt)
def create_prompt(payload: PromptCreate) -> Prompt:
    return get_store().create_prompt(payload)
