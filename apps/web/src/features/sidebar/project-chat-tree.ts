import type { ChatSession, ProjectFolder } from "../../types/api";

export type ProjectChatTreeNode = {
  folder: ProjectFolder;
  children: ProjectChatTreeNode[];
  chats: ChatSession[];
};

export type ProjectChatTree = {
  roots: ProjectChatTreeNode[];
  rootChats: ChatSession[];
};

function sortFolders(a: ProjectFolder, b: ProjectFolder): number {
  if (a.depth !== b.depth) return a.depth - b.depth;
  return a.name.localeCompare(b.name, "pt-BR", { sensitivity: "base" });
}

function sortChats(a: ChatSession, b: ChatSession): number {
  return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
}

export function buildProjectChatTree(
  projectId: string,
  folders: ProjectFolder[],
  sessions: ChatSession[]
): ProjectChatTree {
  const projectFolders = folders.filter((folder) => folder.project_id === projectId).sort(sortFolders);
  const projectSessions = sessions.filter((session) => session.project_id === projectId);

  const nodes = new Map<string, ProjectChatTreeNode>();
  for (const folder of projectFolders) {
    nodes.set(folder.id, { folder, children: [], chats: [] });
  }

  const roots: ProjectChatTreeNode[] = [];
  for (const node of nodes.values()) {
    if (node.folder.parent_id && nodes.has(node.folder.parent_id)) {
      nodes.get(node.folder.parent_id)?.children.push(node);
    } else {
      roots.push(node);
    }
  }

  for (const session of projectSessions) {
    if (session.folder_id && nodes.has(session.folder_id)) {
      nodes.get(session.folder_id)?.chats.push(session);
      continue;
    }
    roots.push({
      folder: {
        id: `virtual-root-${session.id}`,
        project_id: session.project_id,
        name: "",
        depth: 0,
        path: "",
        parent_id: null,
        created_at: session.created_at,
        updated_at: session.updated_at
      },
      children: [],
      chats: [session]
    });
  }

  const normalizeNode = (node: ProjectChatTreeNode): ProjectChatTreeNode => ({
    ...node,
    children: node.children.map(normalizeNode).sort((left, right) => sortFolders(left.folder, right.folder)),
    chats: [...node.chats].sort(sortChats)
  });

  const normalizedRoots = roots
    .map(normalizeNode)
    .filter((node) => node.folder.name)
    .sort((left, right) => sortFolders(left.folder, right.folder));

  const rootChats = projectSessions.filter((session) => !session.folder_id).sort(sortChats);
  return { roots: normalizedRoots, rootChats };
}
