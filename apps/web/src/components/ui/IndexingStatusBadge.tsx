import { cn } from "../../lib/utils";
import { Mono } from "./Mono";
import { Pulse, StatusDot } from "./StatusDot";

interface IndexingStatusBadgeProps {
  /** Arquivos na fila de indexação (backlog). 0 = tudo indexado. */
  count: number;
  className?: string;
}

/** Pílula de status da fila de indexação. Pulsa em ember quando há backlog. */
export function IndexingStatusBadge({ count, className }: IndexingStatusBadgeProps) {
  const empty = count === 0;
  const color = empty ? "var(--ok)" : "var(--ember)";
  return (
    <div
      aria-live="polite"
      className={cn("inline-flex items-center gap-[7px] rounded-md border bg-forge-panel px-2.5 py-[5px]", className)}
      style={{ borderColor: `color-mix(in srgb, ${color} 30%, var(--line-soft))` }}
    >
      <span aria-hidden>{empty ? <StatusDot color={color} /> : <Pulse color={color} />}</span>
      <Mono size={10.5} className="font-medium text-forge-text-soft">
        {empty ? "tudo indexado" : `${count} arquivos na fila`}
      </Mono>
    </div>
  );
}
