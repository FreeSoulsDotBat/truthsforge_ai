import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatTitleRequiredDialog } from "./ChatTitleRequiredDialog";

describe("ChatTitleRequiredDialog", () => {
  it("does not render when closed", () => {
    const { container } = render(<ChatTitleRequiredDialog open={false} onConfirm={() => {}} />);

    expect(container.firstChild).toBeNull();
  });

  it("renders an accessible dialog when open", () => {
    render(<ChatTitleRequiredDialog open onConfirm={() => {}} onCancel={() => {}} />);

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByLabelText("Título do chat")).toBeTruthy();
  });

  it("keeps confirm disabled for blank and default titles", () => {
    render(<ChatTitleRequiredDialog open initialTitle="Novo chat" onConfirm={() => {}} />);

    const input = screen.getByLabelText("Título do chat");
    const confirm = screen.getByText("Confirmar") as HTMLButtonElement;

    expect(confirm.disabled).toBe(true);
    fireEvent.change(input, { target: { value: "   " } });
    expect(confirm.disabled).toBe(true);
    fireEvent.change(input, { target: { value: "Briefing 3D" } });
    expect(confirm.disabled).toBe(false);
  });

  it("cancels with Escape", () => {
    const onCancel = vi.fn();
    render(<ChatTitleRequiredDialog open onConfirm={() => {}} onCancel={onCancel} />);

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("confirms with Enter when title is valid", () => {
    const onConfirm = vi.fn();
    render(<ChatTitleRequiredDialog open initialTitle="Suporte headphone" onConfirm={onConfirm} />);

    fireEvent.keyDown(screen.getByLabelText("Título do chat"), { key: "Enter" });

    expect(onConfirm).toHaveBeenCalledWith("Suporte headphone");
  });

  it("disables actions while busy", () => {
    render(<ChatTitleRequiredDialog open initialTitle="Suporte headphone" busy onConfirm={() => {}} />);

    expect((screen.getByText("Confirmar") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText("Cancelar") as HTMLButtonElement).disabled).toBe(true);
  });
});
