import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { CopyableCode } from "./CopyableCode";
import { HelperIcon } from "./HelperIcon";
import { NumberInput } from "./NumberInput";
import { ProgressBar } from "./ProgressBar";
import { RiskPill } from "./RiskPill";
import { Select } from "./Select";
import { Textarea } from "./Textarea";

describe("form atoms", () => {
  it("RiskPill maps level to text + aria-label", () => {
    render(<RiskPill level="high" />);
    const el = screen.getByText("high");
    expect(el.getAttribute("aria-label")).toBe("risco high");
  });

  it("ProgressBar exposes determinate aria values, omits them when indeterminate", () => {
    const { rerender } = render(<ProgressBar value={62} label="Importando" />);
    let bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBe("62");
    rerender(<ProgressBar indeterminate label="Importando" />);
    bar = screen.getByRole("progressbar");
    expect(bar.getAttribute("aria-valuenow")).toBeNull();
  });

  it("ProgressBar clamps out-of-range values", () => {
    render(<ProgressBar value={140} label="x" />);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("100");
  });

  it("HelperIcon announces its tip", () => {
    render(<HelperIcon tip="Aleatoriedade · 0-2" />);
    expect(screen.getByLabelText("Aleatoriedade · 0-2")).toBeTruthy();
  });

  it("Select renders its options", () => {
    render(
      <Select
        aria-label="provider"
        value="anthropic"
        onChange={() => {}}
        options={[
          { value: "openai", label: "OpenAI" },
          { value: "anthropic", label: "Anthropic" }
        ]}
      />
    );
    expect(screen.getByRole("option", { name: "OpenAI" })).toBeTruthy();
    expect((screen.getByLabelText("provider") as HTMLSelectElement).value).toBe("anthropic");
  });

  it("Textarea flags error via aria-invalid", () => {
    render(<Textarea aria-label="t" error value="" onChange={() => {}} />);
    expect(screen.getByLabelText("t").getAttribute("aria-invalid")).toBe("true");
  });

  describe("NumberInput", () => {
    it("commits a parsed number and clears to null", () => {
      const onChange = vi.fn();
      render(<NumberInput aria-label="temp" value={null} onChange={onChange} />);
      const input = screen.getByLabelText("temp");
      fireEvent.change(input, { target: { value: "42" } });
      expect(onChange).toHaveBeenLastCalledWith(42);
      fireEvent.change(input, { target: { value: "" } });
      expect(onChange).toHaveBeenLastCalledWith(null);
    });

    it("keeps an incomplete draft without committing", () => {
      const onChange = vi.fn();
      render(<NumberInput aria-label="temp" value={null} onChange={onChange} />);
      const input = screen.getByLabelText("temp");
      // "-" is a genuinely incomplete draft (in incompleteNumericDrafts) — must not commit.
      fireEvent.change(input, { target: { value: "-" } });
      expect(onChange).not.toHaveBeenCalled();
      expect((input as HTMLInputElement).value).toBe("-");
      fireEvent.change(input, { target: { value: "-5" } });
      expect(onChange).toHaveBeenLastCalledWith(-5);
    });

    it("renders a suffix", () => {
      render(<NumberInput aria-label="t" value={4096} suffix="tok" />);
      expect(screen.getByText("tok")).toBeTruthy();
    });
  });

  it("CopyableCode copies its content on click", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<CopyableCode tip="trace_id">tr_8a4f9c12d</CopyableCode>);
    fireEvent.click(screen.getByRole("button", { name: "Copiar trace_id" }));
    expect(writeText).toHaveBeenCalledWith("tr_8a4f9c12d");
  });

  it("Button keeps the default variant and supports primary", () => {
    const { rerender } = render(<Button>Salvar</Button>);
    expect(screen.getByRole("button", { name: "Salvar" }).className).toContain("bg-[#1a1d20]");
    rerender(<Button variant="primary">Forjar</Button>);
    expect(screen.getByRole("button", { name: "Forjar" }).className).toContain("uppercase");
  });
});
