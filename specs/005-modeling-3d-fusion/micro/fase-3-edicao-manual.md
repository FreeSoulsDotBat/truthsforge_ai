# Micro-plano — Fase 3: Edição manual (read-back / reconciliação sob demanda)

**Fase**: 3 | **Spec**: [`../spec.md`](../spec.md) (RF-014, RF-015) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 2 (núcleo agêntico + gate). Usa o read-back geométrico da Fase 2.

## Objetivo

Cobrir o fluxo real "mexi no modelo à mão, agora continue daqui": antes de planejar uma edição, o motor lê **sob demanda** o estado atual do Fusion (timeline + geometria) e **reconcilia** com o histórico de modelagem registrado, para que o plano de edição parta da realidade, não de um estado desatualizado.

## Estado atual (ponto de partida)

- Planos de edição (`kind="edit"`) já previstos no fluxo (`chat_orchestrator`/planner).
- Histórico de modelagem persistido (Fase 2).
- Leitura de **timeline** + reconciliação com o histórico: **nova** nesta fase (a Fase 2 entregou read-back de geometria; aqui soma-se a timeline e a lógica de divergência).

## Decisões-chave

1. **Gatilho sob demanda**: a leitura/reconciliação ocorre **antes de planejar uma edição** (não em polling contínuo).
2. **Fonte de verdade do estado**: o **Fusion atual** vence o histórico registrado quando houver divergência; o motor anota a divergência no contexto.
3. **Reconciliação**: casar features da timeline atual com os passos registrados; sinalizar o que foi alterado/adicionado/removido manualmente.

## Tarefas atômicas

- **T3.1** — Tool de leitura de **timeline** (features, ordem, parâmetros) via servidor MCP. _(dependente do adapter; validada no gate)_
- **T3.2** — Lógica de **reconciliação** timeline+geometria × histórico registrado (detecção de divergência).
- **T3.3** — Injetar o estado reconciliado no contexto do **planner** antes de propor a edição (RF-014).
- **T3.4** — Edição allowlistada não-high-risk roda no **fluxo fluido** com resumo (RF-015). **[Decisão do dono, 2026-05-25]** isto deve ser o **PADRÃO** das edições (auto-executa, sem card), não um opt-in: **só pedir aprovação quando alguma etapa for high-risk/destrutiva**. Sobrepõe **DT-006** (fluido opt-in) apenas no caminho de EDIÇÃO; o plano PRIMÁRIO segue parando no card. Impl. provável: a rota (`chat_modeling.py:429`) passar `fluid_mode=True` para `propose_edit_plan`, ou desacoplar edição do `modeling_fluid_mode` (hoje default `False` em `contracts.py:409`). `propose_edit_plan` já bloqueia high-risk automaticamente (`_plan_has_high_risk`), então o invariante P8 é preservado. **✅ FEITO (`4683300`):** a rota passa `fluid_mode=True` na edição; testes de rota + orchestrator verdes. (Falta o restante da Fase 3: read-back de timeline + reconciliação.)
- **T3.5** — Testes: cenário "alteração manual → edição parte do estado atual"; divergência detectada e refletida no plano.
- **T3.6** — **Rollback da última edição** [pedido do dono, 2026-05-25]: captura automática de **snapshot ANTES de cada edição** + ação de **restaurar** que desfaz a última edição, exposta como **botão na UI** do chat 3D ("Desfazer última edição"). Reusa `project_store` (`restore_snapshot`/`list_snapshots`) e/ou o rollback nativo do Fusion (**DT-005**). Entregáveis: snapshot pré-edição, endpoint de restore, botão no card/painel. Conecta ao ponto de injeção `rollback` do loop agêntico (hoje `rollback_skipped`) — o mesmo mecanismo serve para o rollback automático ao esgotar correções.

## Contratos / invariantes

- Sem ação destrutiva automática durante a reconciliação (apenas leitura).
- Mantém human-in-the-loop para high-risk; auto-execução só para allowlist não-high-risk (P8/RF-015).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest`.
- Web: gates web se a UI mudar (indicador de reconciliação).
- **Gate do dono (Fusion real)**: alterar o modelo manualmente no Fusion, pedir uma edição por chat e confirmar que o motor parte do estado real e conclui corretamente.

## Riscos

- **Timeline read-back incompleto** no adapter → reconciliação parcial. Mitigação: validar cedo no Fusion real; declarar limites.
- **Casamento ambíguo** entre features manuais e registradas → falsa divergência. Mitigação: heurística conservadora + sinalização ao dono.

## Definição de pronto (Fase 3)

- [ ] Leitura sob demanda de timeline + geometria.
- [ ] Reconciliação com histórico e injeção no planner.
- [ ] Edição não-high-risk **auto-executa por padrão** (aprovação só para high-risk/destrutivo) — decisão do dono, sobrepõe DT-006 no caminho de edição.
- [ ] **Rollback da última edição**: snapshot pré-edição + restore + botão na UI.
- [ ] Testes verdes; gate do dono aprovado.
