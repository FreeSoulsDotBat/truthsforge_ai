"""F8 Sub 3.2 — Derivação do ``IntentSpec`` a partir do plano (ADR-023).

Camada de domínio **pura**: lê os steps declarados de um ``ModelingPlan`` e deriva
o "esperado" (``IntentSpec``) contra o qual a auto-crítica (Sub 3.1) compara o
estado real. NÃO mede o B-Rep — só interpreta a INTENÇÃO declarada nos steps.

**Invariante "NUNCA chuta":** uma asserção geométrica (contagem de corpos, corpos
órfãos, grupos disjuntos) só é emitida quando o plano é totalmente *contabilizável*
— um build one-shot (``kind=primary`` sem ``parent_plan_id``) cujas operações de
corpo são todas reconhecidas. Caso contrário, devolve apenas a camada semântica
(``acceptance_text``): preferimos o avaliador MUDO a um falso-positivo.

Por que o guard de ``primary`` one-shot: um plano de EDIÇÃO (bloco) só declara os
steps daquele bloco, mas o estado final tem TAMBÉM os corpos pré-existentes — uma
contagem/órfão derivada do bloco isolado acusaria os corpos antigos errado. O
veredito geométrico cross-bloco é trabalho de nível-de-turno (débito honesto;
ver módulo de wiring); aqui ficamos no que é provadamente seguro.
"""

from __future__ import annotations

from app.core.contracts import IntentSpec, ModelingPlan, ModelingPlanKind

__all__ = ["intent_from_plan"]


# Tools que criam EXATAMENTE 1 corpo nomeado (o nome vem do arg ``name``).
_NAMED_PRIMITIVE = frozenset(
    {
        "fusion.add_box",
        "fusion.add_cylinder",
        "fusion.add_sphere",
        "fusion.add_cone",
        "blender.create_mesh_primitive",
    }
)
# Tools que criam corpo a partir de profile — +1 SÓ quando ``operation`` cria
# corpo novo; nome é auto (imprevisível) ⇒ derruba o orphan/disjoint.
_PROFILE_CREATE = frozenset(
    {
        "fusion.extrude_profile",
        "fusion.revolve_profile",
        "fusion.loft_profiles",
        "fusion.sweep_profile",
        "fusion.thicken_surface",
        "fusion.create_surface_patch",
    }
)
_NEW_BODY_OPS = frozenset({"new_body", "new", "newbody", "new_component", "newcomponent"})
_EXISTING_BODY_OPS = frozenset({"join", "cut", "intersect"})
# Divide 1 corpo em 2 (+1 net, peça nova auto-nomeada).
_SPLIT = frozenset({"fusion.split_body"})
# +N desconhecido / surface ops que turvam a contagem ⇒ contagem não-contável.
_UNCOUNTABLE = frozenset(
    {
        "fusion.pattern_rectangular",
        "fusion.pattern_circular",
        "fusion.mirror_feature",
        "fusion.stitch_surfaces",
        "fusion.unstitch_surface",
        "fusion.trim_surface",
        "fusion.extend_surface",
        "fusion.offset_surface",
        "fusion.knuckle_hinge",
        "fusion.metric_screw",
    }
)
_CONSUME = frozenset({"fusion.combine_bodies", "blender.apply_boolean"})
_DELETE = frozenset({"fusion.delete_body"})
# Posicionamento declarativo: resolvido em runtime (pode fundir-DENTRO ⇒ -1 ou
# só juntar ⇒ 0). Net desconhecido ⇒ contagem não-contável. Uma JUNTA também
# invalida a hipótese de disjunção (encaixe coaxial sobrepõe bbox por projeto).
_DECLARATIVE = frozenset(
    {
        "fusion.place_body",
        "fusion.align_axis",
        "fusion.distribute_along",
        "fusion.relate_bodies",
    }
)


def _clean_name(value: object) -> str | None:
    """Extrai o nome de corpo legível de um arg, removendo wrapper ``@body('X')``/
    ``@('X')``/``@X`` e aspas. ``None`` quando não é string utilizável."""

    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.startswith("@"):
        inner = s[1:]
        if "(" in inner:
            inner = inner[inner.index("(") + 1 :]
        inner = inner.strip().rstrip(")").strip().strip("'\"")
        s = inner
    return s or None


def _as_ref_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [n for n in (_clean_name(v) for v in value) if n]
    n = _clean_name(value)
    return [n] if n else []


def _acceptance_text(plan: ModelingPlan) -> str | None:
    parts = [
        sg.acceptance.strip() for sg in plan.sub_goals if sg.acceptance and sg.acceptance.strip()
    ]
    return " | ".join(parts) if parts else None


def intent_from_plan(plan: ModelingPlan) -> IntentSpec:
    """Deriva o ``IntentSpec`` (esperado) dos steps declarados do plano.

    Camada semântica (``acceptance_text``) sempre que houver sub-goals com
    critério. Camada geométrica (contagem/órfão/disjunto) só para build one-shot
    totalmente contabilizável — senão fica ``None``/vazia (avaliador mudo, nunca
    chuta)."""

    acceptance = _acceptance_text(plan)

    # Guard: asserções geométricas só em build one-shot. Plano de edição (bloco)
    # não conhece os corpos pré-existentes ⇒ contagem/órfão seriam falso-positivo.
    one_shot = plan.kind == ModelingPlanKind.primary and not plan.parent_plan_id
    if not one_shot:
        return IntentSpec(acceptance_text=acceptance)

    live: set[str] = set()  # corpos nomeados vivos, simulando o plano por NOME
    count = 0  # net de corpos (de um design VAZIO)
    count_known = True  # vira False em criação/consumo não contabilizável
    names_known = True  # vira False quando surge corpo de nome imprevisível
    joints_present = False  # qualquer junta/placement → disjunção indeterminável

    for step in sorted(plan.steps, key=lambda s: s.seq):
        tool = step.tool_name
        args = step.input_json or {}

        if tool in _NAMED_PRIMITIVE:
            count += 1
            nm = _clean_name(args.get("name"))
            if nm:
                live.add(nm)
            else:
                names_known = False  # primitiva sem nome → nome auto
        elif tool in _PROFILE_CREATE:
            op = str(args.get("operation") or "new_body").lower()
            if op in _NEW_BODY_OPS:
                count += 1
            elif op in _EXISTING_BODY_OPS:
                pass  # opera sobre corpo existente: net 0
            else:
                count_known = False
            names_known = False  # corpo (se houver) tem nome auto
        elif tool in _SPLIT:
            count += 1
            names_known = False
        elif tool in _UNCOUNTABLE:
            count_known = False
            names_known = False
        elif tool in _CONSUME:
            tools_refs = _as_ref_list(
                args.get("tool_refs") or args.get("tools") or args.get("tool_bodies")
            )
            if tools_refs:
                count -= len(tools_refs)
                for r in tools_refs:
                    live.discard(r)
            else:
                count_known = False
            result_nm = _clean_name(args.get("result_name") or args.get("output_name"))
            if result_nm:
                target_nm = _clean_name(
                    args.get("target_ref")
                    or args.get("target")
                    or args.get("target_body")
                    or args.get("target_name")
                )
                if target_nm:
                    live.discard(target_nm)
                live.add(result_nm)
        elif tool in _DELETE:
            count -= 1
            nm = _clean_name(
                args.get("body_name")
                or args.get("body")
                or args.get("body_ref")
                or args.get("target")
                or args.get("name")
            )
            if nm:
                live.discard(nm)
        elif tool in _DECLARATIVE:
            count_known = False  # fuse-DENTRO (-1) ou joint (0): runtime decide
            joints_present = True  # encaixe coaxial sobrepõe bbox → sem disjunção
            if tool == "fusion.distribute_along":
                names_known = False  # cria N corpos auto-nomeados
            # place_body/align_axis não introduzem corpo de nome imprevisível:
            # names_known permanece (o "moving" já existe; um fuse só remove um
            # nome de `live`, seguro p/ órfão). MAS a junta torna a disjunção
            # indeterminável (coaxial sobrepõe; flush encosta) → não emitimos
            # disjoint_groups (avaliador MUDO > falso-positivo de interferência).
        else:
            # read_only / sketch / export / feature neutra conhecida → net 0.
            # Tool desconhecida (fora do registro) → defensivo: não contabiliza.
            from app.modeling.tool_registry import is_known

            if not is_known(tool):
                count_known = False
                names_known = False

    expected_count = count if (count_known and count >= 0) else None
    expected_bodies = [{"name": n} for n in sorted(live)] if names_known else []
    disjoint = (
        [sorted(live)] if (names_known and not joints_present and len(live) >= 2) else []
    )

    return IntentSpec(
        expected_body_count=expected_count,
        expected_bodies=expected_bodies,
        disjoint_groups=disjoint,
        acceptance_text=acceptance,
    )
