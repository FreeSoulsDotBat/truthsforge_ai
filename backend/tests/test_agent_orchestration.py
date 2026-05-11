from app.api.routes.chat import _knowledge_base_ids_for_runtime, select_orchestration_agents
from app.core.contracts import Agent, KnowledgeBase, Project, ProjectContextConfig


def test_enabled_orchestrator_becomes_primary_for_specialist_selection() -> None:
    orchestrator = Agent(
        name="JUDITE",
        system_prompt="coordene",
        role="orchestrator",
        enabled=True,
    )
    specialist = Agent(
        name="Pesquisador",
        system_prompt="pesquise",
        role="specialist",
        enabled=True,
    )

    primary, target, support = select_orchestration_agents(
        [specialist, orchestrator],
        selected_agent_id=specialist.id,
        requested_agent_ids=[],
        multi_agent_mode=False,
    )

    assert primary == orchestrator
    assert target == specialist
    assert support == [specialist]


def test_selected_orchestrator_stays_primary() -> None:
    orchestrator = Agent(
        name="JUDITE",
        system_prompt="coordene",
        role="orchestrator",
        enabled=True,
    )
    specialist = Agent(
        name="Revisor",
        system_prompt="revise",
        role="reviewer",
        enabled=True,
    )

    primary, target, support = select_orchestration_agents(
        [orchestrator, specialist],
        selected_agent_id=orchestrator.id,
        requested_agent_ids=[specialist.id],
        multi_agent_mode=True,
    )

    assert primary == orchestrator
    assert target is None
    assert support == [specialist]


def test_runtime_knowledge_bases_are_restricted_to_project_and_agents() -> None:
    project = Project(
        id="project_alpha",
        name="Projeto Alpha",
        context=ProjectContextConfig(knowledge_base_ids=["kb_project"]),
    )
    primary_agent = Agent(
        name="JUDITE",
        system_prompt="coordene",
        knowledge_base_ids=["kb_agent"],
    )
    support_agent = Agent(
        name="Pesquisador",
        system_prompt="pesquise",
        knowledge_base_ids=["kb_support"],
    )
    knowledge_bases = [
        KnowledgeBase(id="kb_project", name="Projeto"),
        KnowledgeBase(id="kb_agent", name="Agente"),
        KnowledgeBase(id="kb_support", name="Apoio"),
        KnowledgeBase(id="kb_forbidden", name="Fora do escopo"),
        KnowledgeBase(id="kb_disabled", name="Desabilitada", enabled=False),
    ]

    default_ids = _knowledge_base_ids_for_runtime(
        project_id=project.id,
        projects_by_id={project.id: project},
        primary_agent=primary_agent,
        target_agent=None,
        support_agents=[support_agent],
        payload_ids=[],
        session_ids=[],
        knowledge_bases=knowledge_bases,
    )
    payload_ids = _knowledge_base_ids_for_runtime(
        project_id=project.id,
        projects_by_id={project.id: project},
        primary_agent=primary_agent,
        target_agent=None,
        support_agents=[support_agent],
        payload_ids=["kb_forbidden", "kb_disabled", "kb_support", "kb_project"],
        session_ids=[],
        knowledge_bases=knowledge_bases,
    )

    assert default_ids == ["kb_project", "kb_agent", "kb_support"]
    assert payload_ids == ["kb_support", "kb_project"]
