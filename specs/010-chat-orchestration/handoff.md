# handoff.md

Continuidade entre agentes (Codex, Claude Code, Devin, humanos) para `010-chat-orchestration`.

## Estado atual

- Onda 1 do refactor SDD concluída: spec/plan/tasks criados (doc-only).
- Fonte do contrato verificada direto em `backend/app/api/routes/chat.py` (eventos SSE: status, meta, token, reasoning_summary, session_title, modeling_plan, error, done).
- Dívida registrada (DT-001 monólito 2433 linhas; DT-002 `get_store()` direto; DT-003 glue 3D inline) — **não executada**.

## Pendências

- Fase 2 (extração de service layer) aguarda decisão do dono.
- Atualizar `docs/application-map.md` para apontar esta spec (no retro-fit final).
