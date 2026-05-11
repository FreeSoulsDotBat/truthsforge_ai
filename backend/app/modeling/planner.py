from __future__ import annotations

from app.core.contracts import (
    ModelingExecutionMode,
    ModelingPlan,
    ModelingPlanCreate,
    ModelingPlanStatus,
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    ModelingStepStatus,
)

FUSION_HINTS = {
    "paramétrico",
    "parametrico",
    "tolerância",
    "tolerancia",
    "encaixe",
    "furo",
    "extrusão",
    "extrusao",
    "chamfer",
    "chanfro",
    "fillet",
    "rosca",
    "mm",
    "step",
    "stl",
    "3mf",
    "peça",
    "peca",
    "suporte",
    "molde",
}
BLENDER_HINTS = {
    "orgânico",
    "organico",
    "escultura",
    "mesh",
    "render",
    "visual",
    "personagem",
    "textura",
    "cena",
    "bevel",
    "cubo",
}


def choose_software(
    prompt: str, override: ModelingSoftware | None
) -> tuple[ModelingSoftware, float, str]:
    if override in {ModelingSoftware.blender, ModelingSoftware.fusion}:
        return override, 0.95, f"Software escolhido manualmente: {override.value}."

    normalized = prompt.lower()
    fusion_score = sum(1 for hint in FUSION_HINTS if hint in normalized)
    blender_score = sum(1 for hint in BLENDER_HINTS if hint in normalized)
    if fusion_score >= blender_score and fusion_score > 0:
        return (
            ModelingSoftware.fusion,
            min(0.9, 0.62 + fusion_score * 0.04),
            "O pedido parece CAD/paramétrico, então Fusion 360 é o alvo mais seguro.",
        )
    if blender_score > 0:
        return (
            ModelingSoftware.blender,
            min(0.86, 0.62 + blender_score * 0.04),
            "O pedido parece visual, mesh ou orgânico, então Blender é o alvo mais simples.",
        )
    return (
        ModelingSoftware.fusion,
        0.58,
        "Sem sinais fortes; Fusion 360 é o default para peças funcionais e impressão 3D.",
    )


def create_structured_plan(payload: ModelingPlanCreate) -> ModelingPlan:
    software, confidence, rationale = choose_software(payload.prompt, payload.software_override)
    steps = _default_steps(software, payload.mode)
    approval_required = payload.mode != ModelingExecutionMode.safe_auto or any(
        step.approval_required for step in steps
    )
    status = (
        ModelingPlanStatus.draft
        if payload.mode == ModelingExecutionMode.plan_only
        else ModelingPlanStatus.waiting_approval
    )
    return ModelingPlan(
        project_id=payload.project_id,
        conversation_id=payload.conversation_id,
        prompt=payload.prompt,
        mode=payload.mode,
        software_choice=software,
        confidence=confidence,
        approval_required=approval_required,
        status=status,
        rationale=rationale,
        assumptions=[
            "Unidades padrão em milímetros até o usuário informar outra unidade.",
            "Execução real depende do adapter local do software estar disponível no backend.",
            "Scripts livres gerados por IA permanecem bloqueados por padrão.",
        ],
        risks=[
            "Operações mutáveis exigem aprovação humana no MVP.",
            (
                "Blender executa apenas ferramentas allowlistadas; Fusion 360 ainda "
                "permanece mock até bridge desktop ser instalado."
            ),
        ],
        knowledge_base_ids=payload.knowledge_base_ids,
        steps=steps,
    )


def _default_steps(
    software: ModelingSoftware, mode: ModelingExecutionMode
) -> list[ModelingPlanStep]:
    approval_status = (
        ModelingStepStatus.pending
        if mode == ModelingExecutionMode.plan_only
        else ModelingStepStatus.waiting_approval
    )
    if software == ModelingSoftware.blender:
        return [
            ModelingPlanStep(
                seq=1,
                title="Criar snapshot do workspace 3D",
                software=software,
                tool_name="project_store.create_snapshot",
                risk_level=ModelingRiskLevel.low,
                approval_required=False,
                status=ModelingStepStatus.pending,
                input_json={"reason": "before_modeling"},
            ),
            ModelingPlanStep(
                seq=2,
                title="Criar geometria inicial no Blender",
                software=software,
                tool_name="blender.create_mesh_primitive",
                risk_level=ModelingRiskLevel.medium,
                approval_required=True,
                status=approval_status,
                input_json={"primitive": "cube", "units": "mm"},
            ),
            ModelingPlanStep(
                seq=3,
                title="Aplicar acabamento visual controlado",
                software=software,
                tool_name="blender.apply_bevel",
                risk_level=ModelingRiskLevel.medium,
                approval_required=True,
                status=approval_status,
                input_json={"bevel_mm": 1.0, "segments": 3},
            ),
            ModelingPlanStep(
                seq=4,
                title="Exportar STL de validação",
                software=software,
                tool_name="blender.export_stl",
                risk_level=ModelingRiskLevel.low,
                approval_required=False,
                status=ModelingStepStatus.pending,
                input_json={"target": "preview.stl"},
            ),
        ]
    return [
        ModelingPlanStep(
            seq=1,
            title="Criar snapshot do workspace 3D",
            software=software,
            tool_name="project_store.create_snapshot",
            risk_level=ModelingRiskLevel.low,
            approval_required=False,
            status=ModelingStepStatus.pending,
            input_json={"reason": "before_modeling"},
        ),
        ModelingPlanStep(
            seq=2,
            title="Criar sketch paramétrico",
            software=software,
            tool_name="fusion.create_sketch",
            risk_level=ModelingRiskLevel.medium,
            approval_required=True,
            status=approval_status,
            input_json={"units": "mm", "constraints": "dimensioned"},
        ),
        ModelingPlanStep(
            seq=3,
            title="Extrudar corpo principal",
            software=software,
            tool_name="fusion.extrude_profile",
            risk_level=ModelingRiskLevel.medium,
            approval_required=True,
            status=approval_status,
            input_json={"operation": "new_body"},
        ),
        ModelingPlanStep(
            seq=4,
            title="Adicionar acabamento e validar medidas",
            software=software,
            tool_name="fusion.validate_dimensions",
            risk_level=ModelingRiskLevel.low,
            approval_required=False,
            status=ModelingStepStatus.pending,
            input_json={"checks": ["dimensions", "closed_profiles"]},
        ),
    ]
