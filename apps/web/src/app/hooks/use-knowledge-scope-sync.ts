import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";

import { createDefaultProjectDraft } from "../../features/projects/project-domain";
import type { ProjectFolder, ProjectRecord, ProjectUpsert } from "../../types/api";

export type ProjectsStatus = {
  type: "idle" | "error" | "success";
  message: string;
};

type KnowledgeScopeSyncConfig = {
  projects: ProjectRecord[];
  projectFolders: ProjectFolder[];
  selectedKnowledgeProjectId: string | null;
  selectedKnowledgeFolderId: string | null;
  folderDraftParentId: string | null;
  setSelectedKnowledgeProjectId: Dispatch<SetStateAction<string | null>>;
  setSelectedKnowledgeFolderId: Dispatch<SetStateAction<string | null>>;
  setFolderDraftParentId: Dispatch<SetStateAction<string | null>>;
  setProjectDraft: Dispatch<SetStateAction<ProjectUpsert>>;
  setProjectsStatus: Dispatch<SetStateAction<ProjectsStatus>>;
};

export function useKnowledgeScopeSync({
  projects,
  projectFolders,
  selectedKnowledgeProjectId,
  selectedKnowledgeFolderId,
  folderDraftParentId,
  setSelectedKnowledgeProjectId,
  setSelectedKnowledgeFolderId,
  setFolderDraftParentId,
  setProjectDraft,
  setProjectsStatus
}: KnowledgeScopeSyncConfig): void {
  const generalProject = projects.find((project) => project.is_general) ?? projects[0] ?? null;
  const selectedProject =
    projects.find((project) => project.id === selectedKnowledgeProjectId) ??
    (selectedKnowledgeProjectId ? (generalProject ?? null) : null);
  const selectedProjectSignature = selectedProject ? `${selectedProject.id}:${selectedProject.updated_at}` : "none";

  useEffect(() => {
    const fallbackProjectId = generalProject?.id ?? null;
    const validProjectId =
      selectedKnowledgeProjectId && projects.some((project) => project.id === selectedKnowledgeProjectId)
        ? selectedKnowledgeProjectId
        : fallbackProjectId;

    if (validProjectId !== selectedKnowledgeProjectId) {
      setSelectedKnowledgeProjectId(validProjectId);
      setSelectedKnowledgeFolderId(null);
      return;
    }

    if (selectedKnowledgeFolderId) {
      const folder = projectFolders.find((item) => item.id === selectedKnowledgeFolderId);
      if (!folder || (validProjectId && folder.project_id !== validProjectId)) {
        setSelectedKnowledgeFolderId(null);
      }
    }

    if (folderDraftParentId) {
      const parent = projectFolders.find((item) => item.id === folderDraftParentId);
      if (!parent || (validProjectId && parent.project_id !== validProjectId)) {
        setFolderDraftParentId(null);
      }
    }
  }, [
    folderDraftParentId,
    generalProject?.id,
    projectFolders,
    projects,
    selectedKnowledgeFolderId,
    selectedKnowledgeProjectId,
    setFolderDraftParentId,
    setSelectedKnowledgeFolderId,
    setSelectedKnowledgeProjectId
  ]);

  useEffect(() => {
    if (!selectedProject) {
      setProjectDraft(createDefaultProjectDraft());
      setProjectsStatus({ type: "idle", message: "" });
      return;
    }

    setProjectDraft({
      name: selectedProject.name,
      description: selectedProject.description,
      color: selectedProject.color,
      is_general: selectedProject.is_general,
      context: {
        ...selectedProject.context,
        max_documents: 20
      }
    });
    setProjectsStatus({ type: "idle", message: "" });
  }, [selectedProject, selectedProjectSignature, setProjectDraft, setProjectsStatus]);
}
