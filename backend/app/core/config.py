from __future__ import annotations

import logging
import os
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger(__name__)


def _resolve_from_project_root(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _env_int(name: str, default: int) -> int:
    """Lê um env como ``int``, caindo no default (com warning) se mal-formado.

    Evita que um valor inválido (ex.: ``DIMENSIONS=abc``) derrube o import do
    módulo de config — e, com ele, todo o boot do backend — com um traceback
    opaco em ``Settings()``.
    """

    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Env %s=%r inválido (esperado inteiro); usando default %r.", name, raw, default
        )
        return default


def _env_float(name: str, default: float) -> float:
    """Lê um env como ``float``, caindo no default (com warning) se mal-formado."""

    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning(
            "Env %s=%r inválido (esperado número); usando default %r.", name, raw, default
        )
        return default


class Settings(BaseModel):
    app_env: str = Field(default_factory=lambda: os.getenv("TRUTHS_FORGE_ENV", "development"))
    public_base_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    )
    data_dir: Path = Field(
        default_factory=lambda: _resolve_from_project_root(
            os.getenv("TRUTHS_FORGE_DATA_DIR", ".local")
        )
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_DATABASE_URL",
            "postgresql://forge:forge_dev_password@127.0.0.1:5432/truths_forge_ai",
        )
    )
    # Teto do pool de conexões do Postgres (storage-002). Precisa acomodar
    # checkouts ANINHADOS na mesma thread (um método segura uma conexão e
    # chama outro método que faz novo checkout) — o store aplica piso 2 para
    # nunca deadlockar; o default 10 cobre com folga.
    postgres_pool_max_size: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_POSTGRES_POOL_MAX_SIZE", 10)
    )
    qdrant_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_QDRANT_URL", "http://127.0.0.1:6333")
    )
    rag_embedding_backend: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_RAG_EMBEDDING_BACKEND", "auto").lower()
    )
    rag_embedding_model: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    )
    rag_embedding_dimensions: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_RAG_EMBEDDING_DIMENSIONS", 384)
    )
    rag_ocr_languages: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_RAG_OCR_LANGUAGES", "por+eng")
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_REDIS_URL", "redis://127.0.0.1:6379/0")
    )
    # Backend das filas de trabalho (índice/import). ``memory`` (default)
    # mantém a fila em processo — adequada para dev/single-replica. ``redis``
    # ou ``valkey`` usam o servidor em ``redis_url`` (stack local preferencial
    # do AGENTS.md), permitindo compartilhar a fila entre réplicas do backend.
    # Se o backend Redis/Valkey estiver indisponível no startup, a fila cai
    # graciosamente para memória (ver app/workers/job_queue.py).
    queue_backend: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_QUEUE_BACKEND", "memory").lower()
    )
    storage_backend: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_STORAGE_BACKEND", "auto").lower()
    )
    allow_dev_llm: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_ALLOW_DEV_LLM", "true").lower() in {"1", "true", "yes", "on"}
        )
    )
    monthly_budget_brl: float = Field(
        default_factory=lambda: _env_float("TRUTHS_FORGE_MONTHLY_BUDGET_BRL", 200)
    )
    # Teto de polls do Deep Research (5s por poll; 360 ≈ 30 min). O operador
    # pode encurtar via env para não segurar a request indefinidamente em
    # aba abandonada. O provider aplica piso 1.
    deep_research_max_polls: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_DEEP_RESEARCH_MAX_POLLS", 360)
    )
    max_import_bytes: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_MAX_IMPORT_BYTES", 5 * 1024 * 1024 * 1024)
    )
    blender_executable: str | None = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_BLENDER_EXECUTABLE") or None
    )
    modeling_subprocess_timeout_seconds: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_MODELING_TIMEOUT_SECONDS", 90)
    )
    modeling_mcp_transport: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_MCP_TRANSPORT", "in_process").lower()
    )
    fusion_mcp_url: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_FUSION_MCP_URL", "http://127.0.0.1:27182/mcp"
        )
    )
    # Servidor MCP standalone (ADR-017). Local-first: bind loopback por padrão,
    # autenticação por token Bearer. O backend consome este servidor quando
    # ``modeling_mcp_transport == "mcp_http"``. Ver
    # specs/005-modeling-3d-fusion/micro/fase-1-mcp-standalone.md.
    modeling_mcp_server_host: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_MCP_SERVER_HOST", "127.0.0.1")
    )
    modeling_mcp_server_port: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_MCP_SERVER_PORT", 8787)
    )
    # Token explícito (env) tem precedência; vazio => gerado e persistido em
    # ``modeling_dir/mcp_server_token`` por ``auth.load_or_create_token``.
    modeling_mcp_server_token: str = Field(
        default_factory=lambda: os.getenv("TRUTHS_FORGE_MCP_SERVER_TOKEN", "")
    )
    # URL que o cliente backend usa para alcançar o servidor standalone.
    modeling_mcp_server_url: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_MCP_SERVER_URL", "http://127.0.0.1:8787/mcp"
        )
    )
    # Loop agêntico de auto-correção (Fase 2, RF-010/011). Quando ``true``, a
    # execução do plano passa pelo ModelingAgentLoop (executa→inspeciona→corrige,
    # teto 5, rollback ao esgotar) em vez do executor linear. Default OFF até o
    # gate do dono no Fusion real (corretor LLM e read-back dependem do Fusion).
    modeling_agentic_loop_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_AGENTIC_LOOP_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Planejamento hierárquico/agêntico (Frente F2, replan v4). Quando ``true``,
    # o orchestrator decompõe o pedido em sub-objetivos e planeja cada bloco
    # observando o ModelState real (F1) do bloco anterior (decompõe→executa→
    # observa→replaneja), em vez do plano one-shot. Reusa o ModelingAgentLoop
    # por baixo. Default OFF (depende do Fusion real + custo extra de LLM).
    modeling_hierarchical_planning_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_HIERARCHICAL_PLANNING_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Sanitizer determinístico pós-LLM (Frente F6 / ex-Fase 9.2, replan v4).
    # Camada entre planner e executor que remove campos-fantasma e valores de
    # referência geométrica (ex.: `face:"X.top_face"`, `bounding_box.max_x`) que
    # os nudges do system prompt não eliminam 100% (Bug J' do gate da Fase 4).
    # Conservador: só descarta o que NENHUM handler aceita e os nudges proíbem;
    # planos válidos passam intactos. Default ON (guardrail puro, com telemetria
    # por aviso); desligue para depurar o comportamento cru do planner.
    modeling_plan_sanitizer_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_PLAN_SANITIZER_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Reconciliação por geometria ao vivo na edição (Frente F5, replan v4).
    # Quando ``true``, antes de planejar uma edição o orchestrator lê a
    # GEOMETRIA real (``fusion.query_geometry``) além da timeline e injeta um
    # ModelState ao vivo (tokens/raios reais — F1) no contexto do planner, para
    # editar o modelo ATUAL e não um snapshot velho (capta mudanças manuais do
    # usuário). Default OFF: probe extra (custo/latência) e preserva o caminho
    # da Fase 3 já homologado até o gate do dono.
    modeling_live_geometry_reconciliation_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_LIVE_GEOMETRY_RECONCILIATION_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Verificação VISUAL pós-execução (motor genérico, passo 3 — replan v4).
    # Quando ``true``, após executar o plano o loop RENDERIZA o modelo
    # (capture_viewport), manda o render + a intenção para a LLM de visão
    # (gateway multimodal F4), recebe um veredito (corresponde? que diverge?) e,
    # se divergir, REPLANEJA uma edição corretiva. É o que faz a composição
    # genérica se auto-corrigir em qualquer produto. Default OFF (render só no
    # Fusion real + custo de visão). Teto em ``modeling_visual_max_rounds``.
    modeling_visual_verification_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_VISUAL_VERIFICATION_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    modeling_visual_max_rounds: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_MODELING_VISUAL_MAX_ROUNDS", 2)
    )
    # AÇÃO do loop visual (replan corretivo). Agora NÃO-DESTRUTIVO: a correção é
    # instruída a EDITAR corpos existentes (não recriar) e um guard determinístico
    # REVERTE (rollback) qualquer correção que mesmo assim duplique corpos
    # (BoxOuter_fixed/Lid (1)) — ver visual_critique.run_visual_correction. Mesmo
    # seguro, é OPT-IN (default OFF): é um replan via LLM (lento, a visão pode
    # alucinar) e a verificação PRIMÁRIA é a auto-crítica GEOMÉTRICA (F8), com a
    # visão entrando como achado semântico do veredito (ver
    # modeling_self_critique_enabled). Ligue p/ deixar a visão ATUAR (com a rede
    # de segurança do rollback), não só reportar.
    modeling_visual_autocorrect_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_VISUAL_AUTOCORRECT_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Posicionamento PARAMÉTRICO declarativo (Frente F7, ADR-022). Quando
    # ``true``, antes de despachar um passo que carrega referência espacial
    # (``@token('F').center``, objeto ``{edge:.., point:along}``) OU uma das tools
    # declarativas (``place_body``/``align_axis``/``distribute_along``), o executor
    # captura a geometria real (probe ``query_geometry``) e RESOLVE no backend
    # (``spatial_resolver``): refs inline viram números; tools declarativas viram
    # componentes + combine-DENTRO + juntas-ENTRE nativas. Tira a matemática de
    # posição do LLM (filosofia do sanitizer F6). Default OFF: probe extra
    # (custo/latência) + montagem API-blind a confirmar nos gates Fusion (P1/P6);
    # com OFF, o caminho de coordenada absoluta vigente segue intacto e as tools
    # declarativas erram claro (``fusion.spatial_not_resolved``), nunca mis-place.
    modeling_spatial_resolution_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_SPATIAL_RESOLUTION_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Proveniência de operações (Frente F8, ADR-023). Quando ``true``, o executor
    # captura o ModelState ANTES e DEPOIS de cada passo mutativo (probe
    # ``query_geometry``, com carry-forward do after→before entre passos p/ ~1
    # probe/passo) e grava um ``ChangeRecord`` determinístico
    # (criou/modificou/consumiu/deletou + delta) em ``response_json["_provenance"]``
    # + trace. É a base do "o que mudou na peça" p/ a auto-crítica. Default OFF
    # (probe extra; só mutativos); com OFF, zero captura e zero regressão.
    modeling_provenance_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_PROVENANCE_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Auto-crítica estruturada (Frente F8 Sub3.2, ADR-023). Quando ``true``, ao
    # fim da execução de um plano o motor deriva um ``IntentSpec`` (o esperado) do
    # próprio plano + agrega o histórico de proveniência (Sub2) + o ModelState
    # read-back e produz um ``ModelVerdict`` determinístico (faltou/demais/errado/
    # certo). É o feedback GEOMÉTRICO primário (aposenta o juiz-de-visão como
    # fonte). **INVARIANTE: só REPORTA** — persiste em ``plan.model_verdict`` +
    # trace e entra no contexto do próximo bloco; NUNCA dispara replan destrutivo.
    # Depende de ``modeling_provenance_enabled`` p/ ter histórico. Default OFF
    # (probe da captura final; com OFF, zero avaliação e zero regressão).
    modeling_self_critique_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_SELF_CRITIQUE_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Posicionamento por RELAÇÃO genérica (Frente F8 Sub4, ADR-023). Quando
    # ``true``, o passo declarativo ``fusion.relate_bodies`` (vocabulário fechado:
    # flush_mate/cover_opening/coaxial_insert/...) é DERIVADO medindo o ModelState
    # e expandido nas primitivas F7 provadas (place_body/align_axis → joint). O
    # verificador geométrico (contato/interferência/DOF) REPORTA; o reparo é só
    # proposto (gate P6). Default OFF (acoplado ao gate Fusion de junta com offset);
    # com OFF, relate_bodies não é resolvido e zero regressão.
    modeling_relation_placement_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_RELATION_PLACEMENT_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Enforcement de coordenada relativa — Gate B (Frente F9 Pilar 3, ADR-024).
    # Quando ``true``, o executor RECUSA um ``move_body`` cuja coordenada absoluta
    # sobreponha outro corpo OU deixe o corpo longe de todos (os bugs reais de
    # tampa sobreposta / a 80 mm), levantando ``fusion.relative_coord_forbidden``
    # e instruindo a usar ``place_body`` declarativo (o backend mede e encaixa).
    # **INVARIANTE: só RECUSA** — nunca adivinha a posição certa. Default OFF;
    # com OFF, o caminho de coordenada absoluta segue intacto (zero regressão).
    modeling_relative_enforcement_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_RELATIVE_ENFORCEMENT_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Modos de alinhamento do place_body — Frente F9 Pilar 1 (ADR-024). Quando
    # ``true``, o campo ``align`` é honrado: ``center`` (default, snap concêntrico
    # = comportamento atual), ``coplanar`` (só o eixo da normal), ``gap`` (folga
    # ``gap_mm`` no lado do corpo), ``edge``/``corner`` (alinha por borda/canto via
    # AABB; corpo rotacionado → ``fusion.bbox_not_axis_aligned``). Default OFF; com
    # OFF, ``align`` é IGNORADO e o placement é sempre ``center`` (zero regressão).
    modeling_align_modes_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_ALIGN_MODES_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Estado semântico passo-a-passo — Frente F9 Pilar 2 (ADR-024). Quando ``true``,
    # ao capturar o ModelState o motor DERIVA por medição: papéis de face (roles),
    # adjacência entre corpos (touches) e rótulo de corpo (body_label), injetados no
    # ``<model-state>`` p/ o LLM ECOAR a semântica em vez de chutar coordenada. Tudo
    # best-effort: ambíguo → vazio/None (NUNCA rotula errado). Default OFF; com OFF,
    # nenhuma derivação roda e o bloco fica como antes (zero regressão).
    modeling_semantic_state_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_SEMANTIC_STATE_ENABLED", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    allowed_origins_raw: str = Field(
        default_factory=lambda: os.getenv(
            "TRUTHS_FORGE_ALLOWED_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,tauri://localhost,capacitor://localhost",
        )
    )
    # ADR-014 (Onda 2.9): when enabled, ``POST /api/chat/stream`` rejects
    # the first turn of a new chat unless the client provided a
    # non-default, non-blank title. Default OFF so the legacy frontend
    # keeps working until the Onda 5 UI ships; flip to ``true`` once
    # the React side enforces the title modal.
    require_chat_title: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_REQUIRE_CHAT_TITLE", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )

    # Observabilidade do módulo de modelagem 3D (ver
    # specs/005-modeling-3d-fusion/observability-plan.md).
    # Quando ``true``, o ``ModelingTracer`` persiste eventos de trace em
    # ``modeling_trace_events``, emite logs JSON estruturados em
    # ``app.modeling.*`` e enriquece eventos SSE com ``trace_id``. Default
    # ``true`` em dev para visibilidade imediata; desligar reduz custo de I/O
    # em produção pesada.
    modeling_observability_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Quando ``true``, o payload dos eventos ``planner.llm_request`` /
    # ``planner.llm_response`` inclui prompt completo e resposta bruta do
    # LLM. Default ``false`` por privacidade — ativar só para debug.
    modeling_debug_llm_trace: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE", "false").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Reservas para job de retention futuro (não implementado nesta iteração).
    modeling_trace_retention_days_info: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_MODELING_TRACE_RETENTION_INFO", 30)
    )
    modeling_trace_retention_days_error: int = Field(
        default_factory=lambda: _env_int("TRUTHS_FORGE_MODELING_TRACE_RETENTION_ERROR", 180)
    )
    # Discovery agent (P2 do chat-flow-redesign): antes de propor o plano, um
    # agente LLM avalia se o pedido está claro o suficiente; se não, faz
    # perguntas e PARA. Default ``true``. Desligar volta ao comportamento
    # "propõe direto" (ainda com gate de aprovação da P1).
    modeling_discovery_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("TRUTHS_FORGE_MODELING_DISCOVERY_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"}
        )
    )
    # Limiar de confiança: abaixo dele (ou se o LLM listar perguntas) o agente
    # pergunta em vez de propor o plano. Mais alto = pergunta mais.
    modeling_discovery_confidence_threshold: float = Field(
        default_factory=lambda: _env_float("TRUTHS_FORGE_MODELING_DISCOVERY_THRESHOLD", 0.7)
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def imports_dir(self) -> Path:
        return self.data_dir / "imports"

    @property
    def modeling_dir(self) -> Path:
        return self.data_dir / "modeling"

    def ensure_local_dirs(self) -> None:
        for path in [
            self.state_dir,
            self.files_dir,
            self.logs_dir,
            self.cache_dir,
            self.imports_dir,
            self.modeling_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
