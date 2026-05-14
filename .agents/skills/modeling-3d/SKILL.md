---
name: modeling-3d
description: Use ao alterar o bounded context 3D, endpoints `/api/3d`, planner, policy, MCP local, Blender, Fusion, snapshots, printability ou UI da aba 3D.
---

## Objetivo

Preservar o contrato de segurança e auditabilidade do módulo 3D.

## Sempre consultar primeiro

- `docs/3d-mcp-modeling.md`
- `docs/implementation-plan.md`
- `docs/application-map.md`
- `specs/repo-foundation/spec.md`

## Guardrails obrigatórios

- operações mutáveis exigem aprovação humana por padrão;
- scripts livres não entram no caminho feliz;
- snapshot e rollback permanecem parte do fluxo;
- tool calls precisam continuar auditáveis;
- `mock`, adapter ausente e execução real devem ser distinguíveis.

## Regras adicionais

- não reduza Fusion a prioridade maior que Blender sem bridge real pronta no ambiente alvo;
- não introduza shell genérico;
- não remova validações e printability do contrato;
- preserve compatibilidade com planner estruturado e fallback heurístico.

## Saída esperada

Informar sempre:

1. software alvo;
2. risco da mudança;
3. impacto em approval/policy;
4. impacto em snapshots/tool calls/printability.
