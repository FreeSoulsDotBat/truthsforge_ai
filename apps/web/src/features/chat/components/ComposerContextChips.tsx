import { ContextChip } from "../../../components/app-panels";
import { Button } from "../../../components/ui/Button";
import type { ModelConfig } from "../../../types/api";

export interface ComposerContextChipsProps {
  agentName: string;
  projectLabel: string;
  knowledgeBasesLabel: string;
  executionLabel: string;
  deepResearch: boolean;
  deepResearchMaxToolCalls: number;
  onChangeDeepResearchMaxToolCalls: (value: number) => void;
  imageMode: boolean;
  selectedImageModelId: string;
  imageCapableModels: ModelConfig[];
  onSelectImageModel: (id: string | null) => void;
  showDiagnostics: boolean;
  onOpenDiagnostics: () => void;
}

/**
 * Context/execution summary chips above the chat input (agent, project, bases,
 * execution + deep-research call limit, image-model picker and the 3D
 * diagnostics shortcut). Extracted from App.tsx (architecture-map "monólitos de
 * borda"); presentational.
 */
export function ComposerContextChips({
  agentName,
  projectLabel,
  knowledgeBasesLabel,
  executionLabel,
  deepResearch,
  deepResearchMaxToolCalls,
  onChangeDeepResearchMaxToolCalls,
  imageMode,
  selectedImageModelId,
  imageCapableModels,
  onSelectImageModel,
  showDiagnostics,
  onOpenDiagnostics
}: ComposerContextChipsProps) {
  return (
    <div className="flex min-w-0 flex-1 flex-wrap gap-2">
      <ContextChip label="Agente" value={agentName} />
      <ContextChip label="Projeto" value={projectLabel} />
      <ContextChip label="Bases" value={knowledgeBasesLabel} />
      <ContextChip label="Execução" value={executionLabel} />
      {deepResearch && (
        <label className="inline-flex h-8 items-center gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted">
          <span>Chamadas</span>
          <input
            type="number"
            min={1}
            max={100}
            value={deepResearchMaxToolCalls}
            onChange={(event) =>
              onChangeDeepResearchMaxToolCalls(Math.max(1, Math.min(100, Number(event.target.value) || 1)))
            }
            className="h-6 w-14 rounded border border-forge-line bg-[#080908] px-2 text-forge-text"
            aria-label="Limite de chamadas de ferramenta"
            title="Limite de chamadas de ferramenta"
          />
        </label>
      )}
      {imageMode && (
        <label className="inline-flex h-8 items-center gap-2 rounded-md border border-forge-line bg-[#0e0f0e] px-2 text-xs text-forge-muted">
          <span>Modelo imagem</span>
          <select
            value={selectedImageModelId}
            onChange={(event) => onSelectImageModel(event.target.value || null)}
            className="h-6 min-w-44 rounded border border-forge-line bg-[#080908] px-2 text-forge-text"
            aria-label="Modelo de geração de imagem"
            title="Modelo de geração de imagem"
          >
            {!imageCapableModels.length && <option value="">Sem modelos de imagem</option>}
            {imageCapableModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.display_name}
              </option>
            ))}
          </select>
        </label>
      )}
      {showDiagnostics && (
        <Button
          className="h-8 px-2 text-xs"
          onClick={onOpenDiagnostics}
          aria-label="Abrir diagnóstico MCP 3D"
          title="Abrir diagnóstico MCP 3D"
        >
          Diagnóstico 3D
        </Button>
      )}
    </div>
  );
}
