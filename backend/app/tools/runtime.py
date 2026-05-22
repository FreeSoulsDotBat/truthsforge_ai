from __future__ import annotations

from app.core.contracts import (
    Agent,
    AuditEvent,
    PermissionMode,
    PermissionPolicy,
    ToolDefinition,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolPermissionDecision,
)
from app.security.permissions import resolve_permission
from app.tools.catalog import tool_by_id


def _effective_policy(agent: Agent | None, tool: ToolDefinition) -> PermissionPolicy:
    if agent and agent.permission_policy:
        return agent.permission_policy
    return PermissionPolicy(
        agent_id=agent.id if agent else "global",
        dangerous_action_default=PermissionMode.ask
        if tool.dangerous or tool.requires_confirmation
        else PermissionMode.allow,
    )


def evaluate_tool_permission(
    tool: ToolDefinition, agent: Agent | None = None
) -> ToolPermissionDecision:
    if not tool.enabled:
        return ToolPermissionDecision(
            tool_id=tool.id,
            agent_id=agent.id if agent else None,
            permission=PermissionMode.deny,
            allowed=False,
            requires_approval=False,
            reason="tool_disabled",
        )
    if agent and agent.tools_allowed and tool.id not in agent.tools_allowed:
        return ToolPermissionDecision(
            tool_id=tool.id,
            agent_id=agent.id,
            permission=PermissionMode.deny,
            allowed=False,
            requires_approval=False,
            reason="tool_not_allowed_for_agent",
        )

    permission = resolve_permission(_effective_policy(agent, tool), tool)
    return ToolPermissionDecision(
        tool_id=tool.id,
        agent_id=agent.id if agent else None,
        permission=permission,
        allowed=permission == PermissionMode.allow,
        requires_approval=permission == PermissionMode.ask,
        reason=f"permission_{permission.value}",
    )


def execute_tool_request(
    request: ToolExecutionRequest,
    *,
    agent: Agent | None = None,
    store,
) -> ToolExecutionResult:
    tool = tool_by_id(request.tool_id)
    if tool is None:
        return _record_tool_result(
            store,
            ToolExecutionResult(
                tool_id=request.tool_id,
                agent_id=request.agent_id,
                status="denied",
                permission=PermissionMode.deny,
                message="Ferramenta desconhecida.",
            ),
            request.input,
        )

    decision = evaluate_tool_permission(tool, agent)
    if decision.permission == PermissionMode.deny:
        return _record_tool_result(
            store,
            ToolExecutionResult(
                tool_id=tool.id,
                agent_id=agent.id if agent else request.agent_id,
                status="denied",
                permission=decision.permission,
                message=decision.reason,
            ),
            request.input,
        )
    if decision.requires_approval and not request.approved:
        return _record_tool_result(
            store,
            ToolExecutionResult(
                tool_id=tool.id,
                agent_id=agent.id if agent else request.agent_id,
                status="approval_required",
                permission=decision.permission,
                requires_approval=True,
                message="Aprovação humana necessária antes de executar esta ferramenta.",
            ),
            request.input,
        )

    if tool.id == "rag.search":
        return _record_tool_result(
            store,
            ToolExecutionResult(
                tool_id=tool.id,
                agent_id=agent.id if agent else request.agent_id,
                status="completed",
                permission=decision.permission,
                output={
                    "query": str(request.input.get("query") or "").strip(),
                    "message": "Use /api/documents/search para executar a busca RAG.",
                },
                message="Ferramenta segura validada.",
            ),
            request.input,
        )

    # Safety stub (architecture-map finding "tools de escrita ainda em stub"):
    # only ``rag.search`` (read-only) has a real runtime today. Write/execute
    # tools (e.g. python.run, filesystem.write) intentionally do NOT run yet —
    # AGENTS.md requires them to operate in a per-project isolated sandbox with
    # timeout, size limits, audit and mandatory rollback before any runtime is
    # enabled. Until that lands they are rejected here (AFTER the permission
    # gate above), so an enabled-but-unsandboxed tool can never execute. The
    # rejection is audited via ``_record_tool_result``.
    return _record_tool_result(
        store,
        ToolExecutionResult(
            tool_id=tool.id,
            agent_id=agent.id if agent else request.agent_id,
            status="error",
            permission=decision.permission,
            requires_approval=False,
            message=(
                "Ferramenta de escrita/execução ainda não habilitada: requer "
                "sandbox isolado por projeto (timeout, limite de tamanho, "
                "auditoria e rollback) conforme AGENTS.md. Apenas rag.search "
                "(read-only) está disponível neste runtime."
            ),
        ),
        request.input,
    )


def _record_tool_result(
    store, result: ToolExecutionResult, input_payload: dict[str, object]
) -> ToolExecutionResult:
    if hasattr(store, "add_audit_event"):
        store.add_audit_event(
            AuditEvent(
                event_type="tool.execution",
                metadata={
                    "tool_run_id": result.id,
                    "tool_id": result.tool_id,
                    "agent_id": result.agent_id,
                    "status": result.status,
                    "permission": result.permission,
                    "requires_approval": result.requires_approval,
                    "input_keys": sorted(input_payload.keys()),
                    "message": result.message,
                },
            )
        )
    return result
