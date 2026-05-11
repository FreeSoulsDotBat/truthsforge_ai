import type { ProjectFolder, ProjectRecord, ProjectUpsert } from "../../types/api";

export function projectDisplayName(project: ProjectRecord): string {
  return project.is_general ? "Geral" : project.name;
}

export function createDefaultProjectDraft(): ProjectUpsert {
  return {
    name: "",
    description: "",
    color: "#f0b84d",
    is_general: false,
    context: {
      scope_mode: "project_only",
      max_documents: 20,
      folder_ids: [],
      document_ids: [],
      knowledge_base_ids: [],
      file_ids: [],
      prompt_ids: []
    }
  };
}

export function sortProjectsForUi(projects: ProjectRecord[]): ProjectRecord[] {
  return [...projects].sort((left, right) => {
    if (left.is_general && !right.is_general) return -1;
    if (!left.is_general && right.is_general) return 1;
    return left.name.localeCompare(right.name, "pt-BR", { sensitivity: "base" });
  });
}

export function sortFoldersForUi(folders: ProjectFolder[]): ProjectFolder[] {
  return [...folders].sort((left, right) => left.path.localeCompare(right.path, "pt-BR", { sensitivity: "base" }));
}
