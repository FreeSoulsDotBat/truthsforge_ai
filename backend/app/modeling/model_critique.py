"""F8 Sub 3 — Auto-crítica estruturada a partir do histórico (ADR-023).

Camada de domínio **pura**: dado o que era ESPERADO (``IntentSpec``) + o histórico
de mudanças (Sub 2) + o estado atual (``ModelState``), produz um ``ModelVerdict``
classificando cada achado em FALTOU/DEMAIS/ERRADO/CERTO, carimbado por FONTE
(``deterministic`` vs ``semantic``). Toda checagem geométrica (contagem de
corpos, corpo órfão/duplicado, interferência por bbox, op declarada-sem-efeito)
é 100% código que MEDE — só o julgamento de FORMA/função fica no LLM.

**INVARIANTE: REPORTA. Nunca auto-executa correção.** O loop de hoje (juiz de
visão) replanejava sozinho e duplicava corpos / travava deletes; este avaliador
só devolve o veredito — o corretor decide, com 1 tentativa guardada.
"""

from __future__ import annotations

from app.core.contracts import (
    Finding,
    IntentSpec,
    ModelState,
    ModelStateBody,
    ModelVerdict,
    OperationHistory,
)

__all__ = ["build_model_verdict", "render_verdict_block"]

_OVERLAP_EPS = 1e-3  # mm — sobreposição de bbox abaixo disto = contato, não interferência


def _bodies_by_ref(state: ModelState | None) -> dict[str, ModelStateBody]:
    out: dict[str, ModelStateBody] = {}
    for b in state.bodies if state else []:
        if b.stable_id:
            out[b.stable_id] = b
        if b.name:
            out.setdefault(b.name, b)
    return out


def _check_body_count(intent: IntentSpec, state: ModelState | None) -> list[Finding]:
    if intent.expected_body_count is None:
        return []
    actual = len(state.bodies) if state else 0
    exp = intent.expected_body_count
    if actual == exp:
        return [
            Finding(
                kind="correct",
                source="deterministic",
                severity="info",
                check_id="body_count",
                detail=f"{actual} corpo(s), como esperado.",
                expected=exp,
                measured=actual,
            )
        ]
    if actual > exp:
        return [
            Finding(
                kind="excess",
                source="deterministic",
                severity="error",
                check_id="body_count",
                detail=f"{actual} corpos, esperava {exp} — {actual - exp} a mais (órfão?).",
                expected=exp,
                measured=actual,
            )
        ]
    return [
        Finding(
            kind="missing",
            source="deterministic",
            severity="error",
            check_id="body_count",
            detail=f"{actual} corpos, esperava {exp} — faltou {exp - actual}.",
            expected=exp,
            measured=actual,
        )
    ]


def _check_orphan_bodies(intent: IntentSpec, state: ModelState | None) -> list[Finding]:
    expected_names = {str(b.get("name")) for b in intent.expected_bodies if b.get("name")}
    if not expected_names:
        return []
    out: list[Finding] = []
    for b in state.bodies if state else []:
        if b.name and b.name not in expected_names:
            out.append(
                Finding(
                    kind="excess",
                    source="deterministic",
                    severity="warn",
                    check_id="orphan_body",
                    entity_ref=b.stable_id or b.name,
                    detail=f"corpo '{b.name}' não estava previsto (órfão).",
                    measured=b.name,
                )
            )
    return out


def _bbox_overlap_volume(a: ModelStateBody, b: ModelStateBody) -> float:
    if not (a.bbox_min_mm and a.bbox_max_mm and b.bbox_min_mm and b.bbox_max_mm):
        return 0.0
    vol = 1.0
    for i in range(3):
        lo = max(a.bbox_min_mm[i], b.bbox_min_mm[i])
        hi = min(a.bbox_max_mm[i], b.bbox_max_mm[i])
        overlap = hi - lo
        if overlap <= _OVERLAP_EPS:
            return 0.0
        vol *= overlap
    return vol


def _check_interference(intent: IntentSpec, state: ModelState | None) -> list[Finding]:
    by = _bodies_by_ref(state)
    out: list[Finding] = []
    for group in intent.disjoint_groups:
        bodies = [by[r] for r in group if r in by]
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                ov = _bbox_overlap_volume(bodies[i], bodies[j])
                if ov > 0:
                    out.append(
                        Finding(
                            kind="wrong",
                            source="deterministic",
                            severity="error",
                            check_id="interference",
                            detail=(
                                f"'{bodies[i].name}' e '{bodies[j].name}' se sobrepõem "
                                f"(~{ov:.1f} mm³ de bbox) mas deviam ser disjuntos."
                            ),
                            measured=round(ov, 2),
                        )
                    )
    return out


def _check_op_no_effect(history: OperationHistory | None) -> list[Finding]:
    out: list[Finding] = []
    for rec in history.records if history else []:
        cat = (rec.tool_category or "").lower()
        if cat == "read_only":
            continue
        empty = not (rec.created or rec.modified or rec.consumed or rec.deleted or rec.uncertain)
        # Só acusa quando houve captura antes E depois (senão não dá p/ afirmar).
        if empty and rec.captured_before and rec.captured_after:
            out.append(
                Finding(
                    kind="missing",
                    source="deterministic",
                    severity="warn",
                    check_id="op_no_effect",
                    entity_ref=rec.step_id,
                    detail=f"passo {rec.seq} ({rec.tool_name}) não teve efeito mensurável.",
                )
            )
    return out


def build_model_verdict(
    intent: IntentSpec,
    history: OperationHistory | None,
    state: ModelState | None,
) -> ModelVerdict:
    """Avalia o estado contra a intenção + histórico → veredito estruturado.
    SÓ REPORTA (não corrige)."""

    findings: list[Finding] = []
    findings += _check_body_count(intent, state)
    findings += _check_orphan_bodies(intent, state)
    findings += _check_interference(intent, state)
    findings += _check_op_no_effect(history)

    if any(f.severity == "critical" for f in findings):
        overall = "broken"
    elif any(f.kind in ("excess", "wrong") for f in findings):
        overall = "diverged"
    elif any(f.kind == "missing" for f in findings):
        overall = "incomplete"
    else:
        overall = "ok"

    # Determinístico-completo quando NÃO há julgamento semântico pendente: aí o
    # LLM nem precisa ser chamado (a geometria contou toda a história).
    deterministic_complete = intent.acceptance_text is None

    counts: dict[str, int] = {}
    for f in findings:
        counts[f.kind] = counts.get(f.kind, 0) + 1
    detail = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    summary = overall + (f": {detail}" if detail else "")

    return ModelVerdict(
        overall=overall,
        findings=findings,
        summary=summary,
        deterministic_complete=deterministic_complete,
    )


_KIND_LABEL = {
    "missing": "FALTOU",
    "excess": "DEMAIS",
    "wrong": "ERRADO",
    "correct": "OK",
}


def render_verdict_block(verdict: ModelVerdict | None) -> str:
    """Renderiza o ``ModelVerdict`` como bloco ``<auto-critica>`` p/ o contexto do
    planner/corretor no PRÓXIMO bloco. Feedback estruturado e legível — só
    reporta (o corretor decide). Vazio quando não há veredito ou achados."""

    if verdict is None or not verdict.findings:
        return ""
    lines = [f"<auto-critica overall={verdict.overall}>"]
    if verdict.summary:
        lines.append(f"- resumo: {verdict.summary}")
    for f in verdict.findings:
        label = _KIND_LABEL.get(f.kind, f.kind.upper())
        ref = f" [{f.entity_ref}]" if f.entity_ref else ""
        src = "" if f.source == "deterministic" else f" ({f.source})"
        lines.append(f"- {label}{src} {f.check_id}{ref}: {f.detail}")
    if verdict.overall != "ok":
        lines.append(
            "- AÇÃO: corrija o que está FALTOU/DEMAIS/ERRADO sem recriar corpos já "
            "existentes (referencie por nome/role); não duplique."
        )
    lines.append("</auto-critica>")
    return "\n".join(lines)
