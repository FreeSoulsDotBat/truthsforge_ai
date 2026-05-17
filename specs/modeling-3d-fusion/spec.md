# spec.md

## Título

Modelagem 3D chat-first com Blender e Fusion via MCP

## Status

Decisões de produto aprovadas; implementação obrigatória para a trilha atual.

## Objetivo

Consolidar o bounded context 3D com Blender real e Fusion bridge como capacidades obrigatórias, preservando planner, policy, aprovação, snapshots, rollback, printability, exports e artifacts, mas movendo a experiência primária de criação para o chat.
- QUANDO o usuário quiser criar um modelo 3D, O SISTEMA DEVE permitir ativar MCP 3D no chat e enviar o prompt para JUDITE.
- QUANDO o chat receber `modeling_3d.enabled=true`, O SISTEMA DEVE criar um plano 3D vinculado à conversa e persistir metadata de plano na mensagem da JUDITE.
- QUANDO um plano 3D for criado via chat, O SISTEMA DEVE renderizar status/card do plano na conversa e manter a aba 3D como configuração, diagnóstico e continuidade operacional.
- QUANDO `modeling_3d.enabled=true`, O SISTEMA DEVE rejeitar modos concorrentes de imagem, Deep Research e resumo oficial de raciocínio no mesmo request.

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
