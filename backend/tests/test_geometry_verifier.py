"""Testes F8 (Sub 4) — verificador geométrico de relações (``geometry_verifier``).

Mede contato/interferência/DOF do estado pós-execução e propõe reparo
determinístico (offset medido). Só reporta; reparo é proposto, não aplicado.
"""

from __future__ import annotations

from app.core.contracts import ModelState, ModelStateBody, RelationSpec
from app.modeling.geometry_verifier import propose_repair, verify_relation


def _body(name, bmin, bmax):
    return ModelStateBody(name=name, stable_id=name + "_id", bbox_min_mm=bmin, bbox_max_mm=bmax)


def _state(*bodies):
    return ModelState(bodies=list(bodies))


def _flush(moving="Tampa", reference="Caixa"):
    return RelationSpec(kind="flush_mate", moving=moving, reference=reference)


def test_flush_contact_ok() -> None:
    caixa = _body("Caixa", [0, 0, 0], [60, 40, 20])
    tampa = _body("Tampa", [0, 0, 20], [60, 40, 23])  # encosta no topo (gap 0)
    rep = verify_relation(_flush(), _state(caixa, tampa))
    assert rep.contact_ok and rep.ok
    assert abs(rep.gap_mm) < 0.01
    assert propose_repair(rep, _flush()) is None


def test_flush_gap_proposes_approach() -> None:
    caixa = _body("Caixa", [0, 0, 0], [60, 40, 20])
    tampa = _body("Tampa", [0, 0, 22], [60, 40, 25])  # 2 mm flutuando
    rep = verify_relation(_flush(), _state(caixa, tampa))
    assert not rep.contact_ok and not rep.ok
    assert rep.gap_mm == 2.0
    prop = propose_repair(rep, _flush())
    assert prop is not None and prop.reason == "gap" and prop.offset_mm == -2.0


def test_flush_penetration_is_interference() -> None:
    caixa = _body("Caixa", [0, 0, 0], [60, 40, 20])
    tampa = _body("Tampa", [0, 0, 17], [60, 40, 23])  # cravada 3 mm na caixa
    rep = verify_relation(_flush(), _state(caixa, tampa))
    assert not rep.contact_ok and not rep.ok
    assert rep.gap_mm == -3.0 and rep.interference_mm3 > 0
    prop = propose_repair(rep, _flush())
    assert prop is not None and prop.reason == "interference" and prop.offset_mm == 3.0


def test_missing_body_reports_not_ok() -> None:
    rep = verify_relation(_flush(), _state(_body("Caixa", [0, 0, 0], [60, 40, 20])))
    assert not rep.ok and any("ausente" in f for f in rep.findings)


def test_coaxial_overlap_is_contact() -> None:
    furo = _body("Caixa", [0, 0, 0], [60, 40, 20])
    pino = _body("Pino", [28, 18, 5], [32, 22, 25])  # entra no furo (sobrepõe)
    spec = RelationSpec(kind="coaxial_insert", moving="Pino", reference="Caixa")
    rep = verify_relation(spec, _state(furo, pino))
    assert rep.contact_ok and rep.ok
    # coaxial não propõe reparo de offset (não é encosto planar).
    assert propose_repair(rep, spec) is None


def test_seat_in_pocket_containment_is_contact_not_penetration() -> None:
    # Laudo (F): assento correto (peça contida no bolso) era reportado como
    # penetração massiva + reparo ejetava a peça. Agora é contenção esperada.
    caixa = _body("Caixa", [0, 0, 0], [60, 40, 20])
    peca = _body("Peca", [10, 10, 2], [50, 30, 18])  # contida no bbox da caixa
    spec = RelationSpec(kind="seat_in_pocket", moving="Peca", reference="Caixa")
    rep = verify_relation(spec, _state(caixa, peca))
    assert rep.contact_ok and rep.ok
    assert rep.interference_mm3 == 0.0
    assert propose_repair(rep, spec) is None


def test_distribute_on_edge_reports_not_contact_verifiable() -> None:
    # Laudo (G): kind N-corpos não tem verificação de contato 2-corpos — reporta
    # explícito em vez de 'ok' silencioso.
    caixa = _body("Caixa", [0, 0, 0], [60, 40, 20])
    no = _body("No", [0, 0, 0], [2, 2, 2])
    spec = RelationSpec(kind="distribute_on_edge", moving="No", reference="Caixa")
    rep = verify_relation(spec, _state(caixa, no))
    assert any("não tem verificação geométrica" in f for f in rep.findings)


def test_dof_expected_reported() -> None:
    caixa = _body("Caixa", [0, 0, 0], [60, 40, 20])
    tampa = _body("Tampa", [0, 0, 20], [60, 40, 23])
    rep = verify_relation(_flush(), _state(caixa, tampa))
    assert any("DOF esperado=0" in f for f in rep.findings)
