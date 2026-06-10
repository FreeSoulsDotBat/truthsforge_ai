import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  ModelingPlan,
  ModelingPlanStep,
  ModelingPlanStatus,
  ModelingRiskLevel,
  ModelingStepStatus
} from "../types";
import { ModelingPlanCard } from "./ModelingPlanCard";

function step(overrides: Partial<ModelingPlanStep> = {}): ModelingPlanStep {
  return {
    id: overrides.id ?? `step_${Math.random().toString(36).slice(2, 8)}`,
    seq: overrides.seq ?? 1,
    title: overrides.title ?? "Criar primitivo",
    software: overrides.software ?? "blender",
    tool_name: overrides.tool_name ?? "blender.create_mesh_primitive",
    risk_level: (overrides.risk_level ?? "low") as ModelingRiskLevel,
    approval_required: overrides.approval_required ?? false,
    status: (overrides.status ?? "pending") as ModelingStepStatus,
    input_json: overrides.input_json ?? {},
    output_json: overrides.output_json ?? {},
    error: overrides.error ?? null,
    approved_at: overrides.approved_at ?? null,
    completed_at: overrides.completed_at ?? null
  };
}

function plan(overrides: Partial<ModelingPlan> = {}): ModelingPlan {
  return {
    id: overrides.id ?? "m3d_plan_1",
    project_id: overrides.project_id ?? null,
    conversation_id: overrides.conversation_id ?? "chat_1",
    prompt: overrides.prompt ?? "Suporte para fone com base 80x40mm",
    mode: overrides.mode ?? "safe_auto",
    software_choice: overrides.software_choice ?? "blender",
    confidence: overrides.confidence ?? 0.8,
    approval_required: overrides.approval_required ?? false,
    status: (overrides.status ?? "waiting_approval") as ModelingPlanStatus,
    rationale: overrides.rationale ?? "Plano gerado para um suporte simples.",
    assumptions: overrides.assumptions ?? [],
    risks: overrides.risks ?? [],
    knowledge_base_ids: overrides.knowledge_base_ids ?? [],
    steps: overrides.steps ?? [step()],
    planner_source: overrides.planner_source ?? "heuristic",
    fallback_reason: overrides.fallback_reason ?? null,
    kind: overrides.kind ?? "primary",
    parent_plan_id: overrides.parent_plan_id ?? null,
    created_at: overrides.created_at ?? new Date(0).toISOString(),
    updated_at: overrides.updated_at ?? new Date(0).toISOString()
  };
}

describe("ModelingPlanCard", () => {
  it("renders summary, software badge, and step list", () => {
    render(<ModelingPlanCard plan={plan()} />);
    expect(screen.getByText(/Plano 3D MCP/)).toBeTruthy();
    expect(screen.getByText(/Plano gerado para um suporte simples/i)).toBeTruthy();
    expect(screen.getByText("blender")).toBeTruthy();
    expect(screen.getByText(/Criar primitivo/)).toBeTruthy();
  });

  it("falls back to the original prompt when rationale is empty", () => {
    render(<ModelingPlanCard plan={plan({ rationale: "" })} />);
    expect(screen.getByText(/Suporte para fone com base 80x40mm/)).toBeTruthy();
  });

  it("shows the high-risk banner when any step is high or marked approval_required", () => {
    render(
      <ModelingPlanCard
        plan={plan({
          steps: [step({ tool_name: "blender.apply_boolean", risk_level: "high", approval_required: true })]
        })}
      />
    );
    expect(screen.getByText(/etapa\(s\) high-risk/i)).toBeTruthy();
    expect(screen.getByText(/aprovar autoriza todas/i)).toBeTruthy();
  });

  it("does NOT show the high-risk banner when every step is low/medium and no approval flag is set", () => {
    render(<ModelingPlanCard plan={plan()} />);
    expect(screen.queryByText(/etapa\(s\) high-risk/i)).toBeNull();
  });

  it("calls onApprove when the user clicks Aprovar", async () => {
    const onApprove = vi.fn();
    render(<ModelingPlanCard plan={plan()} onApprove={onApprove} />);
    fireEvent.click(screen.getByTestId("modeling-plan-approve"));
    expect(onApprove).toHaveBeenCalledTimes(1);
  });

  it("requires a reason and calls onReject only after the user confirms", async () => {
    const onReject = vi.fn();
    render(<ModelingPlanCard plan={plan()} onReject={onReject} />);
    fireEvent.click(screen.getByTestId("modeling-plan-reject-toggle"));
    const confirm = screen.getByTestId("modeling-plan-reject-confirm") as HTMLButtonElement;
    // Empty reason keeps the confirm button disabled.
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByTestId("modeling-plan-reject-reason"), {
      target: { value: "Dimensões erradas, prefiro outro caminho." }
    });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    expect(onReject).toHaveBeenCalledWith("Dimensões erradas, prefiro outro caminho.");
  });

  it("hides approval buttons once the plan is approved/running/completed", () => {
    render(<ModelingPlanCard plan={plan({ status: "completed" })} onApprove={vi.fn()} />);
    expect(screen.queryByTestId("modeling-plan-approve")).toBeNull();
  });

  it("shows the executing block when plan is running", () => {
    render(<ModelingPlanCard plan={plan({ status: "running" })} />);
    expect(screen.getByText(/Execução em andamento/i)).toBeTruthy();
  });

  it("shows the completed block when plan is completed", () => {
    render(<ModelingPlanCard plan={plan({ status: "completed" })} />);
    expect(screen.getByText(/Plano executado/i)).toBeTruthy();
  });

  it("exposes Retry and Revise buttons when execution failed", () => {
    const onRetry = vi.fn();
    const onRevise = vi.fn();
    render(<ModelingPlanCard plan={plan({ status: "failed" })} onRetry={onRetry} onRevise={onRevise} />);
    fireEvent.click(screen.getByTestId("modeling-plan-retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId("modeling-plan-revise"));
    expect(onRevise).toHaveBeenCalledTimes(1);
  });

  it("C: surfaces which step failed and why on a failed plan", () => {
    render(
      <ModelingPlanCard
        plan={plan({
          status: "failed",
          steps: [
            step({ seq: 1, tool_name: "fusion.add_box", status: "completed" }),
            step({
              seq: 9,
              tool_name: "fusion.distribute_along",
              status: "failed",
              error: "role 'rear_top' ambíguo em 'BoxOuter'"
            })
          ]
        })}
      />
    );
    const detail = screen.getByTestId("modeling-plan-failed-detail");
    expect(detail.textContent).toContain("Passo 9");
    expect(detail.textContent).toContain("fusion.distribute_along");
    expect(detail.textContent).toContain("rear_top");
  });

  it("disables approve/reject while busy", () => {
    render(<ModelingPlanCard plan={plan()} onApprove={vi.fn()} onReject={vi.fn()} isBusy />);
    expect((screen.getByTestId("modeling-plan-approve") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId("modeling-plan-reject-toggle") as HTMLButtonElement).disabled).toBe(true);
  });

  it("renders the 'edição' badge for edit-kind plans", () => {
    render(<ModelingPlanCard plan={plan({ kind: "edit" })} />);
    expect(screen.getByText("edição")).toBeTruthy();
  });

  it("P4: edits a step and calls onEditPlan with the updated steps", () => {
    const onEditPlan = vi.fn();
    render(
      <ModelingPlanCard
        plan={plan({ steps: [step({ title: "Criar cubo", input_json: { primitive: "cube" } })] })}
        onEditPlan={onEditPlan}
      />
    );
    fireEvent.click(screen.getByTestId("modeling-plan-edit-toggle"));
    expect(screen.getByTestId("modeling-plan-editor")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Título da etapa 1"), {
      target: { value: "Criar cubo grande" }
    });
    fireEvent.click(screen.getByTestId("modeling-plan-edit-save"));
    expect(onEditPlan).toHaveBeenCalledTimes(1);
    const payload = onEditPlan.mock.calls[0][0];
    expect(payload.steps[0].title).toBe("Criar cubo grande");
    expect(payload.steps[0].tool_name).toBe("blender.create_mesh_primitive");
    expect(payload.steps[0].input_json).toEqual({ primitive: "cube" });
  });

  it("P4: blocks save and shows an error when the JSON args are invalid", () => {
    const onEditPlan = vi.fn();
    render(<ModelingPlanCard plan={plan()} onEditPlan={onEditPlan} />);
    fireEvent.click(screen.getByTestId("modeling-plan-edit-toggle"));
    fireEvent.change(screen.getByLabelText("Argumentos JSON da etapa 1"), {
      target: { value: "{ not valid json" }
    });
    fireEvent.click(screen.getByTestId("modeling-plan-edit-save"));
    expect(onEditPlan).not.toHaveBeenCalled();
    expect(screen.getByTestId("modeling-plan-edit-error")).toBeTruthy();
  });
});
