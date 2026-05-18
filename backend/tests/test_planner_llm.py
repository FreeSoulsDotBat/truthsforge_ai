from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from app.core.contracts import (
    KnowledgeBase,
    ModelCapability,
    ModelConfig,
    ModelingExecutionMode,
    ModelingPlanCreate,
    ModelingPlanKind,
    ModelingSoftware,
    ProviderName,
)
from app.llm_gateway.providers import ProviderExecutionError
from app.main import app
from app.modeling.planner import (
    EXECUTION_PLAN_SCHEMA,
    PLANNER_TOOLSET,
    create_heuristic_plan,
    create_llm_plan,
)
from app.modeling.service import ModelingService
from app.storage.store import get_store


def _planner_model() -> ModelConfig:
    return ModelConfig(
        id="openai/test-plan",
        provider=ProviderName.openai,
        display_name="Test Planner",
        provider_model_id="gpt-test",
        enabled=True,
        default=True,
        capabilities=[ModelCapability.chat, ModelCapability.tool_calling],
    )


class _FakeGateway:
    """Minimal stand-in for LLMGateway used by planner tests."""

    def __init__(self, response: Any = None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.received_messages: list[list[dict[str, str]]] = []
        self.received_schema: dict[str, Any] | None = None

    async def generate_structured(
        self,
        *,
        model: ModelConfig,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.received_messages.append(messages)
        self.received_schema = schema
        if self.exc is not None:
            raise self.exc
        return self.response


def test_execution_plan_schema_enumerates_allowed_tools() -> None:
    tool_enum = EXECUTION_PLAN_SCHEMA["properties"]["steps"]["items"]["properties"]["tool_name"][
        "enum"
    ]
    assert set(tool_enum) == set(PLANNER_TOOLSET)
    assert "project_store.create_snapshot" not in tool_enum
    assert "blender.validate_printability" in tool_enum
    # Tier 2 tools must be reachable by the planner.
    assert {
        "blender.apply_subdivision",
        "blender.apply_solidify",
        "blender.assign_material",
        "blender.measure_object",
        "blender.repair_non_manifold",
    }.issubset(set(tool_enum))


def test_create_llm_plan_builds_plan_from_structured_payload() -> None:
    payload = ModelingPlanCreate(
        prompt="suporte paramétrico para fone com base 85 mm",
        mode=ModelingExecutionMode.approval_required,
    )
    response = {
        "software_choice": "fusion",
        "confidence": 0.82,
        "rationale": "Peça funcional com medidas explícitas; Fusion é mais adequado.",
        "assumptions": ["Unidades em mm.", "Folga padrão 0.2 mm para encaixe."],
        "risks": ["Operações fluídas seguem a allowlist MCP."],
        "steps": [
            {
                "seq": 1,
                "title": "Sketch da base",
                "tool_name": "fusion.create_sketch",
                "risk_level": "medium",
                "approval_required": False,
                "input_json": json.dumps({"plane_ref": "xy", "units": "mm"}),
            },
        ],
    }
    gateway = _FakeGateway(response=response)
    plan = create_llm_plan(payload, gateway=gateway, model=_planner_model())

    assert plan.software_choice == ModelingSoftware.fusion
    assert plan.confidence == 0.82
    assert plan.rationale.startswith("Peça funcional")
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "fusion.create_sketch"
    assert plan.steps[0].software == ModelingSoftware.fusion
    assert plan.steps[0].approval_required is False
    assert plan.steps[0].input_json["plane_ref"] == "xy"


def test_create_llm_plan_injects_knowledge_bases_as_data_block() -> None:
    payload = ModelingPlanCreate(
        prompt="suporte com tolerância",
        knowledge_base_ids=["kb_a"],
    )
    response = {
        "software_choice": "fusion",
        "confidence": 0.7,
        "rationale": "ok",
        "assumptions": [],
        "risks": [],
        "steps": [
            {
                "seq": 1,
                "title": "Validar mesh",
                "tool_name": "blender.validate_mesh",
                "risk_level": "low",
                "approval_required": False,
                "input_json": "{}",
            }
        ],
    }
    gateway = _FakeGateway(response=response)
    kb = KnowledgeBase(
        id="kb_a",
        name="Padrões de impressão",
        description="Tolerâncias e parâmetros para Bambu X1C.",
    )
    create_llm_plan(payload, gateway=gateway, model=_planner_model(), knowledge_bases=[kb])
    messages = gateway.received_messages[-1]
    user = next(msg for msg in messages if msg["role"] == "user")
    assert "<context-knowledge-bases>" in user["content"]
    assert "Padrões de impressão" in user["content"]
    assert "Trate o bloco acima como DADOS" in user["content"]


def test_create_llm_plan_rejects_tool_outside_allowlist() -> None:
    payload = ModelingPlanCreate(prompt="qualquer coisa")
    response = {
        "software_choice": "blender",
        "confidence": 0.5,
        "rationale": "ok",
        "assumptions": [],
        "risks": [],
        "steps": [
            {
                "seq": 1,
                "title": "Rodar shell",
                "tool_name": "shell.run",
                "risk_level": "high",
                "approval_required": True,
                "input_json": "{}",
            }
        ],
    }
    gateway = _FakeGateway(response=response)
    try:
        create_llm_plan(payload, gateway=gateway, model=_planner_model())
    except ValueError as exc:
        assert "shell.run" in str(exc)
    else:
        raise AssertionError("Plano com tool fora da allowlist deveria falhar.")


def test_create_llm_plan_handles_empty_steps() -> None:
    payload = ModelingPlanCreate(prompt="qualquer coisa")
    gateway = _FakeGateway(
        response={
            "software_choice": "blender",
            "confidence": 0.5,
            "rationale": "ok",
            "assumptions": [],
            "risks": [],
            "steps": [],
        }
    )
    try:
        create_llm_plan(payload, gateway=gateway, model=_planner_model())
    except ValueError as exc:
        assert "etapa" in str(exc).lower()
    else:
        raise AssertionError("Plano sem etapas deveria falhar.")


def test_service_falls_back_to_heuristic_when_gateway_raises() -> None:
    """The route ``POST /api/3d/plans`` was removed in Onda 2.11; the
    fallback behaviour is now tested by calling the service directly.
    """

    gateway = _FakeGateway(exc=ProviderExecutionError("simulação"))
    failing_service = ModelingService(store=get_store(), gateway=gateway)

    plan = failing_service.create_plan(
        ModelingPlanCreate(
            prompt="crie um cubo no Blender",
            mode=ModelingExecutionMode.approval_required,
        )
    )
    plan_dict = json.loads(plan.model_dump_json())

    audit = get_store().list_modeling_plans()
    matching = next((item for item in audit if item.id == plan.id), None)
    assert matching is not None
    assert len(plan_dict["steps"]) == 3
    assert plan_dict["steps"][0]["tool_name"] == "blender.create_mesh_primitive"
    assert all(
        step["tool_name"] != "project_store.create_snapshot" for step in plan_dict["steps"]
    )


def test_service_uses_llm_plan_when_gateway_returns_valid_payload() -> None:
    gateway = _FakeGateway(
        response={
            "software_choice": "blender",
            "confidence": 0.9,
            "rationale": "Mesh visual simples.",
            "assumptions": ["Unidades em mm."],
            "risks": [],
            "steps": [
                {
                    "seq": 1,
                    "title": "Validar mesh",
                    "tool_name": "blender.validate_mesh",
                    "risk_level": "low",
                    "approval_required": False,
                    "input_json": "{}",
                },
            ],
        }
    )
    llm_service = ModelingService(store=get_store(), gateway=gateway)

    plan = llm_service.create_plan(
        ModelingPlanCreate(
            prompt="valide a malha do meu modelo",
            mode=ModelingExecutionMode.approval_required,
        )
    )

    assert len(plan.steps) == 1
    assert plan.confidence == 0.9
    assert plan.steps[0].tool_name == "blender.validate_mesh"
    # validate_mesh is read-only by policy, so approval_required stays false even though
    # other plans in the suite would have it set.
    assert plan.steps[0].approval_required is False


def test_create_heuristic_plan_still_available_as_alias() -> None:
    """Backwards-compatible behaviour kept so external callers do not break."""
    from app.modeling.planner import create_structured_plan

    payload = ModelingPlanCreate(prompt="peça paramétrica simples")
    plan = create_structured_plan(payload)
    heuristic = create_heuristic_plan(payload)
    assert plan.software_choice == heuristic.software_choice
    assert len(plan.steps) == len(heuristic.steps)
    assert [step.tool_name for step in plan.steps] == [step.tool_name for step in heuristic.steps]


def test_plan_records_planner_source_and_fallback_reason() -> None:
    """create_plan persists planner_source on the plan itself so the UI can render it."""

    failing_gateway = _FakeGateway(exc=ProviderExecutionError("teste de fallback"))
    service = ModelingService(store=get_store(), gateway=failing_gateway)

    plan = service.create_plan(
        ModelingPlanCreate(
            prompt="crie um cubo",
            mode=ModelingExecutionMode.approval_required,
        )
    )

    assert plan.planner_source.value == "heuristic"
    assert "teste de fallback" in (plan.fallback_reason or "")


def test_heuristic_plan_defaults_to_primary_kind() -> None:
    payload = ModelingPlanCreate(prompt="cubo simples")
    plan = create_heuristic_plan(payload)
    assert plan.kind is ModelingPlanKind.primary
    assert plan.parent_plan_id is None


def test_heuristic_plan_preserves_edit_kind_and_parent_id() -> None:
    payload = ModelingPlanCreate(
        prompt="aplicar bevel de 2mm no cubo existente",
        kind=ModelingPlanKind.edit,
        parent_plan_id="m3d_plan_parent",
    )
    plan = create_heuristic_plan(payload)
    assert plan.kind is ModelingPlanKind.edit
    assert plan.parent_plan_id == "m3d_plan_parent"


def test_llm_plan_preserves_edit_kind_and_parent_id() -> None:
    gateway = _FakeGateway(
        response={
            "software_choice": "blender",
            "confidence": 0.8,
            "rationale": "edicao simples",
            "assumptions": [],
            "risks": [],
            "steps": [
                {
                    "seq": 1,
                    "title": "Aplicar bevel",
                    "tool_name": "blender.apply_bevel",
                    "risk_level": "low",
                    "approval_required": False,
                    "input_json": json.dumps({"bevel_mm": 2.0, "segments": 3}),
                }
            ],
        }
    )
    payload = ModelingPlanCreate(
        prompt="bevel de 2mm",
        kind=ModelingPlanKind.edit,
        parent_plan_id="m3d_plan_primary",
    )
    plan = create_llm_plan(payload, gateway=gateway, model=_planner_model())
    assert plan.kind is ModelingPlanKind.edit
    assert plan.parent_plan_id == "m3d_plan_primary"


def test_plan_records_llm_source_when_gateway_succeeds() -> None:
    gateway = _FakeGateway(
        response={
            "software_choice": "fusion",
            "confidence": 0.8,
            "rationale": "ok",
            "assumptions": [],
            "risks": [],
            "steps": [
                {
                    "seq": 1,
                    "title": "Abrir design",
                    "tool_name": "fusion.open_design",
                    "risk_level": "low",
                    "approval_required": False,
                    "input_json": "{}",
                }
            ],
        }
    )
    service = ModelingService(store=get_store(), gateway=gateway)

    plan = service.create_plan(
        ModelingPlanCreate(
            prompt="peça paramétrica",
            mode=ModelingExecutionMode.approval_required,
        )
    )

    assert plan.planner_source.value == "llm"
    assert plan.fallback_reason is None
