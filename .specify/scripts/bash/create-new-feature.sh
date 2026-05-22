#!/usr/bin/env bash
# Cria specs/NNN-<slug>/ a partir do template e um handoff stub.
# Uso: create-new-feature.sh <slug> [number]
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

slug="${1:?slug obrigatório}"
specs="$(specs_dir)"
number="${2:-$(next_feature_number "$specs")}"
dirname="${number}-${slug}"
feature_dir="${specs}/${dirname}"
[ -e "$feature_dir" ] && { echo "Já existe: specs/${dirname}" >&2; exit 1; }

mkdir -p "$feature_dir"
cp "$(templates_dir)/spec-template.md" "$feature_dir/spec.md"
printf '# handoff.md\n\nContinuidade entre agentes (Codex, Claude Code, Devin, humanos) para `%s`.\n\n## Estado atual\n\n- _vazio_\n' "$dirname" > "$feature_dir/handoff.md"

echo "Criado: specs/${dirname}/ (spec.md, handoff.md)"
echo "Edite spec.md, depois rode setup-plan.sh ${dirname}"
