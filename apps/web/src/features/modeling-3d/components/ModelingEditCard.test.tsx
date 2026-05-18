import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ModelingPlan, ModelingPlanStep, ModelingPlanStatus } from "../types";
import { ModelingEditCard } from "./ModelingEditCard";

function step(overrides: Partial<ModelingPlanStep> = {}): ModelingPlanStep {
  return {
    id: overrides.id ?? "step",
    seq: overrides.seq ?? 1,
    title: overrides.title ?? "Aplicar bevel",
    software: overrides.software ?? "blender",
    tool_name: overrides.tool_name ?? "blender.apply_bevel",
    risk_level: overrides.risk_level ?? "low",
    approval_required: overrides.approval_required ?? false,
    status: overrides.status ?? "completed",
    input_json: {},
    output_json: {},
    error: null,
    approved_at: null,
    completed_at: null
  };
}

function plan(overrides: Partial<ModelingPlan> = {}): ModelingPlan {
  return {
    id: "m3d_plan_edit",
    project_id: null,
    conversation_id: "chat_1",
    prompt: overrides.prompt ?? "Aumentar parede para 6mm",
    mode: "safe_auto",
    software_choice: "blender",
    confidence: 0.7,
    approval_required: false,
    status: (overrides.status ?? "completed") as ModelingPlanStatus,
    rationale: overrides.rationale ?? "Edição simples no modelo existente.",
    assumptions: [],
    risks: [],
    knowledge_base_ids: [],
    steps: overrides.steps ?? [step()],
    planner_source: "heuristic",
    fallback_reason: null,
    kind: "edit",
    parent_plan_id: overrides.parent_plan_id ?? "m3d_plan_primary",
    created_at: new Date(0).toISOString(),
    updated_at: new Date(0).toISOString()
  };
}

describe("ModelingEditCard", () => {
  it("renders an 'edição executada' header with the edit badge", () => {
    render(<ModelingEditCard plan={plan()} />);
    expect(screen.getByText(/Edição executada/i)).toBeTruthy();
    expect(screen.getByText("edição")).toBeTruthy();
    expect(screen.getByText(/Edição simples/i)).toBeTruthy();
  });

  it("counts executed and failed steps", () => {
    render(
      <ModelingEditCard
        plan={plan({
          steps: [
            step({ status: "completed" }),
            step({ status: "completed", seq: 2, tool_name: "blender.export_stl" }),
            step({ status: "failed", seq: 3, tool_name: "blender.assign_material" })
          ]
        })}
      />
    );
    expect(screen.getByText(/2 etapa\(s\) executada/i)).toBeTruthy();
    expect(screen.getByText(/1 com falha/i)).toBeTruthy();
  });

  it("falls back to a default summary when the plan has no rationale/prompt", () => {
    render(<ModelingEditCard plan={plan({ rationale: "", prompt: "" } as Partial<ModelingPlan>)} />);
    expect(screen.getByText(/Edição executada no modelo 3D/i)).toBeTruthy();
  });

  it("never exposes approval buttons (mini-plans are auto-approved)", () => {
    render(<ModelingEditCard plan={plan()} />);
    expect(screen.queryByText(/Aprovar/i)).toBeNull();
    expect(screen.queryByText(/Rejeitar/i)).toBeNull();
  });
});
