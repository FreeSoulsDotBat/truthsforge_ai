import type { ModelingSoftware } from "../types";

type Modeling3DSettingsSectionProps = {
  software: ModelingSoftware;
  onSoftwareChange: (value: ModelingSoftware) => void;
};

export function Modeling3DSettingsSection({ software, onSoftwareChange }: Modeling3DSettingsSectionProps) {
  return (
    <div className="rounded-md border border-forge-line bg-[#171716] p-3">
      <div className="space-y-1">
        <p className="text-xs uppercase text-forge-muted">Modelagem 3D</p>
        <h4 className="text-sm font-semibold">Configuração do MCP 3D</h4>
        <p className="text-xs text-forge-muted">
          O chat é a experiência principal de modelagem. Esta seção define o adapter preferido para próximos chats 3D.
        </p>
      </div>
      <div className="mt-3 grid gap-3">
        <label className="grid gap-1 text-xs text-forge-muted">
          Software preferido
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
          Execução: fluida allowlistada. Adições e alterações normais podem autoexecutar; deleções, ações destrutivas e
          high-risk exigem aprovação humana.
        </p>
      </div>
    </div>
  );
}
