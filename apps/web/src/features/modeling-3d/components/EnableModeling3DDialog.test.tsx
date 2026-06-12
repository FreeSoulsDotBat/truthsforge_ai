import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EnableModeling3DDialog } from "./EnableModeling3DDialog";

describe("EnableModeling3DDialog", () => {
  it("returns null when closed", () => {
    const { container } = render(
      <EnableModeling3DDialog
        open={false}
        software="auto"
        onClose={() => {}}
        onConfirm={() => {}}
        onSoftwareChange={() => {}}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("confirms activation with selected options", () => {
    const onConfirm = vi.fn();
    const onSoftwareChange = vi.fn();
    render(
      <EnableModeling3DDialog
        open
        software="auto"
        onClose={() => {}}
        onConfirm={onConfirm}
        onSoftwareChange={onSoftwareChange}
      />
    );

    fireEvent.change(screen.getByLabelText("Software"), { target: { value: "fusion" } });
    fireEvent.click(screen.getByText("Ativar no próximo chat"));

    expect(onSoftwareChange).toHaveBeenCalledWith("fusion");
    // P1: o diálogo descreve o gate de aprovação real (todo plano primário
    // para no card), não o modelo fluido pré-P1.
    expect(screen.getByText(/Modo: plano com aprovação/i)).toBeTruthy();
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
