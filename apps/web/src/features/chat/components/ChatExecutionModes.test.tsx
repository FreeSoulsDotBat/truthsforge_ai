import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useAppStore } from "../../../app/store";
import { ChatExecutionModes } from "./ChatExecutionModes";

beforeEach(() => {
  useAppStore.setState({
    reasoningOverride: "default",
    reasoningSummary: false,
    deepResearch: false,
    responseMode: "text",
    multiAgentMode: false
  });
});

describe("ChatExecutionModes", () => {
  it("toggles deep research in the shared store", () => {
    render(<ChatExecutionModes reasoningSummaryUnavailable={false} />);
    expect(useAppStore.getState().deepResearch).toBe(false);
    fireEvent.click(screen.getByRole("switch", { name: /Pesquisa OpenAI/ }));
    expect(useAppStore.getState().deepResearch).toBe(true);
  });

  it("disables 'Resumo oficial' when unavailable", () => {
    render(<ChatExecutionModes reasoningSummaryUnavailable={true} />);
    const toggle = screen.getByRole("switch", { name: /Resumo oficial/ }) as HTMLButtonElement;
    expect(toggle.disabled).toBe(true);
  });

  it("enabling image mode clears deep research", () => {
    useAppStore.setState({ deepResearch: true });
    render(<ChatExecutionModes reasoningSummaryUnavailable={false} />);
    fireEvent.click(screen.getByRole("switch", { name: /Imagem/ }));
    expect(useAppStore.getState().responseMode).toBe("image");
    expect(useAppStore.getState().deepResearch).toBe(false);
  });
});
