import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAppStore } from "../../../app/store";
import { ChatExecutionModes } from "./ChatExecutionModes";

const noop = () => {};

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
    render(<ChatExecutionModes reasoningSummaryUnavailable={false} onDisableModeling3d={noop} />);
    expect(useAppStore.getState().deepResearch).toBe(false);
    fireEvent.click(screen.getByRole("switch", { name: /Pesquisa OpenAI/ }));
    expect(useAppStore.getState().deepResearch).toBe(true);
  });

  it("disables 'Resumo oficial' when unavailable", () => {
    render(<ChatExecutionModes reasoningSummaryUnavailable={true} onDisableModeling3d={noop} />);
    const toggle = screen.getByRole("switch", { name: /Resumo oficial/ }) as HTMLButtonElement;
    expect(toggle.disabled).toBe(true);
  });

  it("enabling image mode clears deep research", () => {
    useAppStore.setState({ deepResearch: true });
    render(<ChatExecutionModes reasoningSummaryUnavailable={false} onDisableModeling3d={noop} />);
    fireEvent.click(screen.getByRole("switch", { name: /Imagem/ }));
    expect(useAppStore.getState().responseMode).toBe("image");
    expect(useAppStore.getState().deepResearch).toBe(false);
  });

  it("disables modeling3d when toggling deep research, image or multi-agent", () => {
    const onDisableModeling3d = vi.fn();
    render(<ChatExecutionModes reasoningSummaryUnavailable={false} onDisableModeling3d={onDisableModeling3d} />);
    fireEvent.click(screen.getByRole("switch", { name: /Pesquisa OpenAI/ }));
    fireEvent.click(screen.getByRole("switch", { name: /Imagem/ }));
    fireEvent.click(screen.getByRole("switch", { name: /Multiagente/ }));
    expect(onDisableModeling3d).toHaveBeenCalledTimes(3);
  });

  it("does not disable modeling3d for reasoning toggles", () => {
    const onDisableModeling3d = vi.fn();
    render(<ChatExecutionModes reasoningSummaryUnavailable={false} onDisableModeling3d={onDisableModeling3d} />);
    fireEvent.click(screen.getByRole("switch", { name: /Raciocínio longo/ }));
    fireEvent.click(screen.getByRole("switch", { name: /Resumo oficial/ }));
    expect(onDisableModeling3d).not.toHaveBeenCalled();
  });
});
