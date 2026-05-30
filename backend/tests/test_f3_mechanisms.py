"""F3 — mecanismos funcionais (rosca, componente, junta, macros).

Valida o *wiring* das tools novas sem depender do Fusion real (o gate de
geometria roda no Fusion). Cobre: presença na allowlist do adapter, no
registry e nos schemas; categorias de risco; e que o gerador de scripts
produz Python sintaticamente válido (braces do f-string corretos) com args
realistas, com o dispatch e os handlers presentes no script renderizado.

O gate de geometria (rosca real, dobradiça que abre, parafuso que encaixa)
é validado no Fusion real — ver ``specs/005-modeling-3d-fusion/micro/
fase-F3-mecanismos.md``.
"""

from __future__ import annotations

import ast

from app.modeling.fusion_mcp_scripts import (
    FUSION_SCRIPT_TOOLS,
    build_autodesk_fusion_script,
)
from app.modeling.tool_registry import (
    FUSION_TOOLS,
    PLANNER_TOOLSET,
    TOOL_REGISTRY,
    ToolCategory,
)
from app.modeling.tool_schemas import TOOL_SCHEMAS

F3_TOOLS = (
    "fusion.thread",
    "fusion.make_component",
    "fusion.joint",
    "fusion.knuckle_hinge",
    "fusion.metric_screw",
)

# args realistas por tool (cobrem string/number/bool/lista aninhada).
F3_CASES: dict[str, dict] = {
    "fusion.thread": {
        "body_ref": "Screw_Shank",
        "diameter_mm": 6.0,
        "is_internal": False,
        "length_mm": 18.0,
    },
    "fusion.make_component": {"body_ref": "Leaf_A", "name": "Hinge_A"},
    "fusion.joint": {
        "joint_type": "revolute",
        "body_one": "Hinge_A",
        "body_two": "Hinge_B",
        "face_selector_one": "cylindrical",
        "face_selector_two": "cylindrical",
        "axis": "z",
    },
    "fusion.knuckle_hinge": {
        "leaf_length_mm": 40,
        "leaf_width_mm": 20,
        "thickness_mm": 4,
        "knuckle_count": 5,
        "pin_diameter_mm": 4,
        "joint": "revolute",
    },
    "fusion.metric_screw": {
        "designation": "M6",
        "length_mm": 24,
        "head_diameter_mm": 10,
        "threaded": True,
    },
}


def test_f3_tools_are_in_every_allowlist() -> None:
    for tool in F3_TOOLS:
        assert tool in FUSION_SCRIPT_TOOLS, f"{tool} ausente em FUSION_SCRIPT_TOOLS"
        assert tool in FUSION_TOOLS, f"{tool} ausente em FUSION_TOOLS (registry)"
        assert tool in PLANNER_TOOLSET, f"{tool} não exposto ao planner"
        assert tool in TOOL_REGISTRY, f"{tool} ausente em TOOL_REGISTRY"
        assert tool in TOOL_SCHEMAS, f"{tool} sem schema de args (drift LLM↔adapter)"


def test_f3_risk_categories() -> None:
    # Rosca/junta/componente alteram o modelo (mutative, auto-exec no fluxo);
    # macros que criam corpos são aditivas.
    assert TOOL_REGISTRY["fusion.thread"].category is ToolCategory.mutative
    assert TOOL_REGISTRY["fusion.make_component"].category is ToolCategory.mutative
    assert TOOL_REGISTRY["fusion.joint"].category is ToolCategory.mutative
    assert TOOL_REGISTRY["fusion.knuckle_hinge"].category is ToolCategory.additive
    assert TOOL_REGISTRY["fusion.metric_screw"].category is ToolCategory.additive


def test_f3_scripts_compile_with_realistic_args() -> None:
    for tool, args in F3_CASES.items():
        script = build_autodesk_fusion_script(tool_name=tool, arguments=args)
        ast.parse(script)  # SyntaxError => braces do f-string quebraram
        assert f'TOOL_NAME = "{tool}"' in script


def test_f3_handlers_and_dispatch_present_in_generated_script() -> None:
    # Todo handler aparece em TODO script gerado (o template é único). Basta
    # checar num script qualquer que os handlers e o dispatch existem.
    script = build_autodesk_fusion_script(tool_name="fusion.thread", arguments={"diameter_mm": 6.0})
    for fn in (
        "def _thread(args):",
        "def _make_component(args):",
        "def _joint(args):",
        "def _knuckle_hinge(args):",
        "def _metric_screw(args):",
        "def _nearest_thread_designation(",
        "def _metric_nominal_mm(",
    ):
        assert fn in script, f"handler ausente no script: {fn}"
    for disp in (
        'if tool_name == "fusion.thread":',
        'if tool_name == "fusion.joint":',
        'if tool_name == "fusion.knuckle_hinge":',
        'if tool_name == "fusion.metric_screw":',
        'if tool_name == "fusion.make_component":',
    ):
        assert disp in script, f"dispatch ausente: {disp}"


def test_thread_uses_modeled_threads_api() -> None:
    # F3: a rosca precisa ser MODELADA (geometria real), não cosmética.
    script = build_autodesk_fusion_script(tool_name="fusion.thread", arguments={"diameter_mm": 8.0})
    assert "threadFeatures" in script
    assert "createThreadInfo" in script
    assert "isModeled = True" in script


def test_joint_supports_revolute_and_uses_joint_api() -> None:
    script = build_autodesk_fusion_script(
        tool_name="fusion.joint", arguments={"joint_type": "revolute"}
    )
    assert "setAsRevoluteJointMotion" in script
    assert "setAsSliderJointMotion" in script
    assert "setAsRigidJointMotion" in script
    assert "JointGeometry" in script


def test_macros_compose_validated_primitives() -> None:
    # Os macros reusam handlers validados (box/cylinder/combine/thread/joint),
    # reduzindo o risco de API blind. Confere as chamadas no script.
    script = build_autodesk_fusion_script(
        tool_name="fusion.knuckle_hinge", arguments={"knuckle_count": 5}
    )
    assert "_add_cylinder({" in script  # knuckles + pino
    assert "_add_box({" in script  # abas
    assert "_combine_bodies({" in script  # une knuckles às abas
    screw = build_autodesk_fusion_script(
        tool_name="fusion.metric_screw", arguments={"designation": "M6"}
    )
    assert "_add_cylinder({" in screw  # haste + cabeça
    assert "_thread({" in screw  # rosca modelada
