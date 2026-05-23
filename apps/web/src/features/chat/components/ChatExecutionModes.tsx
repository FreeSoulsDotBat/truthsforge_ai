import { Activity, Check } from "lucide-react";
import type { ReactNode } from "react";

import { useAppStore } from "../../../app/store";
import { PanelTitle } from "../../../components/app-panels";
import { Mono } from "../../../components/ui/Mono";
import { cn } from "../../../lib/utils";

function ModeRow({
  label,
  hint,
  active,
  disabled = false,
  onToggle
}: {
  label: string;
  hint?: ReactNode;
  active: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={active}
      disabled={disabled}
      onClick={onToggle}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-sm px-2.5 py-2 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        active ? "bg-forge-panel" : "hover:bg-forge-hover"
      )}
    >
      <span
        className={cn(
          "flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[4px] border",
          active ? "border-forge-amber bg-forge-amber text-forge-amber-ink" : "border-forge-line"
        )}
      >
        {active && <Check size={9} strokeWidth={3} />}
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn("block text-[12.5px]", active ? "text-forge-text" : "text-forge-text-soft")}>{label}</span>
        {hint && (
          <Mono size={9.5} className="mt-0.5 block text-forge-faint">
            {hint}
          </Mono>
        )}
      </span>
    </button>
  );
}

/**
 * Painel "Modo de execução" (frame panel.jsx): expõe os modos de execução do chat
 * — os mesmos do menu do composer (ExecutionMenu), via o mesmo `useAppStore`, então
 * os dois ficam sempre em sincronia. MCP 3D fica fora (é gatilhado por diálogo no App).
 *
 * `onDisableModeling3d` espelha o efeito colateral do `ExecutionMenu`: ligar pesquisa,
 * imagem ou multiagente desliga o MCP 3D do próximo chat (a não ser que a sessão ativa
 * já seja 3D). O estado/guarda vive no App.tsx (`nextChatIs3D` + `activeSessionIsModeling3D`),
 * que não são alcançáveis pelo store, então o App injeta o callback.
 */
export function ChatExecutionModes({
  reasoningSummaryUnavailable,
  onDisableModeling3d
}: {
  reasoningSummaryUnavailable: boolean;
  onDisableModeling3d: () => void;
}) {
  const reasoningOverride = useAppStore((state) => state.reasoningOverride);
  const setReasoningOverride = useAppStore((state) => state.setReasoningOverride);
  const reasoningSummary = useAppStore((state) => state.reasoningSummary);
  const setReasoningSummary = useAppStore((state) => state.setReasoningSummary);
  const deepResearch = useAppStore((state) => state.deepResearch);
  const setDeepResearch = useAppStore((state) => state.setDeepResearch);
  const responseMode = useAppStore((state) => state.responseMode);
  const setResponseMode = useAppStore((state) => state.setResponseMode);
  const multiAgentMode = useAppStore((state) => state.multiAgentMode);
  const setMultiAgentMode = useAppStore((state) => state.setMultiAgentMode);
  const imageMode = responseMode === "image";

  const toggleReasoningLong = () => setReasoningOverride((current) => (current === "long" ? "default" : "long"));
  const toggleReasoningSummary = () => setReasoningSummary((current) => !current);
  const toggleDeepResearch = () => {
    setDeepResearch((current) => !current);
    setResponseMode("text");
    setReasoningSummary(false);
    onDisableModeling3d();
  };
  const toggleImage = () => {
    setResponseMode((current) => (current === "image" ? "text" : "image"));
    setDeepResearch(false);
    setReasoningSummary(false);
    onDisableModeling3d();
  };
  const toggleMultiAgent = () => {
    setMultiAgentMode((current) => !current);
    onDisableModeling3d();
  };

  return (
    <div>
      <PanelTitle icon={<Activity size={18} />} title="Modo de execução" />
      <div className="mt-2 flex flex-col gap-0.5">
        <ModeRow
          label="Raciocínio longo"
          hint="mais cuidado antes de responder"
          active={reasoningOverride === "long"}
          onToggle={toggleReasoningLong}
        />
        <ModeRow
          label="Resumo oficial"
          hint={reasoningSummaryUnavailable ? "só texto · modelo OpenAI" : "reasoning.summary=auto"}
          active={reasoningSummary}
          disabled={reasoningSummaryUnavailable}
          onToggle={toggleReasoningSummary}
        />
        <ModeRow
          label="Pesquisa OpenAI"
          hint="2-8 min · múltiplas chamadas"
          active={deepResearch}
          onToggle={toggleDeepResearch}
        />
        <ModeRow label="Imagem" hint="geração de imagem" active={imageMode} onToggle={toggleImage} />
        <ModeRow label="Multiagente" hint="JUDITE + apoios" active={multiAgentMode} onToggle={toggleMultiAgent} />
      </div>
    </div>
  );
}
