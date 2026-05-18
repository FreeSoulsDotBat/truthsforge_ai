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
    mode: "safe_auto",
    software_choice: "fusion",
    confidence: 0.74,
    approval_required: false,
    status: "completed",
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
        approval_required: false,
        status: "completed",
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
    // ``mode`` and the "painel 3D" copy were removed by ADR-013 (Onda 2/3);
    // the v2 card surfaces software, status (label-mapped) and the steps
    // through the shared ModelingPlanCard component.
    render(<MessageBubble message={buildMessage(buildPlan())} platformFilesById={{}} />);

    expect(screen.getByText("Plano 3D MCP")).toBeTruthy();
    expect(screen.getByText("fusion")).toBeTruthy();
    // status label gets localised to pt-BR by the new card.
    expect(screen.getByText("concluído")).toBeTruthy();
    expect(screen.getByText("1. Criar sketch")).toBeTruthy();
    expect(screen.getByText(/fusion.add_rectangle/)).toBeTruthy();
    expect(screen.getByText(/Plano executado/)).toBeTruthy();
  });
});
