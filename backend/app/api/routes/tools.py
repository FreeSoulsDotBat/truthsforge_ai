from fastapi import APIRouter, HTTPException

from app.core.contracts import (
    Agent,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolPermissionDecision,
)
from app.storage.store import get_store
from app.tools.catalog import DEFAULT_TOOLS, tool_by_id
from app.tools.runtime import evaluate_tool_permission, execute_tool_request

router = APIRouter()


def _agent_by_id(agent_id: str | None) -> Agent | None:
    if not agent_id:
        return None
    store = get_store()
    return next((agent for agent in store.list_agents() if agent.id == agent_id), None)


@router.get("", response_model=list[ToolDefinition])
def list_tools() -> list[ToolDefinition]:
    return DEFAULT_TOOLS


@router.get("/{tool_id}/permission", response_model=ToolPermissionDecision)
def get_tool_permission(tool_id: str, agent_id: str | None = None) -> ToolPermissionDecision:
    tool = tool_by_id(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Ferramenta não encontrada.")
    return evaluate_tool_permission(tool, _agent_by_id(agent_id))


# SEGURANÇA (api-rest-005): /execute aciona o runtime de tools (escrita/execução)
# e NÃO tem autenticação — por design local-first (AGENTS.md). PRESSUPOSTO: bind
# loopback-only. Se o backend for exposto além do loopback, esta rota precisa de
# um gate (token local/Origin) antes da exposição. O runtime já aplica a policy
# de aprovação humana (add autoexecuta; alter/delete exigem aprovação).
@router.post("/execute", response_model=ToolExecutionResult)
def execute_tool(payload: ToolExecutionRequest) -> ToolExecutionResult:
    return execute_tool_request(payload, agent=_agent_by_id(payload.agent_id), store=get_store())
