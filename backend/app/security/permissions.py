from __future__ import annotations

from app.core.contracts import PermissionMode, PermissionPolicy, ToolDefinition


def resolve_permission(policy: PermissionPolicy, tool: ToolDefinition) -> PermissionMode:
    configured = policy.tool_permissions.get(tool.id)
    if configured:
        return configured
    if tool.dangerous or tool.requires_confirmation:
        return policy.dangerous_action_default
    return PermissionMode.allow
