"""Regressão: retry de plano ``failed`` precisa ser IDEMPOTENTE (review PR#46).

Bug: ``ModelingAgentLoop.run`` e ``ModelingExecutorService.execute_plan`` só
pulavam passo com ``step.error`` ou aprovação pendente — sem guarda de
``status == completed``. Num plano que falhou no passo N, o retry re-executava
1..N-1 (``add_box`` recria corpos; ``_open_design`` reusa o design ativo →
geometria DUPLICADA) e, pior, BLOQUEAVA o próprio passo N (que carrega
``step.error``). Agora, nos DOIS caminhos:

- passo ``completed`` é PULADO (resultado/proveniência preservados, fora de
  executed/blocked — sem duplicar histórico);
- passo ``failed`` re-executa do zero (erro anterior limpo) — é o alvo do retry;
- passo com ``error`` mas status ≠ ``failed`` (policy/blocklist/rejeição)
  continua bloqueado (bloqueio estrutural, não desfecho de execução);
- passo ``failed`` com ``approval_required`` exige RE-aprovação (a falha
  consumiu a aprovação — fail-safe da constituição).

Cobre também a unificação do gate de execução (``ensure_plan_executable`` com
``allow_completed`` para o retry de chat em ``editing``).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.contracts import (
    ModelingPlan,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)
from app.modeling.agent_loop import ModelingAgentLoop
from app.modeling.executor import ModelingExecutorService, _StepOutcome
from app.modeling.service import ModelingPlanNotExecutable, ensure_plan_executable

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


def _scripted_outcome(step: ModelingPlanStep, ok: bool) -> _StepOutcome:
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


class _ScriptedLoopExecutor:
    """Mimics ModelingExecutorService p/ o loop agêntico (1 decisão por passo)."""

    def __init__(self, store: _FakeStore, decide) -> None:
        self.store = store
        self._tracer = _FakeTracer()
        self.decide = decide
        self.calls: list[tuple[str, bool]] = []

    def _execute_single_step(self, step: ModelingPlanStep, *, plan: ModelingPlan) -> _StepOutcome:
        ok = bool(self.decide(step))
        self.calls.append((step.tool_name, ok))
        return _scripted_outcome(step, ok)


class _ScriptedLinearExecutor(ModelingExecutorService):
    """Executor REAL (caminho ``execute_plan``) com o dispatch de passo scriptado."""

    def __init__(self, store: _FakeStore, decide) -> None:
        super().__init__(store=store, mcp_client=None, snapshots=None, artifacts=None)
        self.decide = decide
        self.calls: list[tuple[str, bool]] = []

    def _execute_single_step(
        self, step: ModelingPlanStep, *, plan: ModelingPlan, from_expansion: bool = False
    ) -> _StepOutcome:
        ok = bool(self.decide(step))
        self.calls.append((step.tool_name, ok))
        return _scripted_outcome(step, ok)


def _step(
    seq: int,
    tool_name: str,
    *,
    status: ModelingStepStatus = ModelingStepStatus.approved,
    error: str | None = None,
    output_json: dict[str, Any] | None = None,
    approval_required: bool = False,
) -> ModelingPlanStep:
    return ModelingPlanStep(
        seq=seq,
        title=f"Etapa {seq}",
        software=ModelingSoftware.fusion,
        tool_name=tool_name,
        risk_level=ModelingRiskLevel.low,
        approval_required=approval_required,
        status=status,
        error=error,
        output_json=output_json or {},
        input_json={},
    )


def _retry_plan(*steps: ModelingPlanStep) -> ModelingPlan:
    """Plano como fica APÓS uma execução que falhou (retry explícito)."""

    return ModelingPlan(
        prompt="peça de teste (retry)",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.failed,
        steps=list(steps),
    )


_DONE_OUTPUT = {"ok": True, "body_name": "Caixa", "_provenance": {"created": ["Caixa"]}}


def _completed_failed_failed_steps() -> tuple[ModelingPlanStep, ...]:
    return (
        _step(
            1,
            "fusion.add_box",
            status=ModelingStepStatus.completed,
            output_json=dict(_DONE_OUTPUT),
        ),
        _step(2, "fusion.fillet_edges", status=ModelingStepStatus.completed),
        _step(3, "fusion.hole", status=ModelingStepStatus.failed, error="falhou na 1ª execução"),
    )


# ------------------------------------------------------------------ loop agêntico


def test_agent_loop_retry_runs_only_the_failed_step() -> None:
    """[completed, completed, failed] re-executado → SÓ o failed roda."""

    store = _FakeStore()
    executor = _ScriptedLoopExecutor(store, decide=lambda step: True)
    plan = _retry_plan(*_completed_failed_failed_steps())

    result = ModelingAgentLoop(executor).run(plan)

    # Só o passo 3 (failed) re-executou — add_box/fillet NÃO recriaram geometria.
    assert executor.calls == [("fusion.hole", True)]
    assert result.executed_step_ids == [plan.steps[2].id]
    # Passos completed preservam resultado/proveniência originais.
    assert result.plan.steps[0].output_json == _DONE_OUTPUT
    assert result.plan.steps[0].status is ModelingStepStatus.completed
    # O passo retried virou completed com o erro antigo limpo; plano completa.
    assert result.plan.steps[2].status is ModelingStepStatus.completed
    assert result.plan.steps[2].error is None
    assert result.plan.status is ModelingPlanStatus.completed
    assert result.blocked_step_ids == []


def test_agent_loop_retry_of_fully_completed_plan_is_noop() -> None:
    """Re-executar plano todo ``completed`` = no-op (base do allow_completed)."""

    store = _FakeStore()
    executor = _ScriptedLoopExecutor(store, decide=lambda step: True)
    plan = ModelingPlan(
        prompt="peça pronta",
        software_choice=ModelingSoftware.fusion,
        status=ModelingPlanStatus.completed,
        steps=[
            _step(1, "fusion.add_box", status=ModelingStepStatus.completed),
            _step(2, "fusion.fillet_edges", status=ModelingStepStatus.completed),
        ],
    )

    result = ModelingAgentLoop(executor).run(plan)

    assert executor.calls == []  # nada re-executou
    assert result.executed_step_ids == []
    assert result.blocked_step_ids == []
    assert result.plan.status is ModelingPlanStatus.completed


def test_agent_loop_retry_blocks_failed_high_risk_until_reapproved() -> None:
    """Constituição: a falha consumiu a aprovação (status=failed ≠ approved); o
    retry de um passo high-risk NÃO auto-executa — exige re-aprovação humana."""

    store = _FakeStore()
    executor = _ScriptedLoopExecutor(store, decide=lambda step: True)
    plan = _retry_plan(
        _step(
            1,
            "fusion.combine_bodies",
            status=ModelingStepStatus.failed,
            error="falhou",
            approval_required=True,
        ),
    )

    result = ModelingAgentLoop(executor).run(plan)

    assert executor.calls == []  # não re-executou sem re-aprovação
    assert result.blocked_step_ids == [plan.steps[0].id]
    assert result.plan.status is ModelingPlanStatus.failed


def test_agent_loop_structural_error_block_still_holds() -> None:
    """Passo com ``error`` mas status ≠ failed (policy/blocklist) segue bloqueado
    — a abertura do retry vale SÓ para desfecho de execução (status=failed)."""

    store = _FakeStore()
    executor = _ScriptedLoopExecutor(store, decide=lambda step: True)
    plan = _retry_plan(
        _step(
            1,
            "fusion.execute_script",
            status=ModelingStepStatus.waiting_approval,
            error="Ferramenta bloqueada pela política local de modelagem 3D.",
        ),
        _step(2, "fusion.hole", status=ModelingStepStatus.failed, error="falhou"),
    )

    result = ModelingAgentLoop(executor).run(plan)

    assert executor.calls == [("fusion.hole", True)]
    assert plan.steps[0].id in result.blocked_step_ids


def test_agent_loop_orphan_running_step_reexecutes() -> None:
    """Decisão documentada: passo ``running`` órfão (teórico — hoje nenhum caminho
    persiste step como running) RE-EXECUTA: o desfecho da execução interrompida é
    desconhecido e congelar bloquearia o plano; duplicação eventual é acusada pelo
    read-back/auto-crítica (F8)."""

    store = _FakeStore()
    executor = _ScriptedLoopExecutor(store, decide=lambda step: True)
    plan = _retry_plan(_step(1, "fusion.add_box", status=ModelingStepStatus.running))

    result = ModelingAgentLoop(executor).run(plan)

    assert executor.calls == [("fusion.add_box", True)]
    assert result.plan.status is ModelingPlanStatus.completed


# ------------------------------------------------------------------ executor linear


def test_linear_executor_retry_runs_only_the_failed_step() -> None:
    """Mesma garantia no caminho do card (``execute_plan`` linear)."""

    store = _FakeStore()
    executor = _ScriptedLinearExecutor(store, decide=lambda step: True)
    plan = _retry_plan(*_completed_failed_failed_steps())

    result = executor.execute_plan(plan)

    assert executor.calls == [("fusion.hole", True)]
    assert result.executed_step_ids == [plan.steps[2].id]
    assert result.blocked_step_ids == []
    # Passos completed preservados como vieram (mesmo output/proveniência).
    assert result.plan.steps[0].output_json == _DONE_OUTPUT
    assert result.plan.steps[1].status is ModelingStepStatus.completed
    # Retry do failed concluiu; plano completa e persiste.
    assert result.plan.steps[2].status is ModelingStepStatus.completed
    assert result.plan.steps[2].error is None
    assert result.plan.status is ModelingPlanStatus.completed
    assert store.plans[plan.id].status is ModelingPlanStatus.completed


def test_linear_executor_retry_failure_keeps_plan_failed() -> None:
    """Se o retry do passo falho falhar de novo, o plano segue ``failed`` —
    nenhum completed re-executa no caminho."""

    store = _FakeStore()
    executor = _ScriptedLinearExecutor(store, decide=lambda step: False)
    plan = _retry_plan(*_completed_failed_failed_steps())

    result = executor.execute_plan(plan)

    assert executor.calls == [("fusion.hole", False)]
    assert result.plan.status is ModelingPlanStatus.failed
    assert result.plan.steps[0].output_json == _DONE_OUTPUT  # intocado


# ------------------------------------------------------------------ gate unificado


def _plan_with_status(status: ModelingPlanStatus) -> ModelingPlan:
    return ModelingPlan(
        prompt="gate",
        software_choice=ModelingSoftware.fusion,
        status=status,
        steps=[_step(1, "fusion.add_box")],
    )


def test_ensure_plan_executable_default_excludes_completed() -> None:
    """Caminho do card: anti-replay — ``completed`` não re-executa (409)."""

    with pytest.raises(ModelingPlanNotExecutable):
        ensure_plan_executable(_plan_with_status(ModelingPlanStatus.completed))


def test_ensure_plan_executable_allow_completed_for_chat_retry() -> None:
    """Fluxo de chat (retry em ``editing``): ``allow_completed=True`` libera o
    re-run — que com o skip idempotente de passos completed é um no-op seguro.
    Estados não-executáveis continuam barrados mesmo com a exceção ligada."""

    ensure_plan_executable(
        _plan_with_status(ModelingPlanStatus.completed), allow_completed=True
    )  # não levanta
    for status in (ModelingPlanStatus.waiting_approval, ModelingPlanStatus.rejected):
        with pytest.raises(ModelingPlanNotExecutable):
            ensure_plan_executable(_plan_with_status(status), allow_completed=True)
    # O fluxo de ponta-a-ponta do orchestrator (retry de completed em ``editing``)
    # é coberto por test_chat_orchestrator.py::test_execute_plan_retry_in_editing_
    # stays_editing, que agora passa por este MESMO gate (fonte única).
