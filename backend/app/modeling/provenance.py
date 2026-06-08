"""F8 — Proveniência de operações + log de mudanças (ADR-023).

Camada de domínio **pura** (sem ``adsk``): dado o ``ModelState`` ANTES e DEPOIS
de um step, produz um ``ChangeRecord`` determinístico — o que a operação
**CRIOU/MODIFICOU/CONSUMIU/DELETOU** + o delta geométrico (bbox/área/volume/
contagens). Casa entidades pelos handles que JÁ existem (``stable_id`` de corpo,
``entityToken`` de face/aresta) e cruza com a CATEGORIA do tool (additive nunca
deleta) p/ marcar ``uncertain`` em vez de afirmar errado sob edição paramétrica.

A matemática de "o que mudou" sai do LLM e vira código que MEDE o B-Rep. É a
base p/ a auto-crítica (Sub 3) dizer o que faltou/foi demais/errado/certo.
"""

from __future__ import annotations

from typing import Any

from app.core.contracts import (
    ChangeRecord,
    EntityChange,
    EntityRef,
    GeometricDelta,
    ModelingPlan,
    ModelState,
    ModelStateBody,
    OperationHistory,
)

__all__ = [
    "diff_model_state",
    "build_change_record",
    "aggregate_history",
    "history_from_plan",
    "render_history_block",
]

_EPS = 1e-6


# --------------------------------------------------------------------------- #
# Handles / índices                                                           #
# --------------------------------------------------------------------------- #
def _body_handle(b: ModelStateBody) -> str | None:
    return b.stable_id or b.name


def _body_ref(b: ModelStateBody) -> EntityRef:
    return EntityRef(kind="body", handle=_body_handle(b) or "?", name=b.name)


def _index_bodies(state: ModelState | None) -> dict[str, ModelStateBody]:
    out: dict[str, ModelStateBody] = {}
    for b in state.bodies if state else []:
        h = _body_handle(b)
        if h:
            out[h] = b
    return out


# --------------------------------------------------------------------------- #
# Deltas geométricos                                                          #
# --------------------------------------------------------------------------- #
def _num_delta(metric: str, before, after) -> GeometricDelta:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return GeometricDelta(
            metric=metric, before=before, after=after, delta=round(after - before, 6)
        )
    return GeometricDelta(metric=metric, before=before, after=after, delta=None)


def _vec_delta(metric: str, before, after) -> GeometricDelta:
    if (
        isinstance(before, (list, tuple))
        and isinstance(after, (list, tuple))
        and len(before) == len(after)
    ):
        delta = [round(after[i] - before[i], 4) for i in range(len(before))]
        return GeometricDelta(metric=metric, before=list(before), after=list(after), delta=delta)
    return GeometricDelta(metric=metric, before=before, after=after, delta=None)


def _body_deltas(b0: ModelStateBody, b1: ModelStateBody) -> list[GeometricDelta]:
    deltas = [
        _vec_delta("bbox_min_mm", b0.bbox_min_mm, b1.bbox_min_mm),
        _vec_delta("bbox_max_mm", b0.bbox_max_mm, b1.bbox_max_mm),
        _num_delta("surface_area_mm2", b0.surface_area_mm2, b1.surface_area_mm2),
        _num_delta("face_count", b0.face_count, b1.face_count),
        _num_delta("edge_count", b0.edge_count, b1.edge_count),
    ]
    if b0.volume_mm3 is not None or b1.volume_mm3 is not None:
        deltas.append(_num_delta("volume_mm3", b0.volume_mm3, b1.volume_mm3))
    return deltas


def _has_change(deltas: list[GeometricDelta]) -> bool:
    for d in deltas:
        if d.delta is None:
            continue
        if isinstance(d.delta, list):
            if any(abs(x) > _EPS for x in d.delta):
                return True
        elif isinstance(d.delta, (int, float)) and abs(d.delta) > _EPS:
            return True
    return False


# --------------------------------------------------------------------------- #
# Classificação                                                               #
# --------------------------------------------------------------------------- #
def _disappeared_op(category: str | None) -> str:
    """Um corpo/entidade sumiu entre before→after: classifica pela categoria do
    tool. additive/mutative NÃO deveriam sumir corpo → ``uncertain`` (não afirma
    errado sob edição paramétrica / troca de handle)."""

    cat = (category or "").lower()
    if cat == "destructive":
        return "deleted"
    if cat == "high_risk":
        return "consumed"  # boolean (combine) absorveu o corpo
    return "uncertain"


def _face_edge_changes(
    b0: ModelStateBody, b1: ModelStateBody, parent: str | None
) -> list[EntityChange]:
    """Faces/arestas criadas/consumidas DENTRO de um corpo que sobreviveu (ex.:
    pocket/fillet consome faces e cria outras). Token = entityToken estável."""

    out: list[EntityChange] = []
    for kind, c0, c1 in (
        ("face", b0.faces, b1.faces),
        ("edge", b0.edges, b1.edges),
    ):
        t0 = {e.token for e in c0 if e.token}
        t1 = {e.token for e in c1 if e.token}
        for tok in sorted(t1 - t0):
            out.append(
                EntityChange(ref=EntityRef(kind=kind, handle=tok, parent_body=parent), op="created")
            )
        for tok in sorted(t0 - t1):
            # sobreviveu o corpo mas a face/aresta sumiu → consumida por feature.
            out.append(
                EntityChange(
                    ref=EntityRef(kind=kind, handle=tok, parent_body=parent), op="consumed"
                )
            )
    return out


def diff_model_state(
    before: ModelState | None, after: ModelState | None, *, category: str | None = None
) -> list[EntityChange]:
    """Diff puro before→after por set-diff de handles estáveis. ``category`` (str
    de ``ToolCategory``) desambigua o caso de entidade que sumiu."""

    changes: list[EntityChange] = []
    b_before = _index_bodies(before)
    b_after = _index_bodies(after)
    before_h, after_h = set(b_before), set(b_after)

    for h in sorted(after_h - before_h):
        changes.append(EntityChange(ref=_body_ref(b_after[h]), op="created"))
    for h in sorted(before_h - after_h):
        changes.append(EntityChange(ref=_body_ref(b_before[h]), op=_disappeared_op(category)))
    for h in sorted(before_h & after_h):
        b0, b1 = b_before[h], b_after[h]
        deltas = _body_deltas(b0, b1)
        if _has_change(deltas):
            changes.append(EntityChange(ref=_body_ref(b1), op="modified", deltas=deltas))
        changes.extend(_face_edge_changes(b0, b1, _body_handle(b1)))
    return changes


# --------------------------------------------------------------------------- #
# ChangeRecord / histórico                                                    #
# --------------------------------------------------------------------------- #
def build_change_record(
    tool_name: str,
    before: ModelState | None,
    after: ModelState | None,
    *,
    category: str | None = None,
    seq: int | None = None,
    step_id: str | None = None,
) -> ChangeRecord:
    """Monta o ChangeRecord de um step a partir do diff, buscando pelos buckets."""

    rec = ChangeRecord(
        tool_name=tool_name,
        tool_category=category,
        seq=seq,
        step_id=step_id,
        bodies_before=(len(before.bodies) if before else None),
        bodies_after=(len(after.bodies) if after else None),
        captured_before=before is not None,
        captured_after=after is not None,
    )
    bucket = {
        "created": rec.created,
        "modified": rec.modified,
        "consumed": rec.consumed,
        "deleted": rec.deleted,
        "uncertain": rec.uncertain,
    }
    for ch in diff_model_state(before, after, category=category):
        bucket[ch.op].append(ch)
    rec.summary = _summarize(rec)
    return rec


def _summarize(rec: ChangeRecord) -> str:
    parts: list[str] = []
    for label, lst in (
        ("criou", rec.created),
        ("modificou", rec.modified),
        ("consumiu", rec.consumed),
        ("deletou", rec.deleted),
        ("sumiu(incerto)", rec.uncertain),
    ):
        if not lst:
            continue
        by_kind: dict[str, int] = {}
        for ch in lst:
            by_kind[ch.ref.kind] = by_kind.get(ch.ref.kind, 0) + 1
        desc = ", ".join(f"{n} {k}" for k, n in sorted(by_kind.items()))
        parts.append(f"{label} {desc}")
    return "; ".join(parts) if parts else "sem mudança detectada"


def aggregate_history(records: list[ChangeRecord]) -> OperationHistory:
    """Agrega ChangeRecords num histórico + entidades correntes (corpos líquidos:
    criados menos deletados/consumidos)."""

    current: dict[str, EntityRef] = {}
    for rec in records:
        for ch in rec.created:
            if ch.ref.kind == "body":
                current[ch.ref.handle] = ch.ref
        for ch in (*rec.deleted, *rec.consumed):
            if ch.ref.kind == "body":
                current.pop(ch.ref.handle, None)
    return OperationHistory(records=list(records), current_entities=list(current.values()))


def render_history_block(history: OperationHistory) -> str:
    """Renderiza o histórico como bloco ``<historico-operacoes>`` p/ o prompt do
    planner/corretor — entidades por NOME/handle estável + deltas numéricos."""

    if not history.records:
        return ""
    lines = ["<historico-operacoes>"]
    for rec in history.records:
        seq = f"{rec.seq}. " if rec.seq is not None else ""
        cat = f" [{rec.tool_category}]" if rec.tool_category else ""
        lines.append(f"- {seq}{rec.tool_name}{cat}: {rec.summary}")
        for ch in (*rec.created, *rec.modified, *rec.deleted, *rec.consumed, *rec.uncertain):
            ref = ch.ref
            who = ref.name or ref.handle
            extra = ""
            for d in ch.deltas:
                if d.delta and (not isinstance(d.delta, list) or any(d.delta)):
                    extra += f" {d.metric}:{d.before}->{d.after}"
            lines.append(f"    {ch.op} {ref.kind} '{who}'{extra}")
    if history.current_entities:
        names = ", ".join((e.name or e.handle) for e in history.current_entities)
        lines.append(f"- corpos atuais: {names}")
    lines.append("</historico-operacoes>")
    return "\n".join(lines)


def _records_from_step_output(output: Any) -> list[ChangeRecord]:
    """Extrai ChangeRecord(s) de um ``output_json`` de step: o ``_provenance``
    direto (passo simples) ou os de cada sub-resultado de uma expansão F7
    declarativa (``expanded``/``sub_results``/``steps``). Best-effort/tolerante."""

    out: list[ChangeRecord] = []
    if not isinstance(output, dict):
        return out
    prov = output.get("_provenance")
    if isinstance(prov, dict):
        try:
            out.append(ChangeRecord.model_validate(prov))
        except Exception:  # noqa: BLE001 - proveniência malformada é ignorada
            pass
    for key in ("expanded", "sub_results", "steps", "results"):
        nested = output.get(key)
        if isinstance(nested, list):
            for item in nested:
                out.extend(_records_from_step_output(item))
    return out


def history_from_plan(plan: ModelingPlan) -> OperationHistory | None:
    """Reconstrói o ``OperationHistory`` de um plano já executado a partir dos
    ``ChangeRecord`` gravados em ``step.output_json["_provenance"]`` (Sub 2.2).

    ``None`` quando nenhum step carregou proveniência (flag OFF na execução ou
    plano sem passos mutativos) — aí a auto-crítica roda só com o ModelState."""

    records: list[ChangeRecord] = []
    for step in sorted(plan.steps, key=lambda s: s.seq):
        records.extend(_records_from_step_output(step.output_json))
    if not records:
        return None
    return aggregate_history(records)
