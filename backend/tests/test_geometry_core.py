"""F4 (follow-up do conselho do PR #50): ``geometry_core`` é a FONTE ÚNICA das
medidas de bbox compartilhadas pelo contexto 3D.

Antes desta extração, ``geometry_verifier`` e ``model_critique`` mantinham CÓPIAS
de ``_bbox_overlap_volume`` com corte divergente (estrito ``<= 0`` vs ``<= 1e-3``)
— duas verdades sobre interferência/contato no mesmo modelo. O ``eps`` virou
parâmetro explícito; estes testes travam os DOIS comportamentos no ponto de
divergência (sobreposição de ~1 µm) para que não voltem a derivar em silêncio.
"""

from app.core.contracts import ModelState, ModelStateBody
from app.modeling.geometry_core import (
    bbox_overlap_volume,
    find_body_by_ref,
    gap_along,
    mate_axis,
)


def _body(
    name: str, lo: list[float], hi: list[float], stable_id: str | None = None
) -> ModelStateBody:
    return ModelStateBody(name=name, stable_id=stable_id, bbox_min_mm=lo, bbox_max_mm=hi)


def test_bbox_overlap_volume_eps_is_the_only_difference() -> None:
    a = _body("A", [0, 0, 0], [10, 10, 10])
    # Sobreposição em x de exatamente 0.0005 mm (abaixo de _OVERLAP_EPS=1e-3),
    # plena em y/z: é o sliver onde as duas cópias antigas discordavam.
    b = _body("B", [9.9995, 0, 0], [20, 10, 10])

    # eps=0 (verificador geométrico): qualquer penetração positiva conta.
    strict = bbox_overlap_volume(a, b)
    assert strict > 0
    assert round(strict, 4) == round(0.0005 * 10 * 10, 4)

    # eps=1e-3 (auto-crítica): sub-µm é contato/ruído, não interferência → 0.
    assert bbox_overlap_volume(a, b, eps=1e-3) == 0.0


def test_bbox_overlap_volume_agrees_off_the_sliver() -> None:
    a = _body("A", [0, 0, 0], [10, 10, 10])
    clear = _body("C", [5, 5, 5], [15, 15, 15])  # penetração franca: 5×5×5
    apart = _body("D", [20, 0, 0], [30, 10, 10])  # sem contato no eixo x

    for eps in (0.0, 1e-3):
        assert bbox_overlap_volume(a, clear, eps=eps) == 125.0
        assert bbox_overlap_volume(a, apart, eps=eps) == 0.0


def test_mate_axis_and_gap_along_on_stacked_bodies() -> None:
    base = _body("Base", [0, 0, 0], [10, 10, 10])
    top = _body("Top", [0, 0, 20], [10, 10, 30])  # empilhado em z, 10 mm acima

    assert mate_axis(base, top) == 2  # z = maior separação dos centros
    assert gap_along(base, top, 2) == 10.0  # folga positiva de 10 mm


def test_find_body_by_ref_matches_name_or_stable_id() -> None:
    state = ModelState(
        bodies=[_body("Caixa", [0, 0, 0], [60, 40, 20], stable_id="ID9")],
    )
    assert find_body_by_ref(state, "Caixa") is state.bodies[0]
    assert find_body_by_ref(state, "ID9") is state.bodies[0]
    assert find_body_by_ref(state, "inexistente") is None
    assert find_body_by_ref(None, "Caixa") is None
