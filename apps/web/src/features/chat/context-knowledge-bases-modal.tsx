import { Database, LoaderCircle, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import type { KnowledgeBase, KnowledgeBaseDocument, PlatformFileIndexingStatus, ProjectRecord } from "../../types/api";
import { projectDisplayName } from "../projects/project-domain";

const MAX_SELECTED_BASES = 12;

type ContextKnowledgeBasesModalProps = {
  open: boolean;
  projects: ProjectRecord[];
  knowledgeBases: KnowledgeBase[];
  knowledgeBaseDocuments: KnowledgeBaseDocument[];
  fileIndexingStatus: PlatformFileIndexingStatus | null;
  selectedProjectIds: string[];
  initialSelectedKnowledgeBaseIds: string[];
  onClose: () => void;
  onSave: (knowledgeBaseIds: string[]) => void;
};

export function ContextKnowledgeBasesModal({
  open,
  projects,
  knowledgeBases,
  knowledgeBaseDocuments,
  fileIndexingStatus,
  selectedProjectIds,
  initialSelectedKnowledgeBaseIds,
  onClose,
  onSave
}: ContextKnowledgeBasesModalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>(initialSelectedKnowledgeBaseIds);
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();
  const selectedProjectNames = selectedProjectIds
    .map((projectId) => projects.find((project) => project.id === projectId))
    .filter((project): project is ProjectRecord => Boolean(project))
    .map(projectDisplayName)
    .join(", ");
  const documentCountByBaseId = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of knowledgeBaseDocuments) {
      if (!item.enabled) continue;
      counts.set(item.knowledge_base_id, (counts.get(item.knowledge_base_id) ?? 0) + 1);
    }
    return counts;
  }, [knowledgeBaseDocuments]);
  const filteredBases = knowledgeBases.filter((knowledgeBase) => {
    if (!knowledgeBase.enabled) return false;
    if (!normalizedQuery) return true;
    return [knowledgeBase.name, knowledgeBase.description, knowledgeBase.scope, knowledgeBase.tags.join(" ")]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });

  if (!open) return null;

  function toggleBase(knowledgeBaseId: string) {
    setSelectedIds((current) =>
      current.includes(knowledgeBaseId)
        ? current.filter((item) => item !== knowledgeBaseId)
        : current.length >= MAX_SELECTED_BASES
          ? current
          : [...current, knowledgeBaseId]
    );
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 px-4">
      <div
        className="relative flex max-h-[86vh] w-full max-w-3xl flex-col overflow-hidden rounded-lg border border-forge-line bg-forge-elev"
        style={{ boxShadow: "0 24px 80px -24px var(--amethyst-glow)" }}
      >
        <span
          aria-hidden
          className="absolute bottom-0 left-0 top-0 z-10 w-[3px]"
          style={{ background: "var(--amethyst)", boxShadow: "0 0 12px var(--amethyst-glow)" }}
        />
        <div className="flex items-start justify-between gap-4 border-b border-forge-line-soft px-5 py-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forge-amethyst">Contexto do chat</p>
            <h3 className="mt-1.5 font-display text-[22px] uppercase tracking-[0.01em] text-forge-text">
              Bases de conhecimento atreladas
            </h3>
            <p className="mt-1 text-sm text-forge-muted">
              Projeto ativo: {selectedProjectNames || "Geral"}. Esta seleção é opcional.
            </p>
          </div>
          <Button className="h-9 w-9 px-0" onClick={onClose} aria-label="Fechar modal" title="Fechar modal">
            <X size={17} />
          </Button>
        </div>

        <div className="space-y-3 px-5 py-4">
          <div className="flex items-center gap-2 rounded-md border border-forge-line bg-forge-ink-deep px-3">
            <Search size={15} className="text-forge-muted" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar por nome, escopo ou tag"
              className="h-10 min-w-0 flex-1 bg-transparent text-sm text-forge-text placeholder:text-forge-muted focus:outline-none"
            />
          </div>
          <p className="text-sm text-forge-muted">
            Selecionadas: {selectedIds.length} / {MAX_SELECTED_BASES}
          </p>
        </div>

        <div className="scrollbar-slim min-h-0 flex-1 space-y-2 overflow-y-auto px-5 pb-4">
          {filteredBases.map((knowledgeBase) => {
            const active = selectedIds.includes(knowledgeBase.id);
            const documentCount = documentCountByBaseId.get(knowledgeBase.id) ?? 0;
            return (
              <button
                key={knowledgeBase.id}
                type="button"
                className={[
                  "flex w-full items-start gap-3 rounded-md border p-3 text-left transition",
                  active
                    ? "border-[color-mix(in_srgb,var(--amethyst)_30%,transparent)] bg-[color-mix(in_srgb,var(--amethyst)_8%,transparent)]"
                    : "border-forge-line bg-forge-ink-deep hover:border-forge-amber/40"
                ].join(" ")}
                onClick={() => toggleBase(knowledgeBase.id)}
              >
                <input
                  type="checkbox"
                  checked={active}
                  readOnly
                  className="mt-1"
                  aria-label={`Selecionar ${knowledgeBase.name}`}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="truncate font-semibold">{knowledgeBase.name}</span>
                    <Badge>{documentCount} docs</Badge>
                  </div>
                  <p className="mt-1 line-clamp-2 text-sm text-forge-muted">
                    {knowledgeBase.scope || knowledgeBase.description || "Sem escopo descrito."}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Badge>top {knowledgeBase.max_documents_per_query}</Badge>
                    <Badge>{knowledgeBase.max_chunks_per_document} chunks/doc</Badge>
                    {knowledgeBase.tags.slice(0, 3).map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                </div>
              </button>
            );
          })}
          {!filteredBases.length && (
            <div className="rounded-md border border-forge-line bg-forge-ink-deep p-4 text-sm text-forge-muted">
              <span className="inline-flex items-center gap-2">
                {query ? <Database size={16} /> : <LoaderCircle size={16} className="animate-spin" />}
                {query ? "Nenhuma base encontrada." : "Carregando bases..."}
              </span>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-forge-line-soft px-5 py-4">
          {fileIndexingStatus && fileIndexingStatus.backlog_files > 0 && (
            <div className="mr-auto flex items-center gap-2 rounded-md border border-forge-amber/50 bg-forge-amber/10 px-3 py-2 text-xs text-forge-amber">
              <LoaderCircle size={14} className="animate-spin" />
              {fileIndexingStatus.backlog_files} arquivo(s) ainda em indexação.
            </div>
          )}
          <Button className="h-9" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            className="h-9 border-[color-mix(in_srgb,var(--amethyst)_50%,transparent)] bg-[color-mix(in_srgb,var(--amethyst)_16%,transparent)] text-forge-amethyst"
            onClick={() => onSave(selectedIds.slice(0, MAX_SELECTED_BASES))}
          >
            Editar bases de conhecimento atreladas
          </Button>
        </div>
      </div>
    </div>
  );
}
