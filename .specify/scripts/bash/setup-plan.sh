#!/usr/bin/env bash
# Instancia plan.md a partir do template numa pasta de spec existente.
# Uso: setup-plan.sh <feature-dir>   (ex.: 010-chat-orchestration)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

fd="${1:?feature-dir obrigatório}"
dir="$(specs_dir)/${fd}"
[ -d "$dir" ] || { echo "Pasta da spec não existe: specs/${fd}" >&2; exit 1; }
plan="${dir}/plan.md"
[ -e "$plan" ] && { echo "plan.md já existe em specs/${fd}"; exit 0; }
cp "$(templates_dir)/plan-template.md" "$plan"
echo "Criado: specs/${fd}/plan.md"
