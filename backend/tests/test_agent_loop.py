"""Testes do loop agêntico de auto-correção (Fase 2, RF-010/011) + assets.

Cobre o controle do ``ModelingAgentLoop`` (sucesso, corrige-e-passa, esgota +
rollback, divergência geométrica) com um executor scriptado (sem Fusion), além
de ``planner.build_correction_context`` e ``tool_schemas``.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling import tool_schemas
from app.modeling.agent_loop import MAX_CORRECTION_ITERATIONS, ModelingAgentLoop
from app.modeling.executor import _StepOutcome
from app.modeling.planner import build_correction_context, correct_step

# --------------------------------------------------------------------------- doubles


class _FakeTracer:
    def record(self, *args, **kwargs) -> None:  # noqa: D401 - no-op
        pass

    def flush(self, *args, **kwargs) -> None:
        pass


class _FakeStore:
    def __init__(self) -> None:
        self.plans: dict[str, ModelingPlan] = {}
        self.audits: list[Any] = []

    def upsert_modeling_plan(self, plan: ModelingPlan) -> ModelingPlan:
        self.plans[plan.id] = plan
        return plan

    def add_audit_event(self, event: Any) -> Any:
        self.audits.append(event)
        return event


class _ScriptedExecutor:
    """Mimics ModelingExecutorService for the loop: one decision per step."""

    def __init__(self, store: _FakeStore, decide) -> None:
        self.store = store
        self._tracer = _FakeTracer()
        self.decide = decide
        self.calls: list[tuple[str, bool]] = []

    def _execute_single_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> _StepOutcome:
        ok = bool(self.decide(step))
        self.calls.append((step.tool_name, ok))
        output = {
            "ok": ok,
            "tool_name": step.tool_name,
            "transport": "mock",
            "mcp_server": "scripted",
            "error_code": None if ok else "scripted.boom",
            "message": "ok" if ok else "falha scriptada",
        }
        updated = step.model_copy(
            update={
                "status": ModelingStepStatus.completed if ok else ModelingStepStatus.failed,
                "output_json": output,
            }
        )
        return _StepOutcome(
            step=updated,
            output=output,
            tool_call_id=None,
            event=f"{step.seq}. {step.tool_name}",
            ok=ok,
        )


def _step(seq: int, tool_name: str, **input_json) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=seq,
        title=f"Etapa {seq}",
        software=ModelingSoftware.fusion,
        tool_name=tool_name,
        risk_level=ModelingRiskLevel.low,
        approval_required=False,
        status=ModelingStepStatus.approved,
        input_json=dict(input_json),
    )


def _plan(*steps: ModelingPlanStep) -> ModelingPlan:
    return ModelingPlan(
        prompt="peça de teste",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.approved,
        steps=list(steps),
    )


# --------------------------------------------------------------------------- loop


def test_loop_runs_clean_without_correction() -> None:
    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: True)
    corrector_calls: list[int] = []

    loop = ModelingAgentLoop(
        executor,
        corrector=lambda s, o, a: corrector_calls.append(a) or s,  # nunca chamado
    )
    result = loop.run(_plan(_step(1, "fusion.create_sketch"), _step(2, "fusion.extrude_profile")))

    assert result.plan.status is ModelingPlanStatus.completed
    assert result.executed_step_ids == [s.id for s in result.plan.steps]
    assert corrector_calls == []  # nenhuma correção necessária
    assert executor.calls == [("fusion.create_sketch", True), ("fusion.extrude_profile", True)]


def test_loop_corrects_then_succeeds() -> None:
    store = _FakeStore()
    # Falha enquanto não estiver "_fixed"; o corrector marca _fixed.
    executor = _ScriptedExecutor(store, decide=lambda step: bool(step.input_json.get("_fixed")))

    def corrector(step, output, attempt):
        return step.model_copy(update={"input_json": {**step.input_json, "_fixed": True}})

    loop = ModelingAgentLoop(executor, corrector=corrector)
    result = loop.run(_plan(_step(1, "fusion.hole")))

    assert result.plan.status is ModelingPlanStatus.completed
    # 1 execução inicial (falha) + 1 reexecução corrigida (ok).
    assert executor.calls == [("fusion.hole", False), ("fusion.hole", True)]


def test_loop_exhausts_iterations_and_rolls_back() -> None:
    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: False)  # sempre falha
    rollbacks: list[str] = []

    loop = ModelingAgentLoop(
        executor,
        corrector=lambda s, o, a: s,  # "corrige" sem resolver
        rollback=lambda plan: rollbacks.append(plan.id),
    )
    result = loop.run(_plan(_step(1, "fusion.hole"), _step(2, "fusion.extrude_profile")))

    assert result.plan.status is ModelingPlanStatus.failed
    # 1 inicial + teto reexecuções para o passo 1.
    assert len(executor.calls) == 1 + MAX_CORRECTION_ITERATIONS
    assert rollbacks == [result.plan.id]  # rollback disparado uma vez
    # Passo 2 não rodou (motor parou após esgotar o passo 1).
    assert all(tool == "fusion.hole" for tool, _ in executor.calls)
    assert result.plan.steps[1].id in result.blocked_step_ids


def test_loop_corrects_on_geometric_divergence_even_when_tool_ok() -> None:
    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: True)  # tool sempre ok

    def verifier(step, output):
        # Diverge até o passo ser "_fixed".
        return None if step.input_json.get("_fixed") else {"expected_mm": 40, "measured_mm": 30}

    def corrector(step, output, attempt):
        return step.model_copy(update={"input_json": {**step.input_json, "_fixed": True}})

    loop = ModelingAgentLoop(executor, corrector=corrector, verifier=verifier)
    result = loop.run(_plan(_step(1, "fusion.extrude_profile")))

    assert result.plan.status is ModelingPlanStatus.completed
    # Apesar de ok=True, a divergência geométrica forçou 1 correção.
    assert executor.calls == [("fusion.extrude_profile", True), ("fusion.extrude_profile", True)]


def test_build_dimension_verifier_compares_list_dims() -> None:
    """C (verifier): expected_dimensions_mm e o read-back das tools são listas
    [x,y,z]. O verifier compara por eixo; bbox z=0 (cut consumiu a peça) diverge.
    """

    from app.modeling.agent_loop import build_dimension_verifier

    verifier = build_dimension_verifier()
    step = _step(1, "fusion.extrude_profile", expected_dimensions_mm=[60, 40, 30])
    assert verifier(step, {"dimensions_mm": [60.0, 40.0, 30.0]}) is None
    div = verifier(step, {"dimensions_mm": [60.0, 40.0, 0.0]})
    assert div is not None and "z" in div
    assert div["z"]["expected"] == 30 and div["z"]["measured"] == 0.0


def test_build_surface_verifier_detects_area_and_closed_divergence() -> None:
    """T5.3b (Fase 5): build_surface_verifier compara expected_surface_area_mm2
    e expected_is_closed contra o read-back. Cobre o caminho crítico do gate
    da carenagem: stitch deixar gap → is_closed=False → loop auto-corrige
    (aumenta tolerance ou insere patch) antes do thicken simétrico falhar."""

    from app.modeling.agent_loop import build_surface_verifier

    verifier = build_surface_verifier(area_tolerance_mm2=5.0)

    # Step do stitch declara que a costura precisa fechar.
    step = _step(
        1,
        "fusion.stitch_surfaces",
        expected_is_closed=True,
        expected_surface_area_mm2=15000.0,
    )

    # Caso conforme.
    ok = {"is_closed": True, "surface_area_mm2": 15001.0}
    assert verifier(step, ok) is None

    # Caso divergente: ficou aberto E área errada.
    div = verifier(step, {"is_closed": False, "surface_area_mm2": 13000.0})
    assert div is not None
    assert div["is_closed"]["expected"] is True and div["is_closed"]["measured"] is False
    assert "hint" in div["is_closed"]  # hint orienta o corretor.
    assert div["surface_area_mm2"]["delta"] == -2000.0

    # Sem expected_* no step → no-op (backward-compat).
    step_legacy = _step(2, "fusion.extrude_profile", distance_mm=10)
    assert verifier(step_legacy, {"surface_area_mm2": 99.0}) is None


def test_combine_verifiers_merges_divergences() -> None:
    """T5.3b: combine_verifiers permite plugar dimensão + superfície no MESMO
    loop sem duplicar caminho de execução. Divergências de ambos são mescladas."""

    from app.modeling.agent_loop import (
        build_dimension_verifier,
        build_surface_verifier,
        combine_verifiers,
    )

    combined = combine_verifiers(
        build_dimension_verifier(),
        build_surface_verifier(),
    )
    step = _step(
        1,
        "fusion.thicken_surface",
        expected_dimensions_mm=[60, 40, 30],
        expected_is_closed=True,
    )
    # bbox certo mas surface aberta — só is_closed diverge.
    div = combined(
        step,
        {"dimensions_mm": [60.0, 40.0, 30.0], "is_closed": False},
    )
    assert div is not None and "is_closed" in div and "x" not in div
    # ambos divergem — payload tem chaves dos dois verifiers.
    div2 = combined(
        step,
        {"dimensions_mm": [60.0, 40.0, 0.0], "is_closed": False},
    )
    assert div2 is not None and "z" in div2 and "is_closed" in div2


def test_verifier_reads_dimensions_from_http_envelope() -> None:
    """C (gate 2026-05-26): tools fusion devolvem ``dimensions_mm`` DENTRO do
    envelope HTTP (JSON stringificado em message/result.message). O verifier
    precisa desempacotar via ``inner_fusion_payload`` — senão ficava mudo no
    Fusion real (lia o nível errado → None → nenhuma divergência detectada)."""

    import json as _json

    from app.modeling.agent_loop import build_dimension_verifier

    verifier = build_dimension_verifier()
    step = _step(1, "fusion.extrude_profile", expected_dimensions_mm=[60, 40, 30])
    blob = _json.dumps({"ok": True, "dimensions_mm": [60.0, 40.0, 0.0]})
    enveloped = {
        "ok": True,
        "input": {},
        "result": {"message": blob, "success": True},
        "message": blob,
        "software": "fusion",
    }
    div = verifier(step, enveloped)
    assert div is not None and "z" in div
    assert div["z"]["measured"] == 0.0
    # Conforme (sem divergência) também desempacota o envelope.
    ok_blob = _json.dumps({"ok": True, "dimensions_mm": [60.0, 40.0, 30.0]})
    assert verifier(step, {"result": {"message": ok_blob}, "message": ok_blob}) is None


def test_loop_threads_divergence_to_corrector() -> None:
    """C (verifier): quando o tool foi OK mas a geometria divergiu, o loop injeta
    a divergência no output que vai ao corretor (para o LLM ver esperado×medido).
    """

    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: True)  # tool sempre ok
    seen: list[dict[str, Any]] = []

    def verifier(step, output):
        return None if step.input_json.get("_fixed") else {"z": {"expected": 30, "measured": 0}}

    def corrector(step, output, attempt):
        seen.append(output)
        return step.model_copy(update={"input_json": {**step.input_json, "_fixed": True}})

    loop = ModelingAgentLoop(executor, corrector=corrector, verifier=verifier)
    result = loop.run(
        _plan(_step(1, "fusion.extrude_profile", expected_dimensions_mm=[60, 40, 30]))
    )

    assert result.plan.status is ModelingPlanStatus.completed
    assert seen and seen[0].get("verification_divergence") == {"z": {"expected": 30, "measured": 0}}


def test_loop_draft_plan_does_not_execute() -> None:
    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: True)
    loop = ModelingAgentLoop(executor)
    plan = _plan(_step(1, "fusion.create_sketch"))
    plan = plan.model_copy(update={"status": ModelingPlanStatus.draft})

    result = loop.run(plan)

    assert result.executed_step_ids == []
    assert executor.calls == []


# --------------------------------------------------------------------------- assets


def test_build_correction_context_includes_error_and_verification() -> None:
    step = _step(2, "fusion.hole", diameter_mm=6)
    output = {"ok": False, "error_code": "fusion.profile_not_found", "message": "perfil ausente"}
    context = build_correction_context(
        step,
        output,
        attempt=2,
        max_attempts=5,
        verification={"expected_mm": 40, "measured_mm": 30},
    )

    assert "fusion.hole" in context
    assert "fusion.profile_not_found" in context
    assert "perfil ausente" in context
    assert "2/5" in context
    assert "expected_mm" in context
    assert "<correcao>" in context and "</correcao>" in context


def test_tool_schemas_render_includes_units_and_examples() -> None:
    rendered = tool_schemas.render_tool_schema("fusion.add_rectangle")
    assert "fusion.add_rectangle" in rendered
    assert "width_mm" in rendered
    assert "(mm)" in rendered
    assert "ex.:" in rendered

    assert tool_schemas.tool_schema("fusion.add_rectangle") is not None


def test_fillet_chamfer_schema_documents_valid_edge_selectors() -> None:
    """Gate da placa (m3d_plan_99598a25): o loop ESGOTOU corrigindo fillet_edges
    porque o LLM inventava edge_selector ('outer_edges_of_body:Body1') e o schema
    — que é passado ao corretor em _correction_messages — não listava os válidos.
    Agora fillet/chamfer documentam o enum all|top|bottom|vertical|horizontal.
    """

    rendered = tool_schemas.render_tool_schema("fusion.fillet_edges")
    assert "edge_selector" in rendered
    for valid in ("all", "top", "vertical", "horizontal"):
        assert valid in rendered
    # chamfer compartilha a mesma gramática de selector
    assert "edge_selector" in tool_schemas.render_tool_schema("fusion.chamfer_edges")


def test_tool_schemas_unknown_tool_falls_back_to_registry() -> None:
    # Tool real do registry sem schema explícito ainda → usa a descrição.
    rendered = tool_schemas.render_tool_schema("fusion.add_cylinder")
    assert "fusion.add_cylinder" in rendered
    assert tool_schemas.tool_schema("fusion.add_cylinder") is None


# --------------------------------------------------------------------------- wiring


class _FakeGateway:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls = 0

    async def generate_structured(self, *, model, messages, schema_name, schema):
        self.calls += 1
        return self.payload


def test_correct_step_uses_llm_to_fix_step() -> None:
    gateway = _FakeGateway(
        {"tool_name": "fusion.hole", "input_json": json.dumps({"diameter_mm": 6, "_fixed": True})}
    )
    step = _step(2, "fusion.hole", diameter_mm=99)
    output = {"ok": False, "error_code": "fusion.boom", "message": "falhou"}

    fixed = correct_step(step, output, 1, gateway=gateway, model=object())

    assert gateway.calls == 1
    assert fixed.tool_name == "fusion.hole"
    assert fixed.input_json.get("_fixed") is True
    assert fixed.status is ModelingStepStatus.approved
    assert fixed.error is None


def test_orchestrator_run_execution_uses_loop_when_flag_on(monkeypatch) -> None:
    from app.core.config import settings
    from app.modeling.chat_orchestrator import ModelingChatOrchestrator

    monkeypatch.setattr(settings, "modeling_agentic_loop_enabled", True)
    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: True)

    class _FakePlanner:
        def build_corrector(self, **_kwargs):
            return None  # sem corretor; o loop ainda executa fim-a-fim

    orchestrator = ModelingChatOrchestrator(store=store, planner=_FakePlanner(), executor=executor)
    result = orchestrator._run_execution(_plan(_step(1, "fusion.create_sketch")))

    assert result.plan.status is ModelingPlanStatus.completed
    # O caminho do loop emite o audit específico (prova que não usou o executor linear).
    assert any(
        getattr(event, "event_type", None) == "modeling.agent_loop_executed"
        for event in store.audits
    )


def test_run_plan_with_optional_loop_uses_loop_when_flag_on(monkeypatch) -> None:
    """Fonte ÚNICA loop×linear usada pelo orchestrator E pelo service (card).

    Regressão do gate da bola (m3d_plan_608fd2579): a flag estava ON, mas o card
    (`service.execute_plan`) executava SEMPRE linear porque o loop só vivia no
    orchestrator. Com flag ON o helper roda pelo loop (emite
    ``modeling.agent_loop_executed``).
    """

    from app.core.config import settings
    from app.modeling.agent_loop import run_plan_with_optional_loop

    monkeypatch.setattr(settings, "modeling_agentic_loop_enabled", True)
    store = _FakeStore()
    executor = _ScriptedExecutor(store, decide=lambda step: True)

    class _FakePlanner:
        def build_corrector(self, **_kwargs):
            return None

    result = run_plan_with_optional_loop(
        executor, _FakePlanner(), _plan(_step(1, "fusion.create_sketch"))
    )

    assert result.plan.status is ModelingPlanStatus.completed
    assert any(
        getattr(e, "event_type", None) == "modeling.agent_loop_executed" for e in store.audits
    )


def test_run_plan_with_optional_loop_uses_linear_when_flag_off(monkeypatch) -> None:
    """Com a flag OFF, delega ao executor linear e NEM constrói o corretor."""

    from app.core.config import settings
    from app.modeling.agent_loop import run_plan_with_optional_loop

    monkeypatch.setattr(settings, "modeling_agentic_loop_enabled", False)
    sentinel = object()
    calls: dict[str, bool] = {}

    class _LinearExec:
        def execute_plan(self, plan):
            calls["linear"] = True
            return sentinel

    class _FakePlanner:
        def build_corrector(self, **_kwargs):
            raise AssertionError("não deve construir corretor com a flag desligada")

    result = run_plan_with_optional_loop(
        _LinearExec(), _FakePlanner(), _plan(_step(1, "fusion.create_sketch"))
    )

    assert result is sentinel
    assert calls.get("linear") is True


def test_build_dimension_verifier_compares_expected_vs_measured() -> None:
    from app.modeling.agent_loop import build_dimension_verifier

    verifier = build_dimension_verifier(tolerance_mm=0.5)
    step = _step(1, "fusion.add_box", expected_dimensions_mm={"x": 40.0, "y": 20.0})

    # Medido dentro da tolerância → conforme (None).
    assert verifier(step, {"dimensions_mm": {"x": 40.3, "y": 20.0}}) is None

    # Medido fora da tolerância → divergência detalhada.
    divergence = verifier(step, {"dimensions_mm": {"x": 30.0, "y": 20.0}})
    assert divergence is not None
    assert divergence["x"] == {"expected": 40.0, "measured": 30.0, "delta": -10.0}
    assert "y" not in divergence

    # Sem dados de verificação (passo sem expected/measured) → None.
    assert verifier(_step(2, "fusion.create_sketch"), {"ok": True}) is None


def test_capture_model_state_populates_and_persists_plan() -> None:
    """F1 (T1.6): _maybe_capture_model_state roda um probe query_geometry pós-
    execução, parseia o ModelState (com tokens) e persiste em plan.model_state."""

    from app.modeling.agent_loop import _maybe_capture_model_state

    store = _FakeStore()

    class _GeomExecutor:
        def __init__(self, store):
            self.store = store
            self.calls: list[str] = []

        def _execute_single_step(self, step, *, plan):
            self.calls.append(step.tool_name)
            output = {
                "ok": True,
                "bodies": [
                    {
                        "name": "Cubo",
                        "stable_id": "sid-cubo",
                        "dimensions_mm": [30, 30, 30],
                        "is_solid": True,
                        "faces": [{"face_token": "FT_TOP", "type": "planar", "area_mm2": 900}],
                        "edges": [],
                    }
                ],
            }
            return _StepOutcome(step=step, output=output, tool_call_id=None, event="x", ok=True)

    ex = _GeomExecutor(store)
    plan = _plan(_step(1, "fusion.add_box"))

    _maybe_capture_model_state(ex, plan)

    assert ex.calls == ["fusion.query_geometry"]  # probe read-back rodou
    assert plan.model_state is not None
    assert plan.model_state.bodies[0].stable_id == "sid-cubo"
    assert plan.model_state.bodies[0].faces[0].token == "FT_TOP"
    # Persistido no store para o próximo bloco/edição ler.
    assert store.plans[plan.id].model_state is not None


def test_capture_model_state_skips_non_fusion() -> None:
    """Captura só roda para fusion; blender/outros não geram probe."""
    from app.modeling.agent_loop import _maybe_capture_model_state
    from app.core.contracts import ModelingSoftware as _SW

    store = _FakeStore()

    class _Ex:
        def __init__(self, store):
            self.store = store
            self.calls = 0

        def _execute_single_step(self, step, *, plan):  # pragma: no cover
            self.calls += 1
            raise AssertionError("não deveria sondar para não-fusion")

    ex = _Ex(store)
    plan = _plan(_step(1, "blender.create_mesh_primitive"))
    plan = plan.model_copy(update={"software_choice": _SW.blender})
    _maybe_capture_model_state(ex, plan)
    assert ex.calls == 0 and plan.model_state is None
