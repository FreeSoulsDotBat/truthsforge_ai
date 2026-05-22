import { Search } from "lucide-react";
import type { FormEvent } from "react";

import { cn } from "../../lib/utils";
import { Button } from "./Button";

interface SearchFieldProps {
  value: string;
  onChange?: (value: string) => void;
  /** Disparado no Enter ou no clique do botão. */
  onSubmit?: (query: string) => void;
  placeholder?: string;
  buttonLabel?: string;
  loading?: boolean;
  className?: string;
}

/** Campo de busca: input com ícone + botão de submit. Substitui as buscas avulsas. */
export function SearchField({
  value,
  onChange,
  onSubmit,
  placeholder = "Buscar…",
  buttonLabel = "Buscar",
  loading = false,
  className
}: SearchFieldProps) {
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit?.(value);
  };

  return (
    <form role="search" onSubmit={submit} className={cn("flex gap-2", className)}>
      <div className="flex h-9 flex-1 items-center gap-2 rounded-sm border border-forge-line-soft bg-forge-ink-deep pl-3 pr-2.5">
        <Search size={13} className="shrink-0 text-forge-muted" aria-hidden />
        <input
          type="search"
          value={value}
          placeholder={placeholder}
          aria-label={placeholder}
          onChange={(event) => onChange?.(event.target.value)}
          className="min-w-0 flex-1 bg-transparent text-[13px] text-forge-text outline-none placeholder:text-forge-muted"
        />
      </div>
      <Button type="submit" variant="primary" aria-busy={loading || undefined} disabled={loading}>
        {buttonLabel}
      </Button>
    </form>
  );
}
