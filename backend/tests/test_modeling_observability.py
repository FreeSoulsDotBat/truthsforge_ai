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
        "fusion.add_line": {"sketch": "s", "points_mm": [[0, 0], [10, 0], [10, 10]], "closed": True},
        "fusion.add_arc": {"sketch": "s", "center_mm": [0, 0], "start_mm": [10, 0], "sweep_deg": 180},
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
        "fusion.add_ellipse": ({"sketch": "s", "major_mm": 40, "minor_mm": 20}, ToolCategory.additive),
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
