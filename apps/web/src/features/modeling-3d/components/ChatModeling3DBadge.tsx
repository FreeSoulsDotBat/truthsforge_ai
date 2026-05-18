import { Box } from "lucide-react";

export function ChatModeling3DBadge({ compact = false }: { compact?: boolean }) {
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-forge-amber/60 bg-[#241d12] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-forge-amber"
      title="Chat de modelagem 3D"
      aria-label="Chat de modelagem 3D"
    >
      <Box size={compact ? 11 : 12} />
      {!compact && "3D"}
    </span>
  );
}
