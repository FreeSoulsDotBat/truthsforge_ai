# plan.md

## Sequência

1. Integrar chat ↔ MCP 3D como experiência primária de criação.
2. Manter a aba 3D como configuração, diagnóstico e continuidade operacional.
3. Revisar capacidades reais de Blender e Fusion.
4. Formalizar contrato Fusion bridge.
5. Endurecer UX de estado mock/adapter/real/erro.
6. Expandir printability mínima.
7. Versionar exports como artifacts.

## Validação

- Testes backend do bounded context 3D.
- Testes backend do contrato `ChatStreamRequest.modeling_3d` e streaming com `modeling_plan`.
- Testes frontend do metadata/card de plano 3D no chat.
- Teste manual com Blender configurado.
- Teste manual com Fusion bridge quando disponível.
- Golden path de plano, aprovação, execução, snapshot, rollback e export.
