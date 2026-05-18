import type { ModelingSoftware } from "../types";

type EnableModeling3DDialogProps = {
  open: boolean;
  software: ModelingSoftware;
  onClose: () => void;
  onConfirm: () => void;
  onSoftwareChange: (value: ModelingSoftware) => void;
};

export function EnableModeling3DDialog({
  open,
  software,
  onClose,
  onConfirm,
  onSoftwareChange
}: EnableModeling3DDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-md rounded-lg border border-forge-line bg-[#111312] p-4 shadow-xl">
        <div className="space-y-1">
          <p className="text-xs uppercase text-forge-muted">MCP 3D</p>
          <h3 className="text-lg font-semibold">Ativar modelagem 3D no chat</h3>
          <p className="text-sm text-forge-muted">
            O próximo chat será marcado como 3D e JUDITE executará adições e alterações normais via MCP fluido. Deleções
            e ações destrutivas continuam abrindo aprovação humana.
          </p>
        </div>
        <div className="mt-4 grid gap-3">
          <label className="grid gap-1 text-xs text-forge-muted">
            Software
            <select
              value={software}
              onChange={(event) => onSoftwareChange(event.target.value as ModelingSoftware)}
              className="h-9 rounded-md border border-forge-line bg-[#0e0f0e] px-3 text-sm text-forge-text"
            >
              <option value="auto">Auto</option>
              <option value="blender">Blender</option>
              <option value="fusion">Fusion 360</option>
            </select>
          </label>
          <p className="rounded-md border border-forge-line bg-[#0e0f0e] px-3 py-2 text-xs text-forge-muted">
            Modo: fluido allowlistado. O plano estruturado fica auditável no chat, sem etapa separada de aprovação para
            operações seguras.
          </p>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            className="rounded-md border border-forge-line px-3 py-2 text-sm text-forge-muted hover:text-forge-text"
            onClick={onClose}
          >
            Cancelar
          </button>
          <button
            type="button"
            className="rounded-md border border-forge-amber/60 bg-[#24211b] px-3 py-2 text-sm text-forge-text"
            onClick={onConfirm}
          >
            Ativar no próximo chat
          </button>
        </div>
      </div>
    </div>
  );
}
