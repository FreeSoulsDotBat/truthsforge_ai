import { FileText, Plus } from "lucide-react";
import type { MutableRefObject } from "react";

import { ExecutionMenuItem } from "../../../components/app-panels";
import { Button } from "../../../components/ui/Button";

export interface ExecutionMenuProps {
  menuRef: MutableRefObject<HTMLDivElement | null>;
  open: boolean;
  onToggleOpen: () => void;
  modeling3dEnabled: boolean;
  reasoningLong: boolean;
  reasoningSummary: boolean;
  reasoningSummaryUnavailable: boolean;
  deepResearch: boolean;
  imageMode: boolean;
  multiAgentMode: boolean;
  onEnableModeling3d: () => void;
  onToggleReasoningLong: () => void;
  onToggleReasoningSummary: () => void;
  onToggleDeepResearch: () => void;
  onToggleImageMode: () => void;
  onToggleMultiAgent: () => void;
  onEditKnowledgeBases: () => void;
  onAttachFile: () => void;
}

/**
 * Execution-mode dropdown of the chat composer (MCP 3D, reasoning, deep
 * research, image, multiagent, attach). Extracted from App.tsx
 * (architecture-map "monólitos de borda"); presentational, with the multi-setter
 * toggles composed by App.
 */
export function ExecutionMenu({
  menuRef,
  open,
  onToggleOpen,
  modeling3dEnabled,
  reasoningLong,
  reasoningSummary,
  reasoningSummaryUnavailable,
  deepResearch,
  imageMode,
  multiAgentMode,
  onEnableModeling3d,
  onToggleReasoningLong,
  onToggleReasoningSummary,
  onToggleDeepResearch,
  onToggleImageMode,
  onToggleMultiAgent,
  onEditKnowledgeBases,
  onAttachFile
}: ExecutionMenuProps) {
  return (
    <div className="relative" ref={menuRef}>
      <Button className="h-8 w-8 px-0" onClick={onToggleOpen} aria-label="Menu de execução" title="Menu de execução">
        <Plus size={15} />
      </Button>
      {open && (
        <div
          className="scrollbar-slim absolute right-0 z-50 max-h-[55vh] w-72 overflow-y-auto rounded-md border border-forge-line bg-[#111313] p-1 shadow-2xl"
          style={{ top: "auto", bottom: "calc(100% + 4px)" }}
        >
          <ExecutionMenuItem
            label="MCP 3D"
            active={modeling3dEnabled}
            title="Usa o chat para criar plano estruturado Blender/Fusion via MCP."
            onClick={onEnableModeling3d}
          />
          <ExecutionMenuItem label="Raciocínio longo" active={reasoningLong} onClick={onToggleReasoningLong} />
          <ExecutionMenuItem
            label="Resumo oficial"
            active={reasoningSummary}
            disabled={reasoningSummaryUnavailable}
            title={
              reasoningSummaryUnavailable
                ? "Disponível apenas para chat texto com modelo OpenAI."
                : "Solicita reasoning.summary=auto."
            }
            onClick={onToggleReasoningSummary}
          />
          <ExecutionMenuItem label="Pesquisa OpenAI" active={deepResearch} onClick={onToggleDeepResearch} />
          <ExecutionMenuItem label="Imagem" active={imageMode} onClick={onToggleImageMode} />
          <ExecutionMenuItem label="Multiagente" active={multiAgentMode} onClick={onToggleMultiAgent} />
          <button
            type="button"
            className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
            onClick={onEditKnowledgeBases}
          >
            <span>Editar bases de conhecimento atreladas</span>
          </button>
          <div className="mx-1 my-1 border-t border-forge-line" />
          <button
            type="button"
            className="flex h-8 w-full items-center justify-between rounded px-2 text-xs text-forge-muted transition hover:bg-[#1b1f22] hover:text-forge-text"
            onClick={onAttachFile}
          >
            <span className="flex items-center gap-2">
              <FileText size={14} />
              Anexar arquivo
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
