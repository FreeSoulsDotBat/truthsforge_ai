import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar, type AppSidebarProps } from "./AppSidebar";
import type { ChatSession, CostUsage } from "../types/api";

function makeSession(id: string, title: string): ChatSession {
  return { id, title } as ChatSession;
}

function makeProps(overrides: Partial<AppSidebarProps> = {}): AppSidebarProps {
  return {
    mobileMenuOpen: false,
    onCloseMobile: vi.fn(),
    onNewChat: vi.fn(),
    isCreatingNewChat: false,
    activeView: "chat",
    onSelectView: vi.fn(),
    sessionsCount: 0,
    promptsCount: 0,
    projects: [],
    folders: [],
    explorerSessions: [],
    historySessions: [],
    activeSessionId: null,
    projectExplorerCollapsed: false,
    projectExplorerExpanded: {},
    onToggleProjectExplorerCollapsed: vi.fn(),
    onToggleProjectExplorerExpanded: vi.fn(),
    historyCollapsed: false,
    deletingSessionId: null,
    historyDisabled: false,
    onToggleHistoryCollapsed: vi.fn(),
    onSelectSession: vi.fn(),
    onCreateChat: vi.fn(),
    onCreateFolder: vi.fn(),
    onDeleteFolder: vi.fn(),
    onMoveSession: vi.fn(),
    onDeleteSession: vi.fn(),
    online: true,
    agentModelLabel: "gpt-4o",
    costUsage: null,
    onOpenSettings: vi.fn(),
    ...overrides
  };
}

const costUsage: CostUsage = {
  month: "2026-05",
  monthly_budget_brl: 200,
  estimated_spend_brl: 12.84,
  remaining_budget_brl: 187.16,
  warn_threshold_percent: 80,
  block_at_budget: false,
  request_count: 3,
  tokens_in: 100,
  tokens_out: 200
};

describe("AppSidebar (v4 reskin)", () => {
  it("renders the forge brandmark wordmark", () => {
    render(<AppSidebar {...makeProps()} />);
    expect(screen.getByText(/Truth/)).toBeTruthy();
    expect(screen.getByText("Forge")).toBeTruthy();
  });

  it("uses the v4 copy for the new-chat button and nav", () => {
    render(<AppSidebar {...makeProps()} />);
    expect(screen.getByRole("button", { name: "Nova conversa" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Conversa" })).toBeTruthy();
  });

  it("marks the active view via aria-current", () => {
    render(<AppSidebar {...makeProps({ activeView: "agents" })} />);
    expect(screen.getByRole("button", { name: "Agentes" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "Conversa" }).getAttribute("aria-current")).toBeNull();
  });

  it("fires onNewChat when the new-chat button is clicked", () => {
    const onNewChat = vi.fn();
    render(<AppSidebar {...makeProps({ onNewChat })} />);
    fireEvent.click(screen.getByRole("button", { name: "Nova conversa" }));
    expect(onNewChat).toHaveBeenCalledTimes(1);
  });

  it("renders metric tiles for chats and prompts", () => {
    render(<AppSidebar {...makeProps({ sessionsCount: 12, promptsCount: 4 })} />);
    expect(screen.getByLabelText("Chats: 12")).toBeTruthy();
    expect(screen.getByLabelText("Prompts: 4")).toBeTruthy();
  });

  it("filters conversations through the search field", () => {
    render(
      <AppSidebar
        {...makeProps({
          historySessions: [makeSession("a", "Pipeline RAG no Postgres"), makeSession("b", "Backup do Notion")]
        })}
      />
    );
    fireEvent.change(screen.getByLabelText("Buscar conversas"), { target: { value: "rag" } });
    expect(screen.getByText("Pipeline RAG no Postgres")).toBeTruthy();
    expect(screen.queryByText("Backup do Notion")).toBeNull();
  });

  it("focuses the search field on Ctrl+K", () => {
    render(<AppSidebar {...makeProps()} />);
    const input = screen.getByLabelText("Buscar conversas");
    expect(document.activeElement).not.toBe(input);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(document.activeElement).toBe(input);
  });

  it("shows the JUDITE online status with the active model", () => {
    render(<AppSidebar {...makeProps({ online: true, agentModelLabel: "gpt-4o" })} />);
    expect(screen.getByText("online · gpt-4o")).toBeTruthy();
  });

  it("shows offline status when disconnected", () => {
    render(<AppSidebar {...makeProps({ online: false })} />);
    expect(screen.getByText("offline")).toBeTruthy();
  });

  it("renders the cost meter from real usage data", () => {
    render(<AppSidebar {...makeProps({ costUsage })} />);
    expect(screen.getByText("custo · 2026-05")).toBeTruthy();
    expect(screen.getByText("R$ 12,84 / 200")).toBeTruthy();
  });

  it("fires onOpenSettings from the footer gear", () => {
    const onOpenSettings = vi.fn();
    render(<AppSidebar {...makeProps({ onOpenSettings })} />);
    fireEvent.click(screen.getByRole("button", { name: "Configurações" }));
    expect(onOpenSettings).toHaveBeenCalledTimes(1);
  });
});
