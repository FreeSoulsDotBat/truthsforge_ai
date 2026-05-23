import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Checkbox } from "./Checkbox";
import { EmptyState } from "./EmptyState";
import { FormField } from "./FormField";
import { Input } from "./Input";
import { Radio } from "./Radio";
import { SegmentedControl } from "./SegmentedControl";
import { Skeleton, TypingDots } from "./Skeleton";
import { Slider } from "./Slider";
import { Toast } from "./Toast";
import { Toggle } from "./Toggle";
import { Tooltip } from "./Tooltip";

describe("form controls", () => {
  it("FormField shows error instead of hint", () => {
    const { rerender } = render(
      <FormField label="Nome" hint="ajuda">
        <input aria-label="nome" />
      </FormField>
    );
    expect(screen.getByText("ajuda")).toBeTruthy();
    rerender(
      <FormField label="Nome" hint="ajuda" error="obrigatório">
        <input aria-label="nome" />
      </FormField>
    );
    expect(screen.getByText("obrigatório")).toBeTruthy();
    expect(screen.queryByText("ajuda")).toBeNull();
  });

  it("Input renders prefix/suffix and flags error", () => {
    render(<Input aria-label="key" prefix="sk-" suffix="vault" error />);
    expect(screen.getByText("sk-")).toBeTruthy();
    expect(screen.getByText("vault")).toBeTruthy();
    expect(screen.getByLabelText("key").getAttribute("aria-invalid")).toBe("true");
  });

  it("Toggle exposes switch role and toggles", () => {
    const onChange = vi.fn();
    render(<Toggle checked={false} onChange={onChange} label="ativo" />);
    const sw = screen.getByRole("switch", { name: "ativo" });
    expect(sw.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("Checkbox toggles via the native input", () => {
    const onChange = vi.fn();
    render(<Checkbox checked={false} onChange={onChange} label="lembrar" />);
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("Radio reports its checked state", () => {
    render(<Radio checked name="g" value="a" label="opção a" onChange={() => {}} />);
    expect((screen.getByRole("radio") as HTMLInputElement).checked).toBe(true);
  });

  it("Slider exposes a range input and reports changes", () => {
    const onChange = vi.fn();
    render(<Slider label="temperatura" value={60} onChange={onChange} />);
    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "75" } });
    expect(onChange).toHaveBeenCalledWith(75);
  });

  it("SegmentedControl selects exclusively", () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        label="modo"
        value="chat"
        onChange={onChange}
        options={[
          { value: "chat", label: "Chat" },
          { value: "3d", label: "3D" }
        ]}
      />
    );
    expect(screen.getByRole("radio", { name: "Chat" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "3D" }));
    expect(onChange).toHaveBeenCalledWith("3d");
  });

  it("Tooltip renders trigger and tooltip content", () => {
    render(
      <Tooltip label="Anexar arquivo" hint="⌘U">
        <button type="button">trigger</button>
      </Tooltip>
    );
    expect(screen.getByRole("button", { name: "trigger" })).toBeTruthy();
    expect(screen.getByRole("tooltip").textContent).toContain("Anexar arquivo");
  });

  it("Toast uses tone role and fires its action", () => {
    const onAction = vi.fn();
    render(<Toast tone="err" title="Custo perto do teto" body="80%" action="Revisar" onAction={onAction} />);
    expect(screen.getByRole("alert")).toBeTruthy();
    fireEvent.click(screen.getByText(/Revisar/));
    expect(onAction).toHaveBeenCalledTimes(1);
  });

  it("Skeleton and TypingDots render", () => {
    const { container } = render(<Skeleton className="h-3 w-1/2" />);
    expect(container.firstChild).toBeTruthy();
    render(<TypingDots />);
    expect(screen.getByRole("status", { name: "carregando" })).toBeTruthy();
  });

  it("EmptyState renders title, hint and action", () => {
    render(<EmptyState title="Nenhum projeto" hint="Crie um projeto" action={<button type="button">Novo</button>} />);
    expect(screen.getByText("Nenhum projeto")).toBeTruthy();
    expect(screen.getByText("Crie um projeto")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Novo" })).toBeTruthy();
  });
});
