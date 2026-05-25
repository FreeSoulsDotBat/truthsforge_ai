import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
    software_choice: overrides.software_choice ?? "blender",
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
    rollback_marker: overrides.rollback_marker ?? null,
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

describe("ModelingEditCard — rollback (T3.6)", () => {
  it("shows the undo button for a completed edit with a rollback marker", () => {
    render(
      <ModelingEditCard
        plan={plan({ software_choice: "fusion", rollback_marker: 5 } as Partial<ModelingPlan>)}
        onRollback={vi.fn()}
      />
    );
    expect(screen.getByTestId("modeling-edit-rollback")).toBeTruthy();
    expect(screen.getByText(/Desfazer última edição/i)).toBeTruthy();
  });

  it("hides the undo button when there is no rollback marker", () => {
    render(<ModelingEditCard plan={plan()} onRollback={vi.fn()} />);
    expect(screen.queryByTestId("modeling-edit-rollback")).toBeNull();
  });

  it("hides the undo button when no onRollback handler is provided", () => {
    render(<ModelingEditCard plan={plan({ rollback_marker: 5 } as Partial<ModelingPlan>)} />);
    expect(screen.queryByTestId("modeling-edit-rollback")).toBeNull();
  });

  it("calls onRollback with the plan id and shows 'desfeita' after success", async () => {
    const onRollback = vi.fn().mockResolvedValue(true);
    render(<ModelingEditCard plan={plan({ rollback_marker: 5 } as Partial<ModelingPlan>)} onRollback={onRollback} />);

    fireEvent.click(screen.getByTestId("modeling-edit-rollback"));

    expect(onRollback).toHaveBeenCalledWith("m3d_plan_edit");
    expect(await screen.findByTestId("modeling-edit-rolled-back")).toBeTruthy();
    expect(screen.queryByTestId("modeling-edit-rollback")).toBeNull();
  });

  it("keeps the button when rollback fails (resolves false)", async () => {
    const onRollback = vi.fn().mockResolvedValue(false);
    render(<ModelingEditCard plan={plan({ rollback_marker: 5 } as Partial<ModelingPlan>)} onRollback={onRollback} />);

    fireEvent.click(screen.getByTestId("modeling-edit-rollback"));

    await waitFor(() => expect(onRollback).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("modeling-edit-rolled-back")).toBeNull();
    expect(screen.getByTestId("modeling-edit-rollback")).toBeTruthy();
  });
});
