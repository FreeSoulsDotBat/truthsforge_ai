#!/usr/bin/env bash
# Funções compartilhadas pelos scripts do Spec Kit (Truth's Forge AI).
# Não duplicam scripts/quality.ps1 — apenas localizam paths e numeram features.
set -euo pipefail

repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || { echo "Não é um repositório git." >&2; exit 1; }
}
specs_dir()         { echo "$(repo_root)/specs"; }
templates_dir()     { echo "$(repo_root)/.specify/templates"; }
constitution_path() { echo "$(repo_root)/.specify/memory/constitution.md"; }

# Próximo número de feature: múltiplo de 10 acima do maior NNN- existente
# (specs/_legacy/ é ignorada). Passe um número explícito para forçar (ex.: 005).
next_feature_number() {
  local specs="$1" max=0 n base
  if [ -d "$specs" ]; then
    for d in "$specs"/*/; do
      [ -d "$d" ] || continue
      base="$(basename "$d")"
      [ "$base" = "_legacy" ] && continue
      if [[ "$base" =~ ^([0-9]{3})- ]]; then
        n=$((10#${BASH_REMATCH[1]}))
        [ "$n" -gt "$max" ] && max=$n
      fi
    done
  fi
  printf '%03d' $(( (max / 10) * 10 + 10 ))
}
