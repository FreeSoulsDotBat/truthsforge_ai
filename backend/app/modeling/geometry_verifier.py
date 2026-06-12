"""F8 Sub 4 — Verificador geométrico de relações (ADR-023).

Camada de domínio **pura** (sem ``adsk``): após a execução de uma relação, MEDE o
``ModelState`` e reporta **contato** (as faces encostam?), **interferência** (os
corpos se penetram?) e **DOF** (graus de liberdade esperados pela junta). Produz
um ``GeometricContactReport`` — **só REPORTA**, aposentando o juiz-de-visão como
fonte de verdade geométrica.

O reparo determinístico (``propose_repair``) é só PROPOSTO (re-junta com offset
medido); a aplicação fica atrás do gate P6 (o motor de junta com offset). Nunca
auto-corrige no escuro — espelha o invariante "reporta, não corrige" do Sub 3.
"""

from __future__ import annotations

from app.core.contracts import (
    GeometricContactReport,
    ModelState,
    RelationRepairProposal,
    RelationSpec,
)
from app.modeling.geometry_core import (
    bbox_overlap_volume,
    find_body_by_ref,
    gap_along,
    mate_axis,
)

__all__ = ["verify_relation", "propose_repair"]

_CONTACT_TOL = 0.2  # mm — |folga| abaixo disto = contato
_EPS = 1e-3  # mm — penetração abaixo disto = ruído numérico

# Encosto FACE-A-FACE: contato medido por folga/penetração no eixo do mate.
_FLUSH_KINDS = frozenset({"flush_mate", "cover_opening"})
# CONTENÇÃO/encaixe: a sobreposição de bbox é ESPERADA (pino no furo, peça no
# bolso) — medir contato por overlap>0, NUNCA classificar como penetração.
_CONTAIN_KINDS = frozenset({"coaxial_insert", "hinge_along_shared_edge", "seat_in_pocket"})
# DOF esperado por kind (p/ o relatório; medição real é gate do dono).
_EXPECTED_DOF = {
    "flush_mate": 0,
    "cover_opening": 0,
    "seat_in_pocket": 0,
    "coaxial_insert": 1,
    "hinge_along_shared_edge": 1,
}


def verify_relation(spec: RelationSpec, state_after: ModelState | None) -> GeometricContactReport:
    """Mede a relação no estado pós-execução. ``contact_ok``/``gap_mm``/
    ``interference_mm3``/``dof_ok`` + achados legíveis. Só reporta."""

    report = GeometricContactReport(
        relation_kind=spec.kind, moving=spec.moving, reference=spec.reference
    )
    m = find_body_by_ref(state_after, spec.moving)
    r = find_body_by_ref(state_after, spec.reference)
    if m is None or r is None:
        report.ok = False
        report.findings.append(
            f"corpo ausente no estado pós-execução (moving={m is not None}, "
            f"reference={r is not None}) — a relação pode ter consumido/falhado."
        )
        return report

    if spec.kind in _FLUSH_KINDS:
        axis = mate_axis(m, r)
        gap = gap_along(m, r, axis)
        report.gap_mm = round(gap, 3)
        if gap < -_EPS:
            # penetração: interferência REAL ao longo do eixo do mate.
            report.interference_mm3 = round(bbox_overlap_volume(m, r), 2)
            report.contact_ok = False
            report.ok = False
            report.findings.append(
                f"penetração de {-gap:.2f} mm no eixo {'xyz'[axis]} "
                f"('{spec.moving}' atravessa '{spec.reference}')."
            )
        elif gap > _CONTACT_TOL:
            report.contact_ok = False
            report.ok = False
            report.findings.append(
                f"folga de {gap:.2f} mm: '{spec.moving}' não encosta em '{spec.reference}'."
            )
        else:
            report.contact_ok = True
    elif spec.kind in _CONTAIN_KINDS:
        # Contenção/encaixe (coaxial, bolso): sobreposição de bbox é ESPERADA (o
        # pino entra no furo, a peça assenta no bolso) — NUNCA tratar como
        # penetração. Contato = overlap>0; sem overlap, o encaixe não ocorreu.
        ov = bbox_overlap_volume(m, r)
        report.contact_ok = ov > 0
        if ov <= 0:
            report.ok = False
            report.findings.append(
                f"'{spec.moving}' não sobrepõe '{spec.reference}' — o encaixe "
                f"({spec.kind}) não se concretizou."
            )
    else:
        # distribute_on_edge etc.: distribuição N-corpos, não um contato 2-corpos.
        # Honestidade (invariante 6): reporta explicitamente que não há verificação
        # geométrica de contato p/ este kind — em vez de devolver 'ok' silencioso.
        report.findings.append(
            f"kind '{spec.kind}' não tem verificação geométrica de contato 2-corpos "
            "(distribuição N-corpos) — verificar no gate."
        )
    # DOF não é medível do ModelState (precisa da junta) — gate do dono. Registra
    # o esperado p/ o relatório, sem afirmar medição.
    if spec.kind in _EXPECTED_DOF:
        report.findings.append(f"DOF esperado={_EXPECTED_DOF[spec.kind]} (verificar no gate).")

    return report


def propose_repair(
    report: GeometricContactReport, spec: RelationSpec
) -> RelationRepairProposal | None:
    """Correção determinística PROPOSTA p/ relações de encosto: re-junta com
    ``offset`` = -folga (fecha) ou -penetração (afasta). ``None`` quando já há
    contato ou o kind não tem reparo fechado. NÃO auto-aplica (gate P6)."""

    if spec.kind not in _FLUSH_KINDS or report.gap_mm is None or report.contact_ok:
        return None
    gap = report.gap_mm
    if gap > _CONTACT_TOL:
        return RelationRepairProposal(
            relation_kind=spec.kind,
            reason="gap",
            offset_mm=round(-gap, 3),
            detail=f"aproximar '{spec.moving}' em {gap:.2f} mm p/ encostar.",
        )
    if gap < -_EPS:
        return RelationRepairProposal(
            relation_kind=spec.kind,
            reason="interference",
            offset_mm=round(-gap, 3),
            detail=f"afastar '{spec.moving}' em {-gap:.2f} mm p/ eliminar penetração.",
        )
    return None
