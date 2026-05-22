#!/usr/bin/env bash
# Verifica se a casca do Spec Kit está presente antes de specify/plan/tasks.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$DIR/common.sh"

ok=1
check() { if [ -e "$2" ]; then echo "[ok]    $1"; else echo "[falta] $1"; ok=0; fi; }
check ".specify/memory/constitution.md" "$(constitution_path)"
check ".specify/templates"              "$(templates_dir)"
check "specs/"                          "$(specs_dir)"
[ "$ok" -eq 1 ] || { echo "Pré-requisitos do Spec Kit ausentes."; exit 1; }
echo "Pré-requisitos do Spec Kit OK."
