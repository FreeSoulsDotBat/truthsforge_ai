import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ChatMessage, ModelingPlan } from "../types/api";
import { MessageBubble } from "./app-chat";

function buildPlan(): ModelingPlan {
  return {
    id: "plan_chat_1",
    project_id: "project_1",
    conversation_id: "session_1",
    prompt: "Modele uma caixa paramétrica",
    mode: "approval_required",
    software_choice: "fusion",
    confidence: 0.74,
    approval_required: true,
    status: "waiting_approval",
    rationale: "Criar sketch, extrusão e export validável.",
    assumptions: ["Usar unidades em mm"],
    risks: ["Depende do bridge Fusion local"],
    knowledge_base_ids: [],
    steps: [
      {
        id: "step_1",
        seq: 1,
        title: "Criar sketch",
        software: "fusion",
        tool_name: "fusion.add_rectangle",
        risk_level: "medium",
        approval_required: true,
        status: "waiting_approval",
        input_json: {},
        output_json: {},
        error: null,
        approved_at: null,
        completed_at: null
      }
    ],
    planner_source: "llm",
    fallback_reason: null,
    created_at: new Date("2026-05-14T00:00:00Z").toISOString(),
    updated_at: new Date("2026-05-14T00:00:00Z").toISOString()
  };
}

function buildMessage(plan: ModelingPlan): ChatMessage {
  return {
    id: "msg_1",
    session_id: "session_1",
    role: "assistant",
    content: "Criei um plano 3D estruturado.",
    metadata: {
      response_mode: "modeling_3d",
      modeling_plan_id: plan.id,
      modeling_plan: plan
    },
    created_at: new Date("2026-05-14T00:00:00Z").toISOString()
  };
}

describe("MessageBubble modeling 3D", () => {
  it("renders a modeling plan card inside the assistant message", () => {
    render(<MessageBubble message={buildMessage(buildPlan())} platformFilesById={{}} />);

    expect(screen.getByText("Plano 3D MCP")).toBeTruthy();
    expect(screen.getByText("fusion")).toBeTruthy();
    expect(screen.getByText("approval_required")).toBeTruthy();
    expect(screen.getAllByText("waiting_approval")).toHaveLength(2);
    expect(screen.getByText("1. Criar sketch")).toBeTruthy();
    expect(screen.getByText(/fusion.add_rectangle/)).toBeTruthy();
    expect(screen.getByText(/aprovação, execução MCP, snapshots, rollback e printability/)).toBeTruthy();
  });
});
