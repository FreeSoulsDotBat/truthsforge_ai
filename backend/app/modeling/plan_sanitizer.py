"""Sanitizer determinístico pós-LLM (Frente F6 / ex-Fase 9.2).

Camada **entre o planner e o executor**: remove campos-fantasma e valores de
referência geométrica que os nudges do system prompt não eliminam por completo.

Evidência (gate da Fase 4, Bug J'): mesmo com nudges explícitos, o LLM emitia,
em ~1/4 dos furos, coisas como ``face: "Placa.top_face"`` e
``position_mm: ["Placa.bounding_box.max_x - 20", ...]`` — sintaxes que **nenhum
handler aceita** e que fazem o step cair em fallback errado ou falhar no adapter.

Princípio: **conservador**. Só descarta o que (a) nenhum handler do adapter
aceita e (b) os nudges proíbem explicitamente. Planos válidos passam intactos —
o sanitizer não reescreve geometria nem "adivinha" valores. Cada alteração vira
um ``logger.warning`` (telemetria) e uma :class:`SanitizeAction` (testável).

Não substitui Structured Outputs (9.1, já no planner via ``generate_structured``)
nem o retry agêntico (9.3, no ``agent_loop``); é a malha determinística do meio.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from app.modeling.spatial_ref import strip_at_refs

logger = logging.getLogger(__name__)

# Campos que NENHUM handler do adapter aceita e que os nudges proíbem. Carregam
# referências de face/superfície inventadas (o handler quer ``body``/``body_ref``
# + selector/token, nunca ``face: "<body>.top_face"``).
GHOST_KEYS: frozenset[str] = frozenset(
    {
        "face",
        "target_face",
        "target_body_face",
        "face_ref",
        "surface",
        "surface_ref",
    }
)

# Exceções por tool: chaves que SÃO canônicas para certas tools e portanto NÃO
# devem ser tratadas como fantasma. ``surface``/``surface_ref`` são o seletor de
# corpo primário das tools de superfície da Fase 5 (ver tool_schemas.py); apagá-
# las cegamente quebra fusion.trim_surface / fusion.unstitch_surface no adapter.
GHOST_KEY_EXCEPTIONS: dict[str, frozenset[str]] = {
    "fusion.trim_surface": frozenset({"surface", "surface_ref"}),
    "fusion.unstitch_surface": frozenset({"surface", "surface_ref"}),
}

# Aliases de NOME que carregam um valor válido — remapear (não descartar) para a
# chave canônica quando esta ainda não veio.
ALIAS_REMAP: dict[str, str] = {
    "axis_line": "axis",
}

# Referência geométrica embutida num VALOR string — inválida em QUALQUER campo
# (``position_mm``, ``distance_mm``, expressões). O handler rejeita expressões do
# tipo ``<body>.bounding_box.max_x`` / ``<body>.center`` / ``<body>.top_face``.
_GEOM_REF_RE = re.compile(
    r"\b[A-Za-z_]\w*\.(?:bounding_box|boundingbox|bbox|center|centroid|"
    r"top_face|bottom_face|min_[xyz]|max_[xyz])\b"
)


@dataclass(frozen=True)
class SanitizeAction:
    """Registro de uma alteração feita pelo sanitizer (para telemetria/teste)."""

    kind: str  # "drop_ghost_key" | "drop_geom_ref_value" | "remap_alias"
    field: str
    detail: str


def _value_has_geom_ref(value: Any) -> bool:
    if isinstance(value, str):
        from app.core.config import settings

        if settings.modeling_spatial_resolution_enabled:
            # Flag ON: o resolver resolve @-refs → POUPA-as; só a forma CRUA
            # (Placa.bbox.max_z) cai.
            return bool(_GEOM_REF_RE.search(strip_at_refs(value)))
        # Flag OFF: ninguém resolve @-refs → derruba QUALQUER @-ref pela PRESENÇA
        # (o regex só pega a forma crua <palavra>.<geom>; @token('F').center tem
        # ')' antes do '.center' e escaparia), senão chegaria cru ao adapter →
        # mis-place em (0,0). A forma crua (sem @) também cai.
        if strip_at_refs(value) != value:
            return True
        return bool(_GEOM_REF_RE.search(value))
    if isinstance(value, (list, tuple)):
        return any(_value_has_geom_ref(item) for item in value)
    return False


def sanitize_tool_arguments(tool_name: str, args: Any) -> tuple[Any, list[SanitizeAction]]:
    """Limpa o dict de argumentos de um step. Retorna ``(args_limpos, ações)``.

    Não-dict passa intacto. Conservador por design — ver docstring do módulo.
    """
    if not isinstance(args, dict):
        return args, []

    cleaned = dict(args)
    actions: list[SanitizeAction] = []

    # 1) remap de aliases (preserva o valor na chave canônica).
    for alias, canonical in ALIAS_REMAP.items():
        if alias in cleaned:
            value = cleaned.pop(alias)
            if cleaned.get(canonical) is None:
                cleaned[canonical] = value
                actions.append(
                    SanitizeAction(
                        "remap_alias",
                        alias,
                        f"{tool_name}: '{alias}' remapeado para '{canonical}'",
                    )
                )
            else:
                actions.append(
                    SanitizeAction(
                        "drop_ghost_key",
                        alias,
                        f"{tool_name}: '{alias}' descartado (canônico '{canonical}' já presente)",
                    )
                )

    # 2) campos-fantasma (sem valor aproveitável em nenhum handler), exceto os
    #    que são canônicos para a tool em questão (ver GHOST_KEY_EXCEPTIONS).
    allowed = GHOST_KEY_EXCEPTIONS.get(tool_name, frozenset())
    for key in list(cleaned.keys()):
        if key in GHOST_KEYS and key not in allowed:
            cleaned.pop(key, None)
            actions.append(
                SanitizeAction(
                    "drop_ghost_key",
                    key,
                    f"{tool_name}: campo '{key}' não existe em nenhum handler do adapter",
                )
            )

    # 3) valores com referência geométrica inválida (em qualquer campo restante).
    for key in list(cleaned.keys()):
        if _value_has_geom_ref(cleaned[key]):
            bad = cleaned.pop(key)
            actions.append(
                SanitizeAction(
                    "drop_geom_ref_value",
                    key,
                    f"{tool_name}: valor com referência geométrica inválida "
                    f"em '{key}': {bad!r} (use número cru ou parâmetro)",
                )
            )

    for action in actions:
        logger.warning("plan_sanitizer %s [%s] %s", action.kind, action.field, action.detail)

    return cleaned, actions
