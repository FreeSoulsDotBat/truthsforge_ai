import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppSidebar, type AppSidebarProps } from "./AppSidebar";

function makeProps(overrides: Partial<AppSidebarProps> = {}): AppSidebarProps {
  return {
    mobileMenuOpen: false,
    onCloseMobile: vi.fn(),
    onNewChat: vi.fn(),
    isCreatingNewChat: false,
    activeView: "chat",
    onSelectView: vi.fn(),
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
    ...overrides
  };
}

describe("AppSidebar (v4 reskin)", () => {
  it("renders the forge brandmark wordmark", () => {
    render(<AppSidebar {...makeProps()} />);
    expect(screen.getByText(/Truth/)).toBeTruthy();
    expect(screen.getByText("Forge")).toBeTruthy();
  });

  it("marks the active view via aria-current", () => {
    render(<AppSidebar {...makeProps({ activeView: "agents" })} />);
    expect(screen.getByRole("button", { name: "Agentes" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "Chat" }).getAttribute("aria-current")).toBeNull();
  });

  it("fires onNewChat when the new-chat button is clicked", () => {
    const onNewChat = vi.fn();
    render(<AppSidebar {...makeProps({ onNewChat })} />);
    fireEvent.click(screen.getByRole("button", { name: "Novo chat" }));
    expect(onNewChat).toHaveBeenCalledTimes(1);
  });

  it("shows JUDITE online status with the active model in the footer", () => {
    render(<AppSidebar {...makeProps({ online: true, agentModelLabel: "gpt-4o" })} />);
    expect(screen.getByText("online · gpt-4o")).toBeTruthy();
  });

  it("shows offline status when disconnected", () => {
    render(<AppSidebar {...makeProps({ online: false })} />);
    expect(screen.getByText("offline")).toBeTruthy();
  });
});
