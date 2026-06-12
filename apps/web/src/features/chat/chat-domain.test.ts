import { describe, expect, it } from "vitest";

import type { ChatMessage, ChatSession, ModelingPlan } from "../../types/api";
import {
  chatSessionNeedsTitle,
  initialAssistantStatus,
  isDefaultChatTitle,
  messageMetadata,
  modelingStageForPlanStatus,
  normalizeStreamExecutionModes,
  withModelingPlan
} from "./chat-domain";

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

function buildPlan(overrides: Partial<ModelingPlan> = {}): ModelingPlan {
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
    updated_at: new Date("2026-05-14T00:00:00Z").toISOString(),
    ...overrides
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

  it("preserves the known trace_id when a REST payload arrives without it (RF-024)", () => {
    const withTrace = withModelingPlan(buildMessage(), buildPlan({ trace_id: "tr_sse_1" }));
    const afterRestAction = withModelingPlan(withTrace, buildPlan({ status: "running" }));

    expect(messageMetadata(afterRestAction).modeling_plan?.trace_id).toBe("tr_sse_1");
    expect(messageMetadata(afterRestAction).modeling_plan?.status).toBe("running");
  });

  it("adopts the new trace_id when the payload provides one", () => {
    const withTrace = withModelingPlan(buildMessage(), buildPlan({ trace_id: "tr_old" }));
    const updated = withModelingPlan(withTrace, buildPlan({ trace_id: "tr_new" }));

    expect(messageMetadata(updated).modeling_plan?.trace_id).toBe("tr_new");
  });

  it("does not carry a trace_id over to a different plan", () => {
    const withTrace = withModelingPlan(buildMessage(), buildPlan({ trace_id: "tr_plan_1" }));
    const otherPlan = withModelingPlan(withTrace, buildPlan({ id: "plan_2" }));

    expect(messageMetadata(otherPlan).modeling_plan?.trace_id).toBeUndefined();
    expect(messageMetadata(otherPlan).modeling_plan_id).toBe("plan_2");
  });

  it("maps every plan status to the chat stage shared by SSE and the post-409 reconcile", () => {
    expect(modelingStageForPlanStatus("draft")).toBe("planning");
    expect(modelingStageForPlanStatus("waiting_approval")).toBe("planning");
    expect(modelingStageForPlanStatus("approved")).toBe("executing");
    expect(modelingStageForPlanStatus("running")).toBe("executing");
    expect(modelingStageForPlanStatus("completed")).toBe("editing");
    expect(modelingStageForPlanStatus("failed")).toBe("failed");
    expect(modelingStageForPlanStatus("rejected")).toBe("discovery");
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

  it("normalizes incompatible chat modes when MCP 3D is enabled", () => {
    const modes = normalizeStreamExecutionModes({
      reasoningOverride: "long",
      deepResearch: true,
      responseMode: "image",
      reasoningSummary: true,
      multiAgentMode: true,
      modeling3d: { enabled: true, mode: "safe_auto", software_override: "blender" }
    });

    expect(modes).toMatchObject({
      reasoningOverride: "default",
      deepResearch: false,
      responseMode: "text",
      reasoningSummary: false,
      multiAgentMode: false,
      imageModelEnabled: false,
      modeling3dEnabled: true
    });
  });
});

describe("chat-domain required title helpers", () => {
  function buildSession(title: string): ChatSession {
    return {
      id: "session_1",
      title,
      model_id: null,
      agent_id: null,
      project_id: "project_general",
      folder_id: null,
      context_project_ids: [],
      context_document_ids: [],
      context_knowledge_base_ids: [],
      archived: false,
      is_modeling_3d: false,
      modeling_software_preference: null,
      modeling_stage: null,
      modeling_plan_id: null,
      metadata: {},
      created_at: new Date("2026-05-14T00:00:00Z").toISOString(),
      updated_at: new Date("2026-05-14T00:00:00Z").toISOString(),
      messages: []
    };
  }

  it("treats blank and default chat titles as invalid for the first send", () => {
    expect(isDefaultChatTitle("")).toBe(true);
    expect(isDefaultChatTitle(" Novo chat ")).toBe(true);
    expect(isDefaultChatTitle("New chat")).toBe(true);
    expect(isDefaultChatTitle("Plano de suporte")).toBe(false);
  });

  it("requires a title when no usable session title exists", () => {
    expect(chatSessionNeedsTitle(null)).toBe(true);
    expect(chatSessionNeedsTitle(buildSession("Novo chat"))).toBe(true);
    expect(chatSessionNeedsTitle(buildSession("Briefing do suporte"))).toBe(false);
  });
});
