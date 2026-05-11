from fastapi import APIRouter

from app.core.contracts import Agent, AgentCreate, AgentUpdate
from app.storage.store import get_store

router = APIRouter()


@router.get("", response_model=list[Agent])
def list_agents() -> list[Agent]:
    return get_store().list_agents()


@router.post("", response_model=Agent)
def create_agent(payload: AgentCreate) -> Agent:
    return get_store().create_agent(payload)


@router.put("/{agent_id}", response_model=Agent)
def update_agent(agent_id: str, payload: AgentUpdate) -> Agent:
    return get_store().update_agent(agent_id, payload)
