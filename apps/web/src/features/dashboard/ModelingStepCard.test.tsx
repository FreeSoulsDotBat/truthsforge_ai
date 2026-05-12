import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ModelingPlanStep } from "../../types/api";
import { ModelingStepCard } from "./dashboard-sections";

function buildStep(overrides: Partial<ModelingPlanStep> = {}): ModelingPlanStep {
  return {
    id: "step_abc",
    seq: 2,
    title: "Criar primitivo",
    software: "blender",
    tool_name: "blender.create_mesh_primitive",
    risk_level: "medium",
    approval_required: true,
    status: "waiting_approval",
    input_json: {},
    output_json: {},
    error: null,
    approved_at: null,
    completed_at: null,
    ...overrides
  };
}

describe("ModelingStepCard", () => {
  it("renders title, tool_name, risk and status badges", () => {
    render(<ModelingStepCard step={buildStep()} isBusy={false} onDecide={() => {}} />);
    expect(screen.getByText("2. Criar primitivo")).toBeTruthy();
    expect(screen.getByText("blender.create_mesh_primitive")).toBeTruthy();
    expect(screen.getByText("medium")).toBeTruthy();
    expect(screen.getByText("aprovação")).toBeTruthy();
    expect(screen.getByText("waiting_approval")).toBeTruthy();
  });

  it("shows the approve/reject buttons only when waiting_approval", () => {
    const { rerender } = render(<ModelingStepCard step={buildStep()} isBusy={false} onDecide={() => {}} />);
    expect(screen.queryByText("Aprovar etapa")).toBeTruthy();
    expect(screen.queryByText("Rejeitar etapa")).toBeTruthy();

    rerender(
      <ModelingStepCard
        step={buildStep({ status: "completed", approval_required: true })}
        isBusy={false}
        onDecide={() => {}}
      />
    );
    expect(screen.queryByText("Aprovar etapa")).toBeNull();
    expect(screen.queryByText("Rejeitar etapa")).toBeNull();
  });

  it("hides the action buttons when the step is auto (approval_required=false)", () => {
    render(
      <ModelingStepCard
        step={buildStep({ approval_required: false, status: "waiting_approval" })}
        isBusy={false}
        onDecide={() => {}}
      />
    );
    expect(screen.queryByText("Aprovar etapa")).toBeNull();
    expect(screen.queryByText("Rejeitar etapa")).toBeNull();
    expect(screen.getByText("auto")).toBeTruthy();
  });

  it("calls onDecide('approve') when the user clicks Aprovar etapa", () => {
    const onDecide = vi.fn();
    render(<ModelingStepCard step={buildStep()} isBusy={false} onDecide={onDecide} />);
    fireEvent.click(screen.getByText("Aprovar etapa"));
    expect(onDecide).toHaveBeenCalledTimes(1);
    expect(onDecide).toHaveBeenCalledWith("approve");
  });

  it("calls onDecide('reject') when the user clicks Rejeitar etapa", () => {
    const onDecide = vi.fn();
    render(<ModelingStepCard step={buildStep()} isBusy={false} onDecide={onDecide} />);
    fireEvent.click(screen.getByText("Rejeitar etapa"));
    expect(onDecide).toHaveBeenCalledTimes(1);
    expect(onDecide).toHaveBeenCalledWith("reject");
  });

  it("disables buttons when isBusy is true", () => {
    render(<ModelingStepCard step={buildStep()} isBusy={true} onDecide={() => {}} />);
    expect(screen.getByText("Aprovar etapa").hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("Rejeitar etapa").hasAttribute("disabled")).toBe(true);
  });

  it("renders output_json.message when present", () => {
    render(
      <ModelingStepCard
        step={buildStep({
          status: "completed",
          output_json: { message: "primitivo criado com 8000 mm³" }
        })}
        isBusy={false}
        onDecide={() => {}}
      />
    );
    expect(screen.getByText("primitivo criado com 8000 mm³")).toBeTruthy();
  });

  it("renders the error message in red when the step errored out", () => {
    render(
      <ModelingStepCard
        step={buildStep({ status: "failed", error: "Blender executable missing." })}
        isBusy={false}
        onDecide={() => {}}
      />
    );
    const errorNode = screen.getByText("Blender executable missing.");
    expect(errorNode).toBeTruthy();
    // The error paragraph carries the forge-red text utility.
    expect(errorNode.className).toContain("text-forge-red");
  });
});
