import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelingCapabilities, ProjectRecord } from "../../types/api";
import { api } from "../../lib/api";
import { ModelingDashboard } from "./dashboard-sections";

vi.mock("../../lib/api", () => ({
  api: {
    modelingCapabilities: vi.fn(),
    modelingPlans: vi.fn(),
    startModelingSession: vi.fn()
  }
}));

const emptyCapabilities: ModelingCapabilities = {
  mode: "local_mcp",
  default_execution_mode: "approval_required",
  safety_notes: [],
  adapters: []
};

function buildProject(overrides: Partial<ProjectRecord> = {}): ProjectRecord {
  return {
    id: "project_general",
    name: "Geral",
    description: "Projeto global",
    color: "#f0b84d",
    is_general: true,
    context: {
      scope_mode: "project_only",
      max_documents: 20,
      folder_ids: [],
      document_ids: [],
      knowledge_base_ids: [],
      file_ids: [],
      prompt_ids: []
    },
    created_at: "2026-05-17T00:00:00Z",
    updated_at: "2026-05-17T00:00:00Z",
    ...overrides
  };
}

function renderDashboard(projects: ProjectRecord[]) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ModelingDashboard projects={projects} onOpenChat={() => {}} />
    </QueryClientProvider>
  );
}

describe("ModelingDashboard", () => {
  beforeEach(() => {
    vi.mocked(api.modelingCapabilities).mockResolvedValue(emptyCapabilities);
    vi.mocked(api.modelingPlans).mockResolvedValue([]);
    vi.mocked(api.startModelingSession).mockResolvedValue({
      id: "session_1",
      software: "blender",
      project_id: "project_general",
      status: "mock",
      mcp_server: "blender_mcp",
      metadata: {},
      created_at: "2026-05-17T00:00:00Z",
      updated_at: "2026-05-17T00:00:00Z"
    });
  });

  it("uses the persisted general project instead of a duplicate general-context option", () => {
    renderDashboard([buildProject()]);

    const projectSelect = screen.getByLabelText("Projeto") as HTMLSelectElement;
    expect(projectSelect.value).toBe("project_general");
    expect(screen.getByRole("option", { name: "Geral" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "Contexto geral" })).toBeNull();
  });

  it("starts adapter sessions scoped to the general project by default", async () => {
    renderDashboard([buildProject()]);

    fireEvent.click(screen.getByText("Blender"));

    await waitFor(() => {
      expect(api.startModelingSession).toHaveBeenCalledWith({
        software: "blender",
        project_id: "project_general",
        force_mock: true
      });
    });
  });
});
