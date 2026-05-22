# plan.md

## Estratégia

Evoluir o runtime atual de agentes/tools em etapas pequenas, preservando policy, auditoria e UX de aprovação.

## Sequência

1. Formalizar contratos de ação: adição, alteração e deleção.
2. Implementar sandbox por projeto para tools com escrita/execução.
3. Aplicar timeout, limite de tamanho e auditoria em todo tool call.
4. Implementar rollback obrigatório para ações mutáveis.
5. Evoluir JUDITE para workflows multi-etapa com checkpoints humanos.
6. Implementar memória durável por usuário, projeto, agente e decisão.

## Validação

- Testes backend para policy `allow`, `ask`, `deny`.
- Testes backend para aprovação obrigatória em alteração/deleção.
- Testes de auditoria por tool call.
- Testes manuais/e2e de workflow multi-etapa com checkpoint.
