import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("returns null when open=false", () => {
    const { container } = render(
      <ConfirmDialog open={false} title="hidden" onConfirm={() => {}} onCancel={() => {}} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders with role=alertdialog and labels", () => {
    render(
      <ConfirmDialog
        open
        title="Restaurar snapshot?"
        description="vai sobrescrever o workspace"
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toBeTruthy();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText("Restaurar snapshot?")).toBeTruthy();
    expect(screen.getByText("vai sobrescrever o workspace")).toBeTruthy();
  });

  it("focuses the confirm button on open", () => {
    render(<ConfirmDialog open title="t" confirmLabel="Sim" onConfirm={() => {}} onCancel={() => {}} />);
    expect(document.activeElement?.textContent).toBe("Sim");
  });

  it("calls onConfirm when the confirm button is clicked", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="t" confirmLabel="OK" onConfirm={onConfirm} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("OK"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("calls onCancel when the cancel button is clicked", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="t" cancelLabel="Voltar" onConfirm={onConfirm} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("Voltar"));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("calls onCancel when ESC is pressed", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="t" onConfirm={() => {}} onCancel={onCancel} />);
    fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when the backdrop is clicked", () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="t" onConfirm={() => {}} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole("alertdialog"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables buttons while busy", () => {
    render(
      <ConfirmDialog
        open
        title="t"
        confirmLabel="OK"
        cancelLabel="Voltar"
        busy
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    );
    expect(screen.getByText("OK").hasAttribute("disabled")).toBe(true);
    expect(screen.getByText("Voltar").hasAttribute("disabled")).toBe(true);
  });

  it("Tab cycles focus between confirm and cancel", () => {
    render(
      <ConfirmDialog open title="t" confirmLabel="OK" cancelLabel="Voltar" onConfirm={() => {}} onCancel={() => {}} />
    );
    const dialog = screen.getByRole("alertdialog");
    // Initial focus is on confirm ("OK").
    expect(document.activeElement?.textContent).toBe("OK");
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement?.textContent).toBe("Voltar");
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement?.textContent).toBe("OK");
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement?.textContent).toBe("Voltar");
  });

  it("renders custom children instead of description", () => {
    render(
      <ConfirmDialog open title="t" description="ignored" onConfirm={() => {}} onCancel={() => {}}>
        <span data-testid="custom">conteúdo custom</span>
      </ConfirmDialog>
    );
    expect(screen.getByTestId("custom").textContent).toBe("conteúdo custom");
    expect(screen.queryByText("ignored")).toBeNull();
  });
});
