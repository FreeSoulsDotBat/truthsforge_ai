import { describe, expect, it } from "vitest";

import type { ChatMessage, ModelingPlan } from "../../types/api";
import { initialAssistantStatus, withModelingPlan } from "./chat-domain";

function buildMessage(): ChatMessage {
  return {
    id: "msg_1",
    session_id: "session_1",
    role: "assistant",
    content: "",
    metadata: { provider: "dev" },
    created_at: new Date("2026-05-14T00:00:00Z").toISOString()
  };
}

function buildPlan(): ModelingPlan {
  return {
    id: "plan_1",
    project_id: "project_1",
    conversation_id: "session_1",
    prompt: "Crie um suporte 3D",
    mode: "safe_auto",
    software_choice: "blender",
    confidence: 0.82,
    approval_required: false,
    status: "completed",
    rationale: "Plano seguro com etapas auditáveis.",
    assumptions: [],
    risks: [],
    knowledge_base_ids: [],
    steps: [
      {
        id: "step_1",
        seq: 1,
        title: "Criar base",
        software: "blender",
        tool_name: "blender.create_mesh_primitive",
        risk_level: "medium",
        approval_required: false,
        status: "completed",
        input_json: {},
        output_json: {},
        error: null,
        approved_at: null,
        completed_at: null
      }
    ],
    planner_source: "heuristic",
    fallback_reason: null,
    created_at: new Date("2026-05-14T00:00:00Z").toISOString(),
    updated_at: new Date("2026-05-14T00:00:00Z").toISOString()
  };
}

describe("chat-domain modeling 3D helpers", () => {
  it("marks the assistant message as a modeling 3D response with plan metadata", () => {
    const message = withModelingPlan(buildMessage(), buildPlan());

    expect(message.metadata?.provider).toBe("dev");
    expect(message.metadata?.response_mode).toBe("modeling_3d");
    expect(message.metadata?.modeling_plan_id).toBe("plan_1");
    expect(message.metadata?.modeling_plan).toMatchObject({
      id: "plan_1",
      software_choice: "blender",
      status: "completed"
    });
  });

  it("uses a 3D-specific initial runtime status when MCP 3D is enabled", () => {
    const status = initialAssistantStatus({
      reasoningOverride: "default",
      deepResearch: false,
      responseMode: "text",
      multiAgentMode: false,
      reasoningSummary: false,
      modeling3dEnabled: true
    });

    expect(status.stage).toBe("modeling_3d");
    expect(status.label).toContain("3D");
  });
});
