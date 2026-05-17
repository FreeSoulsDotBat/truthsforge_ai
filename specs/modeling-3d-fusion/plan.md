# plan.md

## Sequência

1. Integrar chat ↔ MCP 3D como experiência primária de criação.
2. Manter a aba 3D como configuração, diagnóstico e continuidade operacional.
3. Tornar o fluxo do chat fluido: autoexecutar adições/alterações normais e bloquear só deleção/destrutivo/high-risk.
4. Remover snapshot automático do planner/card, mantendo snapshots manuais e rollback explícito no painel 3D.
5. Revisar capacidades reais de Blender e Fusion.
6. Formalizar contrato Fusion bridge.
7. Endurecer UX de estado mock/adapter/real/erro.
8. Expandir printability mínima.
9. Versionar exports como artifacts.

## Validação

- Testes backend do bounded context 3D.
- Testes backend do contrato `ChatStreamRequest.modeling_3d` e streaming com `modeling_plan`.
- Testes frontend do metadata/card de plano 3D no chat.
- Teste manual com Blender configurado.
- Teste manual com Fusion bridge quando disponível.
- Golden path de prompt no chat, plano fluido, autoexecução, export e acompanhamento no painel 3D.
- Golden path separado para aprovação de etapa destrutiva/high-risk e rollback manual por snapshot.
