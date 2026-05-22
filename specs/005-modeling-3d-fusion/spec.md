# spec.md

## Título

Modelagem 3D chat-first integral com Blender e Fusion via MCP

## Status

Decisões aprovadas. Refatoração v2 em curso (ondas 0–6 descritas em `tasks.md`).
Sucede a v1 (chat + painel híbrido) e remove o painel de aprovação/execução.

## Objetivo

Tornar o módulo 3D chat-first de verdade: cada chat 3D é uma sessão completa de
modelagem, da descoberta de contexto até a execução e edição. A configuração de
adapters e o diagnóstico operacional migram para Configurações gerais e um modal
no cabeçalho do chat. O painel 3D no dashboard é removido. Aprovação de plano
acontece exclusivamente dentro do chat, por botões inline no card do plano.

## Requisitos comportamentais (EARS)

### Ativação e identidade do chat 3D

- QUANDO o usuário criar um novo chat, O SISTEMA DEVE permitir marcar esse chat
  como 3D ativando a flag por chat persistida em `chats.is_modeling_3d`.
- QUANDO o usuário ativar 3D em um chat com histórico não vazio, O SISTEMA DEVE
  apresentar modal informativo com botões "Criar novo chat 3D" e "Cancelar",
  sem copiar mensagens do chat original.
- QUANDO um chat for marcado como 3D, O SISTEMA DEVE renderizar um ícone de
  identificação na sidebar, no header do chat e em qualquer card de prévia,
  com tooltip "Chat de modelagem 3D".
- QUANDO um chat for marcado como 3D, A FLAG `is_modeling_3d` NÃO PODE ser
  alterada para `false` posteriormente (imutável após criação).

### Descoberta de contexto (stage `discovery`)

- QUANDO o usuário enviar a primeira mensagem em um chat 3D vazio, O SISTEMA
  DEVE entrar em fase `discovery` e o agente DEVE buscar entendimento completo:
  geometria pretendida, dimensões, materiais, restrições físicas, processo de
  fabricação, contexto de uso.
- QUANDO o contexto não estiver claro, O AGENTE DEVE chamar a tool
  `3d.ask_clarification` para perguntar antes de propor plano, sem criar registros
  de plano ou execução.
- QUANDO o usuário anexar imagem ou arquivo 3D durante a descoberta, O SISTEMA
  DEVE chamar `3d.analyze_attachment` (vision para imagens, Blender headless para
  arquivos 3D com análise profunda — mesh stats, simetria, features sugeridas)
  e incorporar a análise como contexto da conversa.

### Proposta de plano (stage `planning`)

- QUANDO o agente julgar que tem contexto suficiente, ELE DEVE chamar a tool
  `3d.propose_plan` que cria um `ModelingPlan` com `kind="primary"` vinculado
  ao chat e transiciona o chat para stage `planning`.
- QUANDO `3d.propose_plan` for chamada, O SISTEMA DEVE renderizar o
  `ModelingPlanCard` na conversa contendo: descrição em prosa do que será
  modelado (físico e processual), lista de etapas, badges de risco por etapa,
  banner de aviso quando houver etapas high-risk, e os botões "Aprovar" e
  "Rejeitar".
- A APROVAÇÃO/REJEIÇÃO do plano DEVE acontecer exclusivamente via botões no
  card dentro do chat. Resposta textual livre NÃO DEVE acionar execução.

### Aprovação e execução (stages `approved` → `executing`)

- QUANDO o usuário clicar "Aprovar" no card, O SISTEMA DEVE transicionar
  o chat para stage `approved`, registrar a aprovação na auditoria, executar
  todas as etapas do plano em sequência e transicionar para `executing` e em
  seguida `editing` ao terminar com sucesso.
- A APROVAÇÃO GLOBAL DO PLANO cobre todas as etapas, incluindo high-risk
  (`apply_boolean`, `repair_non_manifold`, `restore_snapshot`, `run_script`).
  O sistema NÃO DEVE interromper a execução para reaprovações step-a-step
  após o plano principal aprovado.
- QUANDO o usuário clicar "Rejeitar" no card (com motivo opcional), O SISTEMA
  DEVE retornar o chat para stage `discovery`, registrar a rejeição e o motivo,
  e o agente DEVE retomar a conversa para entender o que precisa mudar.

### Edições subsequentes (stage `editing`)

- QUANDO o usuário enviar nova mensagem em um chat com stage `editing`, O
  AGENTE DEVE tratar a mensagem como pedido de edição do modelo já executado.
- QUANDO a edição contiver apenas tools allowlistadas não-high_risk, O AGENTE
  DEVE chamar `3d.propose_edit_plan` que cria um `ModelingPlan` com
  `kind="edit"`, executa automaticamente e renderiza `ModelingEditCard`
  compacto com o resumo do que foi feito.
- QUANDO a edição contiver alguma tool high-risk, O AGENTE DEVE chamar
  `3d.request_high_risk_approval` que cria o mini-plano em estado pendente,
  renderiza card com botões "Aprovar"/"Rejeitar" e só executa após aprovação.

### Anexos com análise profunda

- QUANDO o usuário anexar imagem, O SISTEMA DEVE comprimir/limitar resolução,
  enviar ao gateway LLM com capacidade vision e armazenar a análise no contexto
  do chat.
- QUANDO o usuário anexar arquivo 3D (`.stl`, `.obj`, `.step`, `.3mf`, `.blend`),
  O SISTEMA DEVE executar análise profunda via Blender headless: bounding box,
  contagens (vértices/faces/edges), volume, simetria detectada, features
  identificáveis, sugestões iniciais de planejamento.
- A ANÁLISE DEVE respeitar limite de tamanho (`≤ 50 MB` na primeira versão) e
  timeout dedicado curto (`15 s`), com fallback para metadata mínima.

### Diagnóstico operacional

- A ABA "MODELING" DO DASHBOARD DEVE ser removida.
- A CONFIGURAÇÃO de Blender path, Fusion MCP URL, transport mode e status de
  adapters DEVE viver em Configurações gerais.
- O DIAGNÓSTICO de capabilities, sessões, snapshots, tool calls, model versions
  e printability reports DEVE ser acessível via modal `ModelingDiagnosticsModal`
  aberto pelo cabeçalho do chat 3D.
- O MODAL DE DIAGNÓSTICO É READ-ONLY: não exibe botões de aprovar, executar ou
  criar planos.

### Título obrigatório (escopo não-3D acoplado)

- QUANDO o usuário criar um novo chat (3D ou não), O SISTEMA DEVE exigir título
  não vazio antes da primeira mensagem.
- O FRONTEND DEVE bloquear o input de mensagem até que o título seja fornecido.
- O BACKEND DEVE rejeitar `POST /api/chat/stream` com `HTTP 422` quando
  `chat.title` estiver vazio ou nulo.
- O SISTEMA NÃO DEVE chamar a OpenAI para auto-titulação de chats. O serviço
  e endpoint atuais de auto-titulação DEVEM ser removidos.
- CHATS EXISTENTES sem título DEVEM receber backfill `"Sem título - YYYY-MM-DD"`
  derivado de `created_at` na migração que torna `title NOT NULL`.

## Estados de chat

```
created (title obrigatório) → discovery → planning → approved → executing → editing ↺
                                              ↑                                ↓
                                              └────── (rejeição) ──────────────┘
```

Para chats não-3D, somente o estado `created` se aplica; demais campos 3D são
nulos.

## Fluxo único (substitui modos plan_only / approval_required / safe_auto)

Os três modos legados são **removidos**. Todo chat 3D segue o mesmo caminho:
descoberta → plano primário com aprovação no chat → execução completa →
edições com mini-planos auto-aprovados (ou aprovação inline para high-risk).

O usuário não precisa mais escolher modo. A flag `is_modeling_3d` é binária e
imutável após criação.

## Requisitos funcionais (preservados da v1)

- QUANDO uma sessão 3D iniciar, O SISTEMA DEVE distinguir mock, adapter ausente,
  execução real e erro.
- QUANDO Blender estiver configurado, O SISTEMA DEVE executar tools allowlistadas
  reais.
- QUANDO Fusion bridge estiver instalado, O SISTEMA DEVE operar via loopback
  local.
- QUANDO uma etapa for destrutiva ou high-risk, O SISTEMA DEVE registrar
  auditoria e manter snapshots manuais e rollback explícito.
- QUANDO houver export ou validação, O SISTEMA DEVE registrar artifact e
  printability.

## Out of scope

- Reescrita do Fusion legacy add-in.
- DAG não-linear de planos.
- Replay/versionamento de plano executado.
- Plugins 3D externos.

## Fontes

- `docs/3d-mcp-modeling.md`
- `docs/decisions.md` (ADR-012, ADR-013, ADR-014)
- `specs/000-repo-foundation/spec.md`
- Plano de execução: `C:\Users\Jonatan\.claude\plans\gostaria-de-planejar-uma-lovely-ember.md`
