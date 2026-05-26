"""Testes do módulo de observabilidade (``app.modeling.observability``).

Cobre:
- ``ModelingTracer.start_trace`` + propagação via contextvars.
- ``record`` quando observability está desligado vira no-op.
- ``record_span`` mede duração e emite ``.completed``/``.failed``.
- Truncate de payload acima de ``MODELING_TRACE_PAYLOAD_LIMIT_BYTES``.
- Mapping de exceção do gateway → event_type específico via
  ``classify_provider_exception`` + ``_LLM_ERROR_EVENT_TYPES``.

Não cobre o pipeline ponta-a-ponta — isso fica para teste de integração
via ``scripts/smoke-modeling-trace.ps1`` rodando contra a stack
containerizada (ver docs/local-dev.md).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.contracts import (
    MODELING_TRACE_PAYLOAD_LIMIT_BYTES,
    ModelingTraceEvent,
    ModelingTraceLevel,
    ModelingTraceSource,
)
from app.llm_gateway.exceptions import (
    LLMAuthError,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    classify_provider_exception,
)
from app.modeling.observability import (
    ModelingTracer,
    _plan_id_var,
    _project_id_var,
    _sequence_var,
    _session_id_var,
    _trace_id_var,
    _truncate_payload,
    current_trace_id,
    generate_trace_id,
    reset_tracer,
)


class _FakeStore:
    """Store mínima para satisfazer ``TraceEventStore``.

    Captura tudo em memória para asserções. ``raise_on_flush`` permite
    simular falha do banco e verificar que o tracer não propaga exceção.
    """

    def __init__(self, *, raise_on_flush: bool = False) -> None:
        self.events: list[ModelingTraceEvent] = []
        self.raise_on_flush = raise_on_flush

    def record_trace_events_bulk(self, events: list[ModelingTraceEvent]) -> None:
        if self.raise_on_flush:
            raise RuntimeError("simulated DB failure")
        self.events.extend(events)


@pytest.fixture(autouse=True)
def _reset_tracer_singleton() -> None:
    """Garante isolamento entre testes (o tracer é singleton no módulo).

    Resetar TANTO o singleton quanto os contextvars — eventos emitidos
    em testes anteriores deixam o trace_id pendurado e contaminam o
    próximo teste se não limparmos.
    """

    reset_tracer()
    _trace_id_var.set(None)
    _plan_id_var.set(None)
    _session_id_var.set(None)
    _project_id_var.set(None)
    _sequence_var.set(0)
    yield
    reset_tracer()
    _trace_id_var.set(None)
    _plan_id_var.set(None)
    _session_id_var.set(None)
    _project_id_var.set(None)
    _sequence_var.set(0)


def test_generate_trace_id_is_sortable_by_time() -> None:
    import time as _time

    a = generate_trace_id()
    _time.sleep(0.002)  # garante ms diferente (vs apenas randomness)
    b = generate_trace_id()
    # Propriedade real: o prefixo de timestamp (parte após "mt_" e antes
    # do segundo "_") é monotônico não-decrescente. Sufixo random pode
    # variar; comparar apenas a parte temporal.
    ts_a = a.split("_")[1]
    ts_b = b.split("_")[1]
    assert ts_a < ts_b


def test_start_trace_binds_contextvar_and_emits_started_event() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    trace_id = tracer.start_trace(session_id="sess-1", project_id="proj-1")

    assert current_trace_id() == trace_id
    assert tracer._buffers[trace_id].events[0].event_type == "trace.started"
    assert tracer._buffers[trace_id].events[0].source == ModelingTraceSource.backend
    assert tracer._buffers[trace_id].events[0].payload["session_id"] == "sess-1"


def test_bind_plan_backfills_buffered_events_without_plan_id() -> None:
    """Fix do "trace vazio por plano" (gate m3d_plan_2f7aeff0): spans do planner
    (``model_resolved``/``llm_request``) gravados ANTES do plano existir saiam
    com ``plan_id=None`` e o diagnóstico-por-plano não os achava. ``bind_plan``
    deve propagar o plan_id recém-ligado aos eventos já buffered do trace.
    """

    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")  # plan_id ainda None
    tracer.record("planner.model_resolved", source=ModelingTraceSource.backend)
    tracer.record("planner.llm_request", source=ModelingTraceSource.backend)

    buffer = tracer._buffers[current_trace_id()]
    assert [e.plan_id for e in buffer.events] == [None, None, None]  # +trace.started

    tracer.bind_plan("m3d_plan_x")
    assert all(e.plan_id == "m3d_plan_x" for e in buffer.events)

    # Eventos seguintes continuam herdando o plan_id via contextvar.
    tracer.record("planner.plan_created", source=ModelingTraceSource.backend)
    assert buffer.events[-1].plan_id == "m3d_plan_x"


def test_execute_plan_opens_trace_for_card_path() -> None:
    """Fix do "trace de execução vazio" (gate m3d_plan_2f7aeff0): o card chama
    ``/plans/{id}/execute`` FORA de um trace aberto, então todo ``record()`` do
    executor virava no-op (``tid is None``). ``ModelingService.execute_plan`` deve
    abrir um trace ligado ao plano durante a execução. Usa store/executor fakes
    para não tocar o storage real (conftest de isolamento ainda não mergeado).
    """

    from app.core.contracts import (
        ModelingExecutionResult,
        ModelingPlan,
        ModelingPlanStatus,
        ModelingSoftware,
    )
    from app.modeling.observability import current_plan_id
    from app.modeling.service import ModelingService

    plan = ModelingPlan(
        id="m3d_plan_test_a1",
        prompt="peça de teste",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.approved,
        steps=[],
    )
    seen: dict[str, Any] = {}

    class _Store:
        def record_trace_events_bulk(self, events: list[ModelingTraceEvent]) -> None:
            pass

        def get_modeling_plan(self, plan_id: str) -> ModelingPlan:
            return plan

    class _Executor:
        def execute_plan(self, p: ModelingPlan) -> ModelingExecutionResult:
            seen["trace_id"] = current_trace_id()
            seen["plan_id"] = current_plan_id()
            return ModelingExecutionResult(
                plan=p,
                executed_step_ids=[],
                blocked_step_ids=[],
                events=[],
                tool_call_ids=[],
            )

    svc = ModelingService(store=_Store())
    svc.executor = _Executor()  # type: ignore[assignment]

    assert current_trace_id() is None  # nada aberto antes (caminho do card)
    svc.execute_plan("m3d_plan_test_a1")

    assert seen["trace_id"] is not None  # trace estava ABERTO durante a execução
    assert seen["plan_id"] == "m3d_plan_test_a1"  # e ligado ao plano


def test_record_without_active_trace_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store)
    # Sem start_trace, não há contextvar — deve retornar None silenciosamente.
    result = tracer.record("planner.foo", source=ModelingTraceSource.backend)
    assert result is None
    assert store.events == []


def test_record_when_observability_disabled_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modeling import observability as obs

    monkeypatch.setattr(obs.settings, "modeling_observability_enabled", False)
    store = _FakeStore()
    tracer = ModelingTracer(store=store)
    tracer.start_trace(session_id="sess")
    result = tracer.record("planner.foo", source=ModelingTraceSource.backend)
    assert result is None


def test_batch_flush_at_batch_size() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=3)
    tracer.start_trace(session_id="sess")
    # start_trace emite 1 evento (trace.started). Mais 2 → 3 → flush.
    tracer.record("a", source=ModelingTraceSource.backend)
    assert store.events == []  # ainda buffered
    tracer.record("b", source=ModelingTraceSource.backend)
    # Agora bateu o batch_size, flush automático aconteceu.
    assert len(store.events) == 3


def test_explicit_flush_drains_buffer() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")
    tracer.record("a", source=ModelingTraceSource.backend)
    assert store.events == []
    tracer.flush()
    assert len(store.events) == 2  # trace.started + "a"


def test_flush_failure_is_swallowed() -> None:
    """Tracer nunca pode derrubar o fluxo do usuário por falha de I/O."""

    store = _FakeStore(raise_on_flush=True)
    tracer = ModelingTracer(store=store, batch_size=2)
    tracer.start_trace(session_id="sess")
    # Não deve levantar mesmo com a store quebrada.
    tracer.record("a", source=ModelingTraceSource.backend)
    tracer.record("b", source=ModelingTraceSource.backend)
    tracer.flush()


def test_record_span_emits_completed_with_duration() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")

    with tracer.record_span("planner.llm_request") as span:
        span.attach({"tokens": 42})

    tracer.flush()
    by_type = [e.event_type for e in store.events]
    assert "planner.llm_request" in by_type
    assert "planner.llm_request.completed" in by_type
    completed = next(e for e in store.events if e.event_type == "planner.llm_request.completed")
    assert completed.duration_ms is not None and completed.duration_ms >= 0
    assert completed.payload["tokens"] == 42


def test_record_span_start_payload_is_not_mutated_by_attach() -> None:
    """PR#28 follow-up: ``span.attach`` nao reescreve retroativamente o start."""

    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")

    with tracer.record_span(
        "planner.llm_request",
        payload={"phase": "start"},
    ) as span:
        span.attach({"tokens": 42})

    tracer.flush()
    started = next(e for e in store.events if e.event_type == "planner.llm_request")
    completed = next(e for e in store.events if e.event_type == "planner.llm_request.completed")
    assert started.payload == {"phase": "start"}
    assert completed.payload["tokens"] == 42


def test_record_span_emits_failed_and_reraises() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")

    with pytest.raises(ValueError):
        with tracer.record_span("planner.llm_request"):
            raise ValueError("boom")

    tracer.flush()
    types = [e.event_type for e in store.events]
    assert "planner.llm_request.failed" in types
    failed = next(e for e in store.events if e.event_type == "planner.llm_request.failed")
    assert failed.level == ModelingTraceLevel.error
    assert failed.payload["exception"] == "ValueError"


def test_truncate_payload_under_limit_returns_as_is() -> None:
    payload: dict[str, Any] = {"a": "x" * 100}
    assert _truncate_payload(payload) is payload


def test_truncate_payload_over_limit_marks_truncated() -> None:
    huge = "x" * (MODELING_TRACE_PAYLOAD_LIMIT_BYTES * 2)
    out = _truncate_payload({"prompt": huge, "model": "y"})
    assert out.get("_truncated") is True
    assert out["_original_size_bytes"] >= len(huge)
    assert "prompt" in out["_keys"] and "model" in out["_keys"]


def test_truncate_payload_non_serializable() -> None:
    class NotSerializable:
        pass

    out = _truncate_payload({"obj": NotSerializable()})
    # default=str do json.dumps na verdade serializa quase tudo — então
    # o truncate primeiro vai conseguir serializar via default. O caso
    # de erro de serialização real é quando o default falha; aqui o
    # objeto vira a representação string e o tamanho não excede.
    assert isinstance(out, dict)


def test_ingest_external_events_records_with_default_source() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")

    tracer.ingest_external_events(
        [
            {
                "event_type": "fusion.tool_completed",
                "level": "info",
                "message": "OK",
                "payload": {"tool": "add_sphere"},
            }
        ],
        default_source=ModelingTraceSource.fusion,
    )
    tracer.flush()
    fusion_events = [e for e in store.events if e.source == ModelingTraceSource.fusion]
    assert len(fusion_events) == 1
    assert fusion_events[0].event_type == "fusion.tool_completed"


def test_ingest_external_events_tolerates_malformed() -> None:
    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess")

    # Source inválido — deve descartar o evento mas não quebrar.
    tracer.ingest_external_events(
        [
            {"event_type": "x.malformed", "source": "INVALID"},
            {"event_type": "x.ok", "source": "fusion", "level": "info"},
        ]
    )
    tracer.flush()
    types = [e.event_type for e in store.events]
    assert "x.ok" in types
    assert "x.malformed" not in types


# ---------------------------------------------------------------------------
# Exception classifier
# ---------------------------------------------------------------------------


class _FakeAuthError(Exception):
    """Simula openai.AuthenticationError sem importar a SDK."""


class _FakeTimeoutError(Exception):
    pass


class _FakeRateLimitError(Exception):
    pass


@pytest.mark.parametrize(
    "exc_class, expected_type",
    [
        (_FakeAuthError, LLMAuthError),
        (_FakeTimeoutError, LLMTimeoutError),
        (_FakeRateLimitError, LLMRateLimitError),
    ],
)
def test_classify_provider_exception_maps_by_name(
    exc_class: type, expected_type: type[LLMProviderError]
) -> None:
    result = classify_provider_exception(exc_class("error message"))
    assert isinstance(result, expected_type)


def test_classify_provider_exception_unknown_returns_base() -> None:
    class _RandomError(Exception):
        pass

    result = classify_provider_exception(_RandomError("???"))
    assert isinstance(result, LLMProviderError)
    assert type(result) is LLMProviderError


def test_classify_provider_exception_detects_timeout_by_message() -> None:
    class _GenericError(Exception):
        pass

    result = classify_provider_exception(_GenericError("Request timed out after 30s"))
    assert isinstance(result, LLMTimeoutError)


def test_llm_auth_error_is_not_retryable() -> None:
    err = LLMAuthError("API key invalid")
    assert err.retryable is False


def test_llm_timeout_error_is_retryable() -> None:
    err = LLMTimeoutError("Request timed out")
    assert err.retryable is True


def test_llm_invalid_response_error_is_not_retryable() -> None:
    err = LLMInvalidResponseError("malformed JSON")
    assert err.retryable is False


# ---------------------------------------------------------------------------
# Fix #0: executor unwrap inner Fusion result
# ---------------------------------------------------------------------------
# Bug observado via trace (porta-figurinhas WC2026): adapter Fusion HTTP
# devolvia ok=true na camada de transporte mesmo com ok=false interno
# stringificado em ``message``. Ver _unwrap_inner_fusion_result.


def test_unwrap_inner_fusion_result_promotes_inner_failure() -> None:
    from app.modeling.executor import _unwrap_inner_fusion_result

    output = {
        "ok": True,
        "tool_name": "fusion.add_rectangle",
        "transport": "http",
        "message": (
            '{"error_code": "fusion.sketch_not_found", '
            '"message": "Sketch não encontrado.", '
            '"ok": false, "retryable": true, "software": "fusion"}'
        ),
    }
    result = _unwrap_inner_fusion_result(output)
    assert result["ok"] is False
    assert result["error_code"] == "fusion.sketch_not_found"
    assert result["message"] == "Sketch não encontrado."
    assert result["retryable"] is True


def test_unwrap_inner_fusion_result_preserves_success() -> None:
    """Quando o inner indica ok:true, mantém o output como veio."""

    from app.modeling.executor import _unwrap_inner_fusion_result

    output = {
        "ok": True,
        "message": '{"ok": true, "sketch_name": "TF_Sketch"}',
    }
    result = _unwrap_inner_fusion_result(output)
    assert result["ok"] is True
    # Não promove nada porque inner também está ok.
    assert "error_code" not in result


def test_unwrap_inner_fusion_result_idempotent_for_direct_failures() -> None:
    """Outputs já no formato direto (ok=False externo) não são alterados."""

    from app.modeling.executor import _unwrap_inner_fusion_result

    output = {
        "ok": False,
        "error_code": "mcp.stdio_server_error",
        "message": "stdio falhou",
    }
    result = _unwrap_inner_fusion_result(output)
    assert result is output  # mesma instância — short-circuit


def test_unwrap_inner_fusion_result_ignores_non_json_message() -> None:
    """Mensagens em texto puro não viram parse acidentalmente."""

    from app.modeling.executor import _unwrap_inner_fusion_result

    output = {"ok": True, "message": "tool executou com sucesso"}
    result = _unwrap_inner_fusion_result(output)
    assert result["ok"] is True


def test_tracer_explicit_flush_drains_partial_buffer() -> None:
    """Bug observado em trace 'modele um prisma' (19/05): planos pequenos
    com menos eventos que ``batch_size`` ficavam no buffer indefinidamente
    porque ninguem chamava flush() externamente apos a execucao. O modal
    de diagnostico ficava vazio mesmo com execucao bem sucedida.

    Regressao test: tracer com batch_size=100 (muito maior que volume real)
    + 5 events emitidos + flush explicito = 5 events na store. Sem o flush,
    o buffer ficaria preso.
    """

    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    tracer.start_trace(session_id="sess", plan_id="plan-123")
    for i in range(5):
        tracer.record(
            f"executor.step_{i}",
            source=ModelingTraceSource.backend,
            payload={"seq": i},
        )
    # Antes do flush: nada no store (buffer < batch_size).
    assert len(store.events) == 0
    tracer.flush()
    # Apos flush: tudo persistido.
    # 1 (trace.started) + 5 (record loops) = 6
    assert len(store.events) == 6
    types = [e.event_type for e in store.events]
    assert types.count("executor.step_0") == 1
    assert types.count("executor.step_4") == 1


# ---------------------------------------------------------------------------
# PR#28 review regressões
# ---------------------------------------------------------------------------


def test_close_trace_removes_buffer_and_flushes() -> None:
    """PR#28 issue 2: close_trace deve flushar e remover o buffer.

    Sem isso, cada request acumula uma entrada permanente em ``_buffers``.
    """

    from app.modeling.observability import ModelingTracer

    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100)
    trace_id = tracer.start_trace(session_id="sess-1")
    tracer.record(
        "executor.step_started",
        source=ModelingTraceSource.backend,
        payload={"seq": 1},
    )
    # Buffer existe antes do close.
    assert trace_id in tracer._buffers
    tracer.close_trace()
    # Buffer foi removido E os eventos chegaram na store.
    assert trace_id not in tracer._buffers
    assert any(e.event_type == "executor.step_started" for e in store.events)


def test_buffers_evict_fifo_when_capacity_exceeded() -> None:
    """PR#28 issue 2: bounded capacity FIFO se close_trace nunca for chamado.

    Defesa em profundidade — em produção close_trace é wired, mas se
    algum caller esquecer não pode vazar memória ilimitada.
    """

    from app.modeling.observability import ModelingTracer

    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=100, max_buffers=3)
    # 3 traces ocupam o cap, o 4o evicta o primeiro (FIFO).
    for i in range(4):
        tracer.start_trace(session_id=f"sess-{i}")
        tracer.record(f"event-{i}", source=ModelingTraceSource.backend, payload={"i": i})
    assert len(tracer._buffers) == 3
    # O primeiro trace foi flushado durante a eviccão — store tem seus eventos.
    types_in_store = [e.event_type for e in store.events]
    assert "event-0" in types_in_store


def test_buffer_eviction_flushes_outside_global_lock() -> None:
    """PR#28 follow-up: flush de eviction nao segura ``_buffers_lock``."""

    class _LockAwareStore(_FakeStore):
        def __init__(self) -> None:
            super().__init__()
            self.tracer: ModelingTracer | None = None
            self.flush_lock_states: list[bool] = []

        def record_trace_events_bulk(self, events: list[ModelingTraceEvent]) -> None:
            assert self.tracer is not None
            self.flush_lock_states.append(self.tracer._buffers_lock.locked())
            super().record_trace_events_bulk(events)

    store = _LockAwareStore()
    tracer = ModelingTracer(store=store, batch_size=100, max_buffers=1)
    store.tracer = tracer

    tracer.start_trace(session_id="sess-1")
    tracer.record("event-1", source=ModelingTraceSource.backend)
    tracer.start_trace(session_id="sess-2")

    assert store.flush_lock_states
    assert all(locked is False for locked in store.flush_lock_states)


def test_record_span_handles_cancellation_with_warn_event() -> None:
    """PR#28 issue 9: CancelledError (BaseException) também fecha o span.

    Antes, só ``Exception`` era capturado → spans cancelados ficavam orfãos
    (start sem .completed nem .failed).
    """

    from app.modeling.observability import ModelingTracer

    store = _FakeStore()
    tracer = ModelingTracer(store=store, batch_size=1)
    tracer.start_trace(session_id="sess")

    class _Cancel(BaseException):
        """Mimics asyncio.CancelledError (BaseException, not Exception)."""

    # Sub-classe customizada — verifica que o catch de BaseException pega.
    _Cancel.__name__ = "CancelledError"

    with pytest.raises(_Cancel):
        with tracer.record_span("planner.llm_request"):
            raise _Cancel()
    tracer.close_trace()
    event_types = [e.event_type for e in store.events]
    assert "planner.llm_request.cancelled" in event_types
    cancelled_event = next(
        e for e in store.events if e.event_type == "planner.llm_request.cancelled"
    )
    assert cancelled_event.level == ModelingTraceLevel.warn


def test_fusion_script_template_compiles_for_every_tool() -> None:
    """O template f-string de fusion_mcp_scripts é fonte de bugs sutis.

    Cada literal ``{`` no template precisa ser ``{{`` ou Python interpreta
    como interpolação. Bug real introduzido em comentário do _set_parameter
    (Fix #1): `# (a) singular legado: {"name": "X", "expression": "10mm"}`
    fazia o script renderizado falhar em runtime com::

        Invalid format specifier ' "X", "expression": "10mm"' for object
        of type 'str'

    Este teste compila o script para todos os tools allowlistados e falha
    se algum não é Python sintaticamente válido. Não exercita o adapter
    real, só o gerador de scripts.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import (
        FUSION_SCRIPT_TOOLS,
        build_autodesk_fusion_script,
    )

    # Args que cobrem tipos primários: string, int, float, bool, dict aninhado.
    sample_args = {
        "name": "MyDesign",
        "binary": True,
        "thickness_mm": 2.5,
        "parameters": {"album_width_mm": 210, "spine_width_mm": 30},
        "sketch": "CoverSketch",
        "plane": "XY",
        "operation": "new_body",
    }

    for tool_name in FUSION_SCRIPT_TOOLS:
        script = build_autodesk_fusion_script(tool_name=tool_name, arguments=sample_args)
        try:
            ast.parse(script)
        except SyntaxError as exc:  # pragma: no cover - test failure path
            raise AssertionError(
                f"Script para {tool_name} não é Python válido: {exc}\n\n"
                f"Trecho problemático:\n"
                f"{script[max(0, (exc.offset or 0) - 100) : (exc.offset or 0) + 100]}"
            ) from exc


def test_onda_a_tools_are_registered_and_compile() -> None:
    """Onda A: as 4 tools novas (polygon, line, arc, revolve) estão na
    allowlist do adapter, no registry, e geram scripts Python válidos com
    args realistas (incluindo expressões paramétricas e listas de pontos).
    """

    import ast

    from app.modeling.fusion_mcp_scripts import (
        FUSION_SCRIPT_TOOLS,
        build_autodesk_fusion_script,
    )
    from app.modeling.tool_registry import FUSION_TOOLS

    onda_a = [
        "fusion.add_polygon",
        "fusion.add_line",
        "fusion.add_arc",
        "fusion.revolve_profile",
    ]
    for tool in onda_a:
        assert tool in FUSION_SCRIPT_TOOLS, f"{tool} ausente em FUSION_SCRIPT_TOOLS"
        assert tool in FUSION_TOOLS, f"{tool} ausente no tool_registry"

    cases = {
        "fusion.add_polygon": {"sketch": "s", "sides": 6, "radius_mm": 25, "center_mm": [0, 0]},
        "fusion.add_line": {
            "sketch": "s",
            "points_mm": [[0, 0], [10, 0], [10, 10]],
            "closed": True,
        },
        "fusion.add_arc": {
            "sketch": "s",
            "center_mm": [0, 0],
            "start_mm": [10, 0],
            "sweep_deg": 180,
        },
        "fusion.revolve_profile": {"sketch": "s", "axis": "y", "angle_deg": 360},
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)  # levanta SyntaxError se o template quebrou
        assert f'TOOL_NAME = "{tool}"' in script


def test_onda_b_primitives_are_registered_and_compile() -> None:
    """Onda B: as 4 primitivas diretas (box, cylinder, sphere, cone) estão
    na allowlist do adapter, no registry, e geram scripts Python válidos.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import (
        FUSION_SCRIPT_TOOLS,
        build_autodesk_fusion_script,
    )
    from app.modeling.tool_registry import FUSION_TOOLS

    cases = {
        "fusion.add_box": {"width_mm": 40, "depth_mm": 20, "height_mm": 10},
        "fusion.add_cylinder": {"diameter_mm": 30, "height_mm": 50},
        "fusion.add_sphere": {"diameter_mm": 50},
        "fusion.add_cone": {"base_diameter_mm": 40, "top_diameter_mm": 0, "height_mm": 60},
    }
    for tool, args in cases.items():
        assert tool in FUSION_SCRIPT_TOOLS, f"{tool} ausente em FUSION_SCRIPT_TOOLS"
        assert tool in FUSION_TOOLS, f"{tool} ausente no tool_registry"
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_primitives_name_the_body_not_only_the_sketch() -> None:
    """Regressão (gate caixa+tampa): add_box/cylinder/sphere/cone passam a
    nomear o CORPO com o ``name`` dado (antes nomeavam só o sketch → o body
    ficava Body1/Body2 e shell/fillet por nome davam fusion.body_not_found).
    O script gerado precisa setar o nome do body e devolver body_name.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        "fusion.add_box": {"name": "BoxOuter", "dimensions_mm": [60, 40, 30]},
        "fusion.add_cylinder": {"name": "Pino", "diameter_mm": 10, "height_mm": 20},
        "fusion.add_sphere": {"name": "Bola", "diameter_mm": 30},
        "fusion.add_cone": {"name": "Bico", "base_diameter_mm": 20, "height_mm": 30},
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert "_unique_body_name" in script, tool
        assert "feat.bodies.item(0).name" in script, tool
        assert '"body_name"' in script, tool


def test_onda_c_features_are_registered_and_compile() -> None:
    """Onda C: fillet/chamfer/shell/hole estão na allowlist, no registry
    (categoria mutative) e geram scripts Python válidos.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import (
        FUSION_SCRIPT_TOOLS,
        build_autodesk_fusion_script,
    )
    from app.modeling.tool_registry import TOOL_REGISTRY, ToolCategory

    cases = {
        "fusion.fillet_edges": {"radius_mm": 2, "edge_selector": "top"},
        "fusion.chamfer_edges": {"distance_mm": 1, "edge_selector": "all"},
        "fusion.shell_body": {"thickness_mm": 2, "open_faces": "top"},
        "fusion.hole": {"diameter_mm": 5, "position_mm": [0, 0]},
    }
    for tool, args in cases.items():
        assert tool in FUSION_SCRIPT_TOOLS, f"{tool} ausente em FUSION_SCRIPT_TOOLS"
        assert TOOL_REGISTRY[tool].category == ToolCategory.mutative
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_primitives_support_origin_z_offset() -> None:
    """Posicionamento (gate caixa+tampa): primitivas ganham origin_mm com z via
    _translate_body (no-op quando offset zero → compat). Permite empilhar/afastar
    corpos sem ficarem sobrepostos na origem.
    """

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    for tool in (
        "fusion.add_box",
        "fusion.add_cylinder",
        "fusion.add_sphere",
        "fusion.add_cone",
    ):
        script = build_autodesk_fusion_script(tool_name=tool, arguments={})
        assert "_translate_body(" in script, tool
        assert "_xyz_mm(" in script, tool


def test_query_timeline_reads_timeline_and_params() -> None:
    """T3.1 (Fase 3): tool read-only que lê a timeline (features/ordem/supressão)
    + os user parameters atuais — insumo da reconciliação (T3.2/T3.3) antes de
    planejar uma edição (estado real do Fusion, não o histórico desatualizado).
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script
    from app.modeling.tool_registry import is_read_only

    script = build_autodesk_fusion_script(tool_name="fusion.query_timeline", arguments={})
    ast.parse(script)
    assert "design.timeline" in script
    assert "userParameters" in script
    assert '"timeline"' in script and '"parameters"' in script
    assert is_read_only("fusion.query_timeline")


def test_rollback_timeline_is_destructive_and_not_planner_visible() -> None:
    """T3.6: rollback da última edição apaga features da timeline após um ponto.
    Destrutivo e FORA do planner (undo do usuário via botão, nunca planejado).
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script
    from app.modeling.tool_registry import PLANNER_TOOLSET, TOOL_REGISTRY, ToolCategory

    script = build_autodesk_fusion_script(tool_name="fusion.rollback_timeline", arguments={})
    ast.parse(script)
    assert "deleteMe" in script and "timeline" in script
    assert TOOL_REGISTRY["fusion.rollback_timeline"].category == ToolCategory.destructive
    assert "fusion.rollback_timeline" not in PLANNER_TOOLSET


def test_move_body_supports_rotation() -> None:
    """Fase 4/G3: move_body completa translação com rotação (rotation_deg + axis
    em torno de center_mm). Backward-compat: translation_mm-só continua válido."""

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    script = build_autodesk_fusion_script(
        tool_name="fusion.move_body",
        arguments={"body_ref": "Body1", "rotation_deg": 90, "axis": "z"},
    )
    ast.parse(script)
    assert "setToRotation" in script
    assert "rotation_deg" in script and "center_mm" in script
    # exige ao menos um movimento (translação OU rotação)
    assert "translation_mm e/ou rotation_deg" in script


def test_pilot_tools_return_dimensions_mm_for_verifier() -> None:
    """C (verifier): extrude + primitivas fazem read-back e devolvem
    dimensions_mm (bbox) no output, p/ o verifier do loop comparar com
    expected_dimensions_mm e auto-corrigir (ex.: cut que consome a peça → bbox 0).
    """

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    for tool in (
        "fusion.extrude_profile",
        "fusion.revolve_profile",
        "fusion.sweep_profile",
        "fusion.loft_profiles",
        "fusion.add_box",
        "fusion.add_cylinder",
        "fusion.add_sphere",
        "fusion.add_cone",
        "fusion.hole",
        "fusion.shell_body",
        "fusion.fillet_edges",
        "fusion.chamfer_edges",
        "fusion.combine_bodies",
    ):
        script = build_autodesk_fusion_script(tool_name=tool, arguments={})
        assert '"dimensions_mm"' in script, tool
        assert "_body_dims_mm(" in script, tool


def test_body_not_found_error_lists_available_bodies() -> None:
    """Gate caixa+tampa: o corretor ficava às cegas em fusion.body_not_found
    (referenciou 'Outer_Box', corpo era 'Box'). O script gerado deve listar os
    corpos disponíveis na mensagem de erro para o corretor se autocorrigir.
    """

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    script = build_autodesk_fusion_script(
        tool_name="fusion.shell_body",
        arguments={"thickness_mm": 2, "body": "Outer_Box"},
    )
    assert "Corpos disponiveis:" in script


def test_fillet_chamfer_warn_on_unrecognized_edge_arg() -> None:
    """Regressão (gate placa+furo+fillet): fillet/chamfer NÃO podem cair mudo
    em edge_selector='all' quando o planner manda a intenção de aresta numa
    chave não reconhecida (ex.: edge_ids_from_previous_query com texto livre) —
    foi assim que o fillet arredondou as arestas do furo contra o plano. O
    script gerado precisa conter o guard que torna esse fallback visível no
    trace (WARN), em vez de silencioso.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    for tool in ("fusion.fillet_edges", "fusion.chamfer_edges"):
        script = build_autodesk_fusion_script(
            tool_name=tool,
            arguments={
                "radius_mm": 2,
                "distance_mm": 1,
                "edge_ids_from_previous_query": "so as externas, nao o furo",
            },
        )
        ast.parse(script)
        assert "args de aresta nao reconhecidos" in script, tool
        assert "edge_warn" in script, tool


def test_onda_def_tools_are_registered_and_compile() -> None:
    """Ondas D-F: replicação, sweeps, modificação direta. Verifica allowlist,
    categorias de risco corretas (combine=high_risk, delete=destructive) e
    que os scripts compilam com args realistas.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import (
        FUSION_SCRIPT_TOOLS,
        build_autodesk_fusion_script,
    )
    from app.modeling.tool_registry import TOOL_REGISTRY, ToolCategory

    cases = {
        # Onda D
        "fusion.pattern_rectangular": (
            {"count_x": 3, "spacing_x_mm": 20, "count_y": 2, "spacing_y_mm": 15},
            ToolCategory.mutative,
        ),
        "fusion.pattern_circular": (
            {"count": 6, "axis": "z", "total_angle_deg": 360},
            ToolCategory.mutative,
        ),
        "fusion.mirror_feature": ({"plane": "yz"}, ToolCategory.mutative),
        "fusion.combine_bodies": (
            {"target_ref": "Body1", "tool_refs": ["Body2"], "operation": "cut"},
            ToolCategory.high_risk,
        ),
        # Onda E
        "fusion.loft_profiles": (
            {"profiles": ["s1", "s2"], "operation": "new_body"},
            ToolCategory.mutative,
        ),
        "fusion.sweep_profile": (
            {"profile": "prof", "path": "path", "operation": "new_body"},
            ToolCategory.mutative,
        ),
        "fusion.add_construction_plane": (
            {"base": "xy", "offset_mm": 10},
            ToolCategory.additive,
        ),
        "fusion.add_spline": (
            {"sketch": "s", "points_mm": [[0, 0], [10, 5], [20, 0]]},
            ToolCategory.additive,
        ),
        # Onda F
        "fusion.move_body": (
            {"body_ref": "Body1", "translation_mm": [10, 0, 5]},
            ToolCategory.mutative,
        ),
        "fusion.scale_body": ({"body_ref": "Body1", "factor": 2.0}, ToolCategory.mutative),
        "fusion.delete_body": ({"body_ref": "Body1"}, ToolCategory.destructive),
    }
    for tool, (args, expected_category) in cases.items():
        assert tool in FUSION_SCRIPT_TOOLS, f"{tool} ausente em FUSION_SCRIPT_TOOLS"
        assert TOOL_REGISTRY[tool].category == expected_category, (
            f"{tool} deveria ser {expected_category}"
        )
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_schema_drift_arc_line_sketch_revolve_aliases() -> None:
    """Schema drift do teste real da bola (20/05): create_sketch aceita
    'sketch' como nome; add_arc aceita forma polar (center+radius+angles);
    add_line aceita start_mm+end_mm; revolve aceita 'result'. Os scripts
    precisam compilar com essas formas.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        "fusion.create_sketch": {"plane": "XY", "sketch": "profile_sketch"},
        "fusion.add_arc": {
            "sketch": "profile_sketch",
            "center_mm": [0, 0],
            "radius_mm": 110,
            "start_angle_deg": 0,
            "end_angle_deg": 180,
        },
        "fusion.add_line": {
            "sketch": "profile_sketch",
            "start_mm": [-110, 0],
            "end_mm": [110, 0],
            "closed": True,
        },
        "fusion.revolve_profile": {
            "sketch": "profile_sketch",
            "angle_deg": 360,
            "result": "new_body",
        },
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_pattern_shell_accept_llm_aliases() -> None:
    """Schema drift do 2o teste da bola (20/05): pattern_circular aceita
    occurrences/quantity + angle_deg; shell_body aceita faces + body_name;
    tools de body aceitam body_name. Scripts precisam compilar.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        "fusion.pattern_circular": {
            "body_name": "Body1",
            "axis": "Z",
            "angle_deg": 360,
            "occurrences": 12,
        },
        "fusion.pattern_rectangular": {
            "body_name": "Body1",
            "occurrences_x": 3,
            "spacing_x_mm": 20,
            "occurrences_y": 2,
            "spacing_y_mm": 15,
        },
        "fusion.shell_body": {"body_name": "Body1", "faces": "all", "thickness_mm": 2.5},
        "fusion.fillet_edges": {"body_name": "Body1", "radius_mm": 2},
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_g1_2_and_hole_v2_scripts_compile() -> None:
    """G1.2 (sketch dims paramétricas guarded em rectangle/circle) e G3
    hole v2 (counterbore). Scripts compilam com args param e counterbore.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        # G1.2: dimensão amarrada a parâmetro
        "fusion.add_rectangle": {"sketch": "s", "width_mm": "box_w_mm", "height_mm": "box_h_mm"},
        "fusion.add_circle": {"sketch": "s", "diameter_mm": "bore_mm"},
        # G3: hole counterbore
        "fusion.hole": {
            "diameter_mm": 5,
            "position_mm": [0, 0],
            "type": "counterbore",
            "counterbore_diameter_mm": 10,
            "counterbore_depth_mm": 3,
        },
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_onda9_rest_scripts_compile() -> None:
    """Onda 9 restante: query_geometry (G2.2), edge_ids/face_ids,
    result_name (G2.3), add_ellipse/add_slot/split_body (G3). Compilam.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script
    from app.modeling.tool_registry import TOOL_REGISTRY, ToolCategory

    cases = {
        "fusion.query_geometry": ({"limit": 30}, ToolCategory.read_only),
        "fusion.add_ellipse": (
            {"sketch": "s", "major_mm": 40, "minor_mm": 20},
            ToolCategory.additive,
        ),
        "fusion.add_slot": (
            {"sketch": "s", "length_mm": 40, "width_mm": 10},
            ToolCategory.additive,
        ),
        "fusion.split_body": ({"body_name": "Body1", "plane": "xy"}, ToolCategory.mutative),
        # G2.2 index-based selection + G2.3 result_name
        "fusion.fillet_edges": ({"body_name": "Body1", "radius_mm": 2, "edge_ids": [0, 3]}, None),
        "fusion.extrude_profile": (
            {"sketch": "s", "distance_mm": 10, "result_name": "Tower"},
            None,
        ),
    }
    for tool, (args, category) in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script
        if category is not None:
            assert TOOL_REGISTRY[tool].category == category


def test_g1_g2_g5_scripts_compile() -> None:
    """G1.1 (parametrização), G2.1 (selectors finos), G5 (fallback de API):
    os scripts precisam compilar com args que exercitam os novos caminhos —
    distâncias como nome de parâmetro, selectors de orientação/tamanho.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        # G1.1: distancia como referencia a parametro (vinculo)
        "fusion.extrude_profile": {"sketch": "s", "distance_mm": "height_mm"},
        "fusion.fillet_edges": {"radius_mm": "edge_radius_mm", "edge_selector": "longest"},
        "fusion.chamfer_edges": {"distance_mm": 2, "edge_selector": "top"},
        "fusion.shell_body": {"thickness_mm": "wall_mm", "open_faces": "+z"},
        # G2.1: selectors finos
        "fusion.hole": {"diameter_mm": 5, "position_mm": [0, 0]},
        # G5: move/scale com fallback de versao
        "fusion.move_body": {"body_name": "Body1", "translation_mm": [10, 0, 5]},
        "fusion.scale_body": {"body_name": "Body1", "factor": 2},
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_add_circle_accepts_aliases() -> None:
    """Quick fix: add_circle aceita circle_diameter_mm e radius_mm além de
    diameter_mm. Verifica que o script compila com cada alias.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    for args in (
        {"sketch": "s", "diameter_mm": 20},
        {"sketch": "s", "circle_diameter_mm": 20},
        {"sketch": "s", "radius_mm": 10},
    ):
        script = build_autodesk_fusion_script(tool_name="fusion.add_circle", arguments=args)
        ast.parse(script)


def test_schema_drift_param_expression_syntax() -> None:
    """Drift do trace placa-parametrizada (mt_019e46942241): o LLM emite
    valores em ``value_mm`` no set_parameter, chaves dimensionais sem sufixo
    (width/height/radius/distance) e sintaxe de expressao do Fusion com "="
    lider (=plate_width, =thickness, =hole_diameter/2). Os scripts devem
    compilar com cada um desses formatos.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        # set_parameter com value_mm em vez de expression
        "fusion.set_parameter": {"name": "plate_width", "value_mm": 80},
        # add_rectangle com chaves sem sufixo + =param
        "fusion.add_rectangle": {
            "width": "=plate_width",
            "height": "=plate_height",
            "centered": True,
        },
        # extrude_profile com distance sem sufixo + =param
        "fusion.extrude_profile": {"sketch": "s", "distance": "=thickness"},
        # add_circle com radius sem sufixo + =expressao composta
        "fusion.add_circle": {"sketch": "s", "radius": "=hole_diameter/2"},
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script


def test_schema_drift_add_box_dimensions_list() -> None:
    """Drift do trace placa (mt_019e46cf2726): o LLM manda as 3 medidas do
    box numa lista unica (dimensions_mm=[w,d,h]) com chave extra ``primitive``
    e ``origin_mm`` como canto, em vez de width_mm/depth_mm/height_mm. O
    script deve compilar com esse formato.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    for args in (
        {
            "name": "PlateBody",
            "origin_mm": [0, 0, 0],
            "primitive": "box",
            "dimensions_mm": [80, 60, 5],
        },
        {"size_mm": [10, 20, 30]},
        {"width_mm": 10, "depth_mm": 20, "height_mm": 30},
    ):
        script = build_autodesk_fusion_script(tool_name="fusion.add_box", arguments=args)
        ast.parse(script)
        assert 'TOOL_NAME = "fusion.add_box"' in script


def test_schema_drift_param_suffix_convention() -> None:
    """Drift do trace placa (mt_019e46d6dc46): o LLM expressa vinculos
    parametricos com o sufixo ``_param`` carregando o nome do parametro
    (width_param/height_param/distance_param/diameter_param). O dispatch
    normaliza <base>_param -> <base>_mm; os scripts devem compilar e o helper
    _normalize_param_suffix deve estar presente no template.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = {
        "fusion.add_rectangle": {
            "sketch": "s",
            "centered": True,
            "width_param": "plate_length",
            "height_param": "plate_width",
        },
        "fusion.extrude_profile": {
            "sketch": "s",
            "operation": "new_body",
            "distance_param": "plate_thickness",
        },
        "fusion.add_circle": {
            "sketch": "s",
            "center_mm": [0, 0],
            "diameter_param": "hole_diameter",
        },
    }
    for tool, args in cases.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert f'TOOL_NAME = "{tool}"' in script
        assert "_normalize_param_suffix" in script


def test_hole_uses_circle_profile_selector() -> None:
    """Bug do teste real da placa (mt_019e46e06f3b): o sketch do furo criado
    SOBRE a face da peca gera 2 profiles (disco + anel); pegar item(0) podia
    pegar o anel e o CUT consumia a peca, deixando so o plug. O hole deve usar
    o seletor por area do circulo (_profile_for_circle), nao profiles.item(0).
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    script = build_autodesk_fusion_script(
        tool_name="fusion.hole",
        arguments={"diameter_mm": 10, "position_mm": [0, 0], "through": True},
    )
    ast.parse(script)
    assert "_profile_for_circle" in script
    # o caminho do furo nao deve mais cair no profiles.item(0) cego dentro do
    # createInput do cut (o helper substitui a selecao).
    assert "_profile_for_circle(sketch, diameter_mm / 20.0)" in script


def test_extrude_profile_uses_profile_selector() -> None:
    """Gate real (m3d_plan_2f7aeff0): ``extrude_profile`` extrudava sempre
    ``profiles.item(0)``. Num sketch com 2 profiles (retangulo + circulo
    coplanares) um ``operation=cut`` consumia a placa inteira. Agora resolve o
    profile via ``_resolve_profile_selection`` (profile_index / profile_diameter_mm)
    e avisa quando um cut ambiguo cai no profiles[0] sem seletor.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    # cut do furo selecionando o profile pela area do circulo
    script = build_autodesk_fusion_script(
        tool_name="fusion.extrude_profile",
        arguments={
            "sketch": "s",
            "operation": "cut",
            "distance_mm": 5,
            "profile_diameter_mm": 10,
        },
    )
    ast.parse(script)
    assert "_resolve_profile_selection" in script
    # não cai mais no item(0) cego dentro do createInput do extrude.
    assert "createInput(profile, operation_map[operation])" in script

    # selecao por indice tambem compila
    script_idx = build_autodesk_fusion_script(
        tool_name="fusion.extrude_profile",
        arguments={
            "sketch": "s",
            "operation": "new_body",
            "distance_mm": 5,
            "profile_index": 1,
        },
    )
    ast.parse(script_idx)


def test_revolve_and_sweep_use_profile_selector() -> None:
    """Follow-up do gate: ``revolve_profile`` e ``sweep_profile`` também caíam em
    ``profiles.item(0)`` cego (mesmo risco do extrude num sketch multi-perfil).
    Agora usam ``_resolve_profile_selection``; os scripts compilam com
    ``profile_index``. (Primitivas e loft ficam de fora: sketch de perfil único
    ou seção por sketch separado.)
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    cases = (
        (
            "fusion.revolve_profile",
            {"sketch": "s", "axis": "y", "angle_deg": 360, "profile_index": 0},
        ),
        (
            "fusion.sweep_profile",
            {"profile": "prof", "path": "path", "profile_index": 1},
        ),
    )
    for tool, args in cases:
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)
        assert "_resolve_profile_selection" in script


def test_open_design_reuses_active_design() -> None:
    """P3: open_design deve REUSAR o design ativo por padrão (não recriar um
    Untitled e zerar o modelo); só cria novo com new_document/reset/force_new.
    Validação de runtime depende do Fusion real; aqui garantimos que o script
    compila e contém a lógica de reuso/force_new.
    """

    import ast

    from app.modeling.fusion_mcp_scripts import build_autodesk_fusion_script

    for args in ({}, {"new_document": True}, {"reset": True}):
        script = build_autodesk_fusion_script(tool_name="fusion.open_design", arguments=args)
        ast.parse(script)
        assert 'TOOL_NAME = "fusion.open_design"' in script
    # A lógica de reuso e de force_new precisa estar presente no template.
    assert "force_new" in script
    assert "activeProduct" in script
    assert '"reused"' in script


def test_unwrap_inner_fusion_result_captures_traceback() -> None:
    """Traceback do inner result vai parar em host_details para debug."""

    from app.modeling.executor import _unwrap_inner_fusion_result

    output = {
        "ok": True,
        "message": (
            '{"ok": false, "error_code": "fusion.script_failed", '
            '"message": "boom", "traceback": "Traceback (most recent call last):..."}'
        ),
    }
    result = _unwrap_inner_fusion_result(output)
    assert result["ok"] is False
    assert "inner_traceback" in result["host_details"]
