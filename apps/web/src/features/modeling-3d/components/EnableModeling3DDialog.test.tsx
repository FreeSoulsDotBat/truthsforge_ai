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
    expect(screen.getByText(/Modo: fluido allowlistado/i)).toBeTruthy();
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
