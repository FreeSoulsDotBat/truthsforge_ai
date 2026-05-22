#!/usr/bin/env bash
# Instancia tasks.md a partir do template numa pasta de spec existente.
# Uso: setup-tasks.sh <feature-dir>   (ex.: 010-chat-orchestration)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

fd="${1:?feature-dir obrigatório}"
dir="$(specs_dir)/${fd}"
[ -d "$dir" ] || { echo "Pasta da spec não existe: specs/${fd}" >&2; exit 1; }
tasks="${dir}/tasks.md"
[ -e "$tasks" ] && { echo "tasks.md já existe em specs/${fd}"; exit 0; }
cp "$(templates_dir)/tasks-template.md" "$tasks"
echo "Criado: specs/${fd}/tasks.md"
