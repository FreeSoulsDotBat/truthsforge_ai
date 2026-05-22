import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FilterPillRow } from "./FilterPillRow";
import { IndexingStatusBadge } from "./IndexingStatusBadge";
import { MetricTile } from "./MetricTile";
import { SearchField } from "./SearchField";
import { WarningBanner } from "./WarningBanner";

describe("molecules", () => {
  it("SearchField submits the current value", () => {
    const onSubmit = vi.fn();
    render(<SearchField value="contexto" onSubmit={onSubmit} />);
    fireEvent.submit(screen.getByRole("search"));
    expect(onSubmit).toHaveBeenCalledWith("contexto");
  });

  it("WarningBanner uses status/alert role by tone and shows title + body", () => {
    const { rerender } = render(
      <WarningBanner tone="ember" title="2 etapas high-risk" body="Aprovar autoriza todas." />
    );
    expect(screen.getByRole("status")).toBeTruthy();
    expect(screen.getByText("2 etapas high-risk")).toBeTruthy();
    expect(screen.getByText("Aprovar autoriza todas.")).toBeTruthy();
    rerender(<WarningBanner tone="err" title="Erro de configuração" />);
    expect(screen.getByRole("alert")).toBeTruthy();
  });

  it("FilterPillRow toggles a value and reflects aria-pressed", () => {
    const onChange = vi.fn();
    render(
      <FilterPillRow
        label="níveis"
        options={[
          { value: "info", label: "info" },
          { value: "warn", label: "warn" }
        ]}
        selected={new Set(["info"])}
        onChange={onChange}
      />
    );
    expect(screen.getByRole("button", { name: "info" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "warn" }).getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "warn" }));
    const next = onChange.mock.calls[0][0] as Set<string>;
    expect(next.has("info")).toBe(true);
    expect(next.has("warn")).toBe(true);
  });

  it("IndexingStatusBadge switches copy by backlog", () => {
    const { rerender } = render(<IndexingStatusBadge count={3} />);
    expect(screen.getByText("3 arquivos na fila")).toBeTruthy();
    rerender(<IndexingStatusBadge count={0} />);
    expect(screen.getByText("tudo indexado")).toBeTruthy();
  });

  it("MetricTile renders label, value and an accessible label", () => {
    const { container } = render(<MetricTile label="chats" value={247} />);
    expect(container.textContent).toContain("chats");
    expect(container.textContent).toContain("247");
    expect(container.querySelector('[aria-label="chats: 247"]')).toBeTruthy();
  });
});
