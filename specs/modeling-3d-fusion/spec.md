# spec.md

## Título

Modelagem 3D obrigatória com Blender e Fusion

## Status

Decisões de produto aprovadas; implementação obrigatória para a trilha atual.

## Objetivo

Consolidar o bounded context 3D com Blender real e Fusion bridge como capacidades obrigatórias, preservando planner, policy, aprovação, snapshots, rollback, printability, exports e artifacts.

## Requisitos funcionais

- QUANDO uma sessão 3D iniciar, O SISTEMA DEVE distinguir mock, adapter ausente, execução real e erro.
- QUANDO Blender estiver configurado, O SISTEMA DEVE executar tools allowlistadas reais.
- QUANDO Fusion bridge estiver instalado, O SISTEMA DEVE operar via loopback local.
- QUANDO uma etapa alterar workspace 3D, O SISTEMA DEVE exigir aprovação, snapshot e rollback.
- QUANDO houver export ou validação, O SISTEMA DEVE registrar artifact e printability.

## Fontes

- `docs/3d-mcp-modeling.md`
- `docs/decisions.md`
- `specs/repo-foundation/spec.md`
