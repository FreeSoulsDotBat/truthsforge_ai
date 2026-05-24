# Especificação: Modelagem 3D chat-first autônoma no Fusion 360 (v4)

**Pasta da spec**: `specs/005-modeling-3d-fusion/` | **Criada em**: 2026-05-23 | **Status**: Rascunho (aguardando aprovação do dono)

**Entrada**: Descrição do dono do produto: "Autonomia de criação de modelos 3D via chat: através de um chat, ser capaz de modelar o que eu quiser, da forma que eu quiser, no Fusion 360 — com planejamento dirigido, execução autônoma do início ao fim e fidelidade ao que foi pedido."

> Idioma: PT-BR (nomes/comandos Spec Kit em inglês). Esta spec descreve o **produto-alvo completo** do bounded context 3D; o **sequenciamento em fases** vive em `plan.md` (macro) e os detalhes por fase em `micro/fase-N-*.md`.
>
> **Escopo desta reescrita (v4):** estritamente o módulo 3D. Acoplamentos não-3D que existiam na v2 (ex.: "título obrigatório de chat") **saem** desta spec. A v4 sucede a v1/v2/v3; **nada do código anterior é assumido como pronto** até passar por auditoria + teste + validação real (ver `plan.md`, Fase 0).

## Cenários de usuário e testes *(obrigatória)*

### História 1 — Modelar por chat com execução autônoma fim-a-fim (Prioridade: P1)

O usuário descreve em linguagem natural o que quer criar. O motor entende ao máximo a intenção, propõe um plano de modelagem em prosa + passos, e — **após a aprovação do plano** — executa **do início ao fim, sem parar no meio**, entregando o modelo no Fusion. O usuário revê o resultado final e segue conversando para editar.

**Por que esta prioridade**: é o coração do produto — autonomia de criação por chat. Sem isso, nada mais importa.

**Teste independente**: com Fusion conectado, um prompt de peça única resulta em modelo construído sem intervenção manual entre a aprovação e o término.

**Cenários de aceitação**:

1. **Dado** um chat 3D e um pedido com contexto suficiente, **Quando** o usuário aprova o plano proposto, **Então** o motor executa todos os passos em sequência, sem solicitar validação passo-a-passo, e reporta conclusão com o resultado final.
2. **Dado** um plano em execução, **Quando** um passo produz erro recuperável, **Então** o motor tenta corrigir automaticamente (loop interno, teto de 5 iterações) sem interromper o usuário.
3. **Dado** um plano em execução, **Quando** o motor não resolve um erro dentro de 5 iterações, **Então** ele para, reverte ao último estado seguro conforme a política de snapshot e reporta a falha com diagnóstico.

---

### História 2 — Planejamento dirigido com aprovação, negação ou edição (Prioridade: P1)

Antes de propor o plano, o motor faz **perguntas dirigidas** para extrair o máximo de detalhes (geometria, dimensões, materiais, restrições, processo de fabricação, uso, destino — incluindo se é para impressão 3D). Com isso monta o plano. O usuário pode **aprovar**, **negar com justificativa** (o motor volta a perguntar) ou **editar** o plano antes de aprovar.

**Por que esta prioridade**: é o que garante "exatamente como pedi" — o plano correto antes de gastar execução.

**Teste independente**: um pedido vago dispara perguntas de clarificação antes de qualquer plano; o card de plano oferece aprovar/negar/editar.

**Cenários de aceitação**:

1. **Dado** um pedido com contexto insuficiente, **Quando** o motor avalia a intenção, **Então** ele pergunta antes de propor plano, sem criar registros de execução.
2. **Dado** um plano proposto, **Quando** o usuário nega com justificativa, **Então** o motor retoma a descoberta usando a justificativa, sem executar.
3. **Dado** um plano proposto, **Quando** o usuário edita os passos e aprova, **Então** a execução segue o plano editado.
4. **Dado** que a trilha planejamento→modelagem é guiada mas **não engessada**, **Quando** o usuário quer conduzir os passos, **Então** ele pode ajustar o plano em vez de aceitar a sequência sugerida.

---

### História 3 — Fidelidade verificada por leitura geométrica (Prioridade: P1)

O motor não confia apenas em "a tool não lançou erro": após executar, ele **lê a geometria de volta** (bounding box, volume, contagens de faces/arestas/corpos, dimensões) e compara com o esperado do plano. Divergência alimenta o loop de correção. O usuário dá a palavra final ao revisar o resultado.

**Por que esta prioridade**: é o mecanismo concreto de "ficou exatamente como pedi" e o passo "inspeciona" do loop agêntico.

**Teste independente**: ao final de uma execução, existe um relatório de verificação comparando esperado × medido por etapa relevante.

**Cenários de aceitação**:

1. **Dado** um passo dimensional concluído, **Quando** o motor lê a geometria resultante, **Então** registra esperado × medido e marca conformidade ou divergência.
2. **Dado** uma divergência detectada, **Quando** ainda há iterações disponíveis, **Então** o motor planeja e aplica uma correção.

---

### História 4 — Edição contínua e reconciliação de alterações manuais (Prioridade: P2)

Depois de modelado, o usuário continua editando por chat. Se o usuário tiver feito **alterações manuais no Fusion**, o motor, **sob demanda** (antes de planejar a próxima edição), lê o estado atual (timeline + geometria) e se reconcilia com o histórico de modelagem antes de propor a edição.

**Por que esta prioridade**: cobre o fluxo real "mexi na mão, agora continue daqui".

**Teste independente**: após uma alteração manual, um novo pedido de edição parte do estado atual real, não de um estado desatualizado.

**Cenários de aceitação**:

1. **Dado** um modelo alterado manualmente no Fusion, **Quando** o usuário pede uma edição, **Então** o motor lê o estado atual e reconcilia o contexto antes de propor o plano de edição.
2. **Dado** uma edição sem operações high-risk, **Quando** o motor a executa, **Então** ela roda no fluxo fluido (auto-execução allowlistada) e o resultado é resumido no chat.

---

### História 5 — MCP reutilizável por outros clientes (Prioridade: P2)

As operações 3D vivem atrás de um **servidor MCP standalone** aderente ao protocolo. O backend do produto é apenas **um** cliente; o usuário pode conectar **outros clientes** (ex.: Claude com conectores personalizados) ao mesmo servidor, respeitando autenticação e o princípio local-first.

**Por que esta prioridade**: desacopla a capacidade 3D do produto e habilita reuso, sem reengenharia futura.

**Teste independente**: um cliente externo autenticado lista e invoca as tools 3D via MCP, separado do backend do produto.

**Cenários de aceitação**:

1. **Dado** o servidor MCP em execução, **Quando** um cliente autenticado se conecta, **Então** ele descobre as tools 3D e as invoca pelo protocolo.
2. **Dado** o princípio local-first, **Quando** o servidor é exposto, **Então** ele exige autenticação e não fica publicamente exposto de forma ingênua (loopback/VPN/pareamento).

---

### História 6 — Observabilidade e depuração acessíveis ao dono (Prioridade: P2)

A observabilidade é ponto forte: cada execução gera trace por passo; o usuário consegue **ler logs/traces** para entender o que ocorreu, e existe **documentação dos melhores scripts de terminal** para depurar erros.

**Por que esta prioridade**: o dono valida no Fusion real (o container é mock); precisa enxergar e diagnosticar.

**Teste independente**: após uma execução, o usuário acessa o trace por passo e a doc lista comandos de debug reais.

**Cenários de aceitação**:

1. **Dado** uma execução concluída ou falha, **Quando** o usuário abre o diagnóstico, **Então** vê trace por passo, logs e o relatório de verificação geométrica.
2. **Dado** um erro reportado, **Quando** o usuário consulta a documentação de depuração, **Então** encontra scripts de terminal indicados para investigar a classe daquele erro.

---

### Casos de borda

- **Adapter ausente / mock** (caso do container remoto): o sistema distingue claramente mock, adapter ausente, execução real e erro, sem fingir sucesso.
- **Anexo de imagem ou arquivo 3D** na descoberta: o sistema analisa (vision para imagem; análise headless para arquivo 3D) dentro de limites de tamanho/timeout, com fallback para metadata mínima.
- **Operação high-risk** (destrutiva, boolean, reparo, restauração, script): coberta pela aprovação única do plano; nunca por liberação de script livre/shell no caminho feliz.
- **Erro irrecuperável** no meio da execução: para, reverte ao último snapshot seguro e reporta — não deixa o modelo em estado inconsistente silencioso.
- **Operação fora da cobertura suportada** na fase corrente: falha de forma explícita ("capacidade ainda não suportada"), sem improviso via script livre.

## Requisitos *(obrigatória)*

### Requisitos funcionais

Forma EARS com ID rastreável.

**Sessão e identidade do chat 3D**
- **RF-001**: QUANDO o usuário marcar um chat como 3D, O SISTEMA DEVE persistir essa identidade e tratar o chat como sessão completa de modelagem (descoberta → execução → edição).
- **RF-002**: QUANDO o chat 3D iniciar, O SISTEMA DEVE distinguir e sinalizar os modos mock, adapter ausente, execução real e erro.

**Descoberta e planejamento**
- **RF-003**: QUANDO o contexto do pedido for insuficiente, O SISTEMA DEVE fazer perguntas dirigidas (geometria, dimensões, materiais, restrições, fabricação, uso, destino de impressão) antes de propor plano, sem criar registros de execução.
- **RF-004**: QUANDO o usuário anexar imagem ou arquivo 3D na descoberta, O SISTEMA DEVE analisá-lo (vision para imagem; análise headless para arquivo 3D) respeitando limite de tamanho e timeout, com fallback para metadata mínima, e incorporar o resultado ao contexto.
- **RF-005**: QUANDO o motor tiver contexto suficiente, O SISTEMA DEVE propor um plano contendo descrição em prosa (físico + processual), lista de passos e indicação de risco por passo.
- **RF-006**: O SISTEMA DEVE permitir que o usuário **aprove**, **negue com justificativa** ou **edite** o plano antes da aprovação; a trilha é guiada, não engessada.
- **RF-007**: QUANDO o usuário negar o plano com justificativa, O SISTEMA DEVE retomar a descoberta usando a justificativa, sem executar.

**Execução autônoma**
- **RF-008**: QUANDO o usuário aprovar o plano, O SISTEMA DEVE executar todos os passos do início ao fim, em sequência, **sem solicitar validação passo-a-passo** e sem pausar para interação do usuário.
- **RF-009**: A aprovação única do plano DEVE cobrir todos os passos, inclusive high-risk; O SISTEMA NÃO DEVE exigir reaprovações por passo após o plano aprovado. A cobertura inclui os **deltas corretivos** gerados pelo loop durante a execução — o loop **não pausa** para reaprovar correções high-risk (decisão do dono, 2026-05-23).
- **RF-010**: ENQUANTO executa, O SISTEMA DEVE rodar um loop de auto-correção `executa → inspeciona → corrige` com teto de **5 iterações** por ponto de falha, sem intervenção do usuário.
- **RF-011**: QUANDO o motor esgotar as 5 iterações sem sucesso, O SISTEMA DEVE parar, reverter ao último estado seguro (snapshot) conforme a política e reportar a falha com diagnóstico.

**Verificação e fidelidade**
- **RF-012**: QUANDO um passo dimensional concluir, O SISTEMA DEVE ler a geometria resultante (bbox, volume, contagens, dimensões) e comparar com o esperado do plano, registrando conformidade ou divergência.
- **RF-013**: QUANDO houver divergência e restarem iterações, O SISTEMA DEVE planejar e aplicar correção; QUANDO a verificação concluir, O SISTEMA DEVE disponibilizar relatório esperado × medido ao usuário.

**Edição e reconciliação**
- **RF-014**: QUANDO o usuário pedir edição em um modelo possivelmente alterado à mão, O SISTEMA DEVE ler sob demanda o estado atual (timeline + geometria) e reconciliar o contexto antes de propor a edição.
- **RF-015**: QUANDO uma edição contiver apenas operações allowlistadas não-high-risk, O SISTEMA PODE executá-la no fluxo fluido (auto-execução), resumindo o resultado.

**Cobertura de operações**
- **RF-016**: O SISTEMA DEVE, como alvo de produto, cobrir todas as operações do workspace **Design** do Fusion 360: sólido (todas as features), superfície (NURBS), sheet metal, sculpt/T-Spline e assemblies (componentes, ocorrências, juntas, materiais físicos). _(Sequenciado em fases no `plan.md`.)_
- **RF-017**: O SISTEMA NÃO DEVE, nesta frente, cobrir outros workspaces do Fusion (CAM/usinagem, simulação/FEA, generative design, drawings 2D, render).
- **RF-018**: QUANDO o usuário solicitar uma operação ainda não suportada pela fase corrente, O SISTEMA DEVE falhar de forma explícita, sem improviso via script livre.

**Persistência e histórico**
- **RF-019**: O SISTEMA DEVE persistir o histórico de chat e o histórico de modelagem (plano, passos executados, verificações, traces) de forma reconstituível, para que o motor entenda criações anteriores.

**Interface MCP reutilizável**
- **RF-020**: O SISTEMA DEVE expor as operações 3D por um servidor MCP standalone aderente ao protocolo, com o backend do produto como um cliente entre outros possíveis.
- **RF-021**: QUANDO um cliente externo se conectar ao servidor MCP, O SISTEMA DEVE exigir autenticação e operar local-first (sem exposição pública ingênua).

**Segurança / human-in-the-loop**
- **RF-022**: O SISTEMA DEVE manter allowlist de fonte única para as tools 3D, snapshots manuais, rollback explícito e auditoria como contrato (não opcional).
- **RF-023**: O SISTEMA NÃO DEVE liberar script livre, shell ou operações destrutivas no caminho feliz.

**Observabilidade**
- **RF-024**: O SISTEMA DEVE gerar trace por passo e disponibilizar logs e o relatório de verificação para leitura do dono.
- **RF-025**: O SISTEMA DEVE manter documentação dos melhores scripts de terminal para depurar as classes de erro do módulo 3D.

**Destino de fabricação**
- **RF-026**: QUANDO o usuário informar que o modelo é (ou não) para impressão 3D, O SISTEMA DEVE considerar esse destino e, quando aplicável, registrar artifact e relatório de printability.

### Requisitos não funcionais

- **RNF-001 (P1)**: O servidor MCP DEVE ser local-first — exposto via loopback/VPN/pareamento, nunca publicamente de forma ingênua; toda conexão externa autenticada. _(Requer ADR — ver `plan.md`.)_
- **RNF-002 (P5)**: O store transacional de produção é Postgres; JSON é apenas dev/test. Tocar storage explicita impacto em `postgres`, `json` e `auto`.
- **RNF-003 (P8)**: Allowlist de tools de fonte única; auditoria, snapshot e rollback obrigatórios em ações de alteração/deleção/high-risk.
- **RNF-004 (P9)**: Gates de qualidade (`ruff format --check`, `ruff check`, `pytest`; web `format:check`, `lint`, `test:unit`, `typecheck`, `build`) verdes nas áreas tocadas; artefatos em PT-BR.
- **RNF-005**: A reabertura da cobertura para assemblies/componentes (mudança no data model do plano) DEVE ser registrada em ADR antes de virar código. _(Reverte a decisão "single-body" do v3.)_
- **RNF-006 (P3/P9 — Clean Architecture)**: O código DEVE seguir clean architecture — camadas separadas (domínio / casos de uso / adapters / interface), sem regra de negócio em rotas e sem acoplamento que impeça teste. Qualidade de código é **não-negociável**.
- **RNF-007 (P4/P9 — Documentação dupla)**: Toda capacidade implementada DEVE ser documentada tanto no site **Docusaurus** (`apps/docs`, que serve `docs/`) quanto no **SDD** (`specs/005-...`), mantidos coerentes entre si e com o código.
- **RNF-008 (P9 — Testes)**: Toda capacidade implementada DEVE ter **testes unitários** cobrindo o comportamento, verdes nos gates de qualidade.
- **RNF-009 (Frontend — Nova UI)**: Toda UI 3D DEVE estar de acordo com a **nova UI em homologação na branch `homolog-new-ui`** (componentes, padrões visuais, navegação). _(Dependência: a branch precisa estar acessível no ambiente — ver `plan.md`, "Pendências de ambiente".)_

### Entidades-chave

- **Chat 3D**: sessão de modelagem; identidade 3D persistida; estágio atual (descoberta/planejamento/execução/edição); preferência de software e destino de impressão.
- **ModelingPlan**: plano proposto; `kind` (`primary`/`edit`); prosa + passos; risco por passo; estado de aprovação.
- **ModelingStep**: passo atômico do plano; tool allowlistada + args; valores dimensionais esperados.
- **ExecutionRun**: execução de um plano; iterações do loop de auto-correção; estado terminal (sucesso/falha) e snapshots associados.
- **VerificationResult**: esperado × medido (bbox, volume, contagens, dimensões) por passo verificado.
- **GeometrySnapshot**: estado salvo para rollback.
- **ToolRegistry/Capability**: allowlist de fonte única + capacidades suportadas por fase.
- **Trace/AuditEvent**: registro por passo para observabilidade e auditoria.
- **Artifact/PrintabilityReport**: exports e relatório de printability quando o destino for impressão.

## Critérios de sucesso *(obrigatória)*

- **CS-001**: A partir de um pedido com contexto suficiente e plano aprovado, o motor entrega o modelo **sem nenhuma intervenção manual** entre aprovação e término.
- **CS-002**: Para cada nível de capacidade entregue, existe **uma peça-exemplo** modelada por chat cujo resultado o dono valida como fiel ao pedido no Fusion real (gate por fase):
  - **Nível 1 — Sólido paramétrico** (ex.: suporte/“bracket” parametrizado com furos e fillets).
  - **Nível 2 — Superfície** (ex.: carenagem/“shell” com superfície NURBS espessada).
  - **Nível 3 — Sheet metal** (ex.: chapa dobrada com flanges e alívios).
  - **Nível 4 — Sculpt** (ex.: forma orgânica via T-Spline).
  - **Nível 5 — Assemblies** (ex.: caixa + tampa + parafusos como componentes com junta).
- **CS-003**: Em pontos de falha recuperáveis, o loop de auto-correção resolve sem intervenção em uma fração mensurável dos casos de teste, e **sempre** termina de forma explícita (sucesso ou falha reportada) em ≤ 5 iterações.
- **CS-004**: Toda execução produz trace por passo e relatório de verificação legíveis pelo dono.
- **CS-005**: Um cliente externo autenticado consegue listar e invocar tools 3D pelo servidor MCP, independente do backend do produto.

## Premissas

- O dono é o único validador no Fusion real; o container remoto é mock (sem Fusion/Windows). Daí o gate de validação por fase (`plan.md`).
- A cobertura "todo o Design" é o alvo; o `plan.md` a entrega em ondas priorizadas, não de uma vez.
- As peças-exemplo de `CS-002` são propostas e podem ser trocadas pelo dono por casos reais equivalentes.
- Blender permanece congelado-mas-mantido nesta frente (paridade fica para depois do v4).
- O **v4 é o guarda-chuva** e absorve o fidelity-roadmap v3 como workstream do motor de fidelidade (decisão do dono, 2026-05-23). Onde houver conflito de escopo, **vence o v4** (cobertura "todo o Design"); a lista "fora de escopo" do fidelity-roadmap (surfaces/sheet metal/sculpt) fica **superada** para as ondas de cobertura.
- Os assets `agent_loop.py`, `tool_schemas.py` e `build_correction_context` hoje vivem **não-commitados em outro worktree** (`master`); sua integração na branch v4 depende da convergência das branches (ver `plan.md` › Pendências de ambiente).

## Fontes *(obrigatória neste repo)*

- Constituição: `.specify/memory/constitution.md` (P1, P5, P6, P8, P9)
- Docs: `docs/3d-mcp-modeling.md`, `docs/architecture.md`, `docs/decisions.md` (ADR-012/013/014; novos ADR-017/018/019 a criar), `docs/infra-observability.md`, `docs/delivery-checklist.md`; site Docusaurus em `apps/docs/` (serve `docs/` cru via `path: "../../docs"`)
- Código (bounded context): `backend/app/modeling/` (`tool_registry.py`, `planner.py`, `planner_service.py`, `executor.py`, `chat_orchestrator.py`, `chat_state.py`, `fusion_adapter.py`, `fusion_mcp_scripts.py`, `mcp_servers/`, `attachment_analyzer.py`, `observability.py`, `snapshot_service.py`, `printability.py`; **absorvidos do fidelity-roadmap**: `agent_loop.py`, `tool_schemas.py`, `planner.build_correction_context`), `apps/web/src/features/modeling-3d/`, `apps/fusion-addin/`
- Plano absorvido (fidelity v3): `fidelity-roadmap.md` — **atualmente no worktree `master`, ainda não nesta branch** (a convergir); vira insumo dos micro-planos (Fases 2/4/8) sob o guarda-chuva v4
- Specs relacionadas: `specs/000-repo-foundation/`, e os insumos desta pasta (`adapter-gaps-roadmap.md`, `adapter-tools-mvp.md`, `chat-flow-redesign.md`, `observability-plan.md`, `g4-assemblies-decision.md` — a reabrir, `handoff.md`)
- Plano macro: `specs/005-modeling-3d-fusion/plan.md` | Micro-planos: `specs/005-modeling-3d-fusion/micro/`

## Dívida de código documentada *(documentar, não reescrever aqui)*

- **DT-001**: Tools das ondas C-F do adapter Fusion nunca rodaram contra Fusion real (APIs version-sensitive) em `backend/app/modeling/fusion_mcp_scripts.py` → validar na auditoria (Fase 0) e na fase de núcleo. Esforço: M. ADR? não.
- **DT-002**: Parametrização "assada" (`createByReal`) sem vínculo a parâmetro em dimensões de sketch em `fusion_mcp_scripts.py` → completar parametrização real (G1.2). Esforço: M. ADR? não.
- **DT-003**: Decisão "single-body" (ADR/`g4-assemblies-decision.md`) conflita com a cobertura-alvo "todo o Design" → reabrir via ADR-018 e reespecificar data model do plano. Esforço: L. ADR? **sim**.
- **DT-004**: Camada MCP atual é stdio interna (`mcp_servers/`) → evoluir para servidor standalone reutilizável (HTTP/SSE + auth) via ADR-017. Esforço: L. ADR? **sim**.
- **DT-005**: Snapshot/rollback é cópia de filesystem (`snapshot_service.py`, `workspace.py`), **não** estado nativo do Fusion (timeline/B-Rep) → rollback real (RF-011) inefetivo; redesenhar na Fase 2. Esforço: M. ADR? talvez.
- **DT-006**: `api/routes/chat_modeling.py` contém regra de negócio do fluxo 3D e **bypassa** o `ModelingChatOrchestrator` (state machine duplicada rota×orchestrator) → consolidar para clean architecture (RNF-006). Esforço: M. ADR? não.
- **DT-007**: Persistência em modo `auto` cai em JSON **silenciosamente** se o Postgres falhar (`storage/store.py`) → tornar explícito/observável em produção (RNF-002). Esforço: S. ADR? não.
- **DT-008**: `chat_state.py` trata `EXECUTION_FAILED` igual a sucesso (cai em `editing`), sem estado de falha/rollback → incoerente com RF-011. Esforço: S. ADR? não.
- **DT-009**: Caminho feliz envia script Python backend-owned via `featureType:"script"` (`fusion_adapter.py`) — respeita RF-023 na letra (script não é do LLM; `run_script` fora da allowlist do planner), mas a fronteira de segurança merece ADR explícito. Esforço: S. ADR? **sim (ADR-019)**.
- **DT-010**: `agent_loop.py` (absorvido do fidelity-roadmap) atualmente **bloqueia** delta corretivo high-risk aguardando aprovação (`_needs_correction` só trata `failed`); ajustar para a decisão do dono (aprovação do plano cobre corretivo; loop não pausa) **e** disparar correção também em **divergência geométrica**, não só em erro de tool. Esforço: M. ADR? não.

## Verificação de qualidade da spec

- [x] Sem detalhe de implementação nos requisitos (linguagem/framework/API)
- [x] Foco em valor; requisitos testáveis e sem ambiguidade
- [x] Critérios de sucesso mensuráveis e agnósticos de tecnologia
- [x] Sem marcadores `[ESCLARECER]` pendentes
- [x] Escopo delimitado; premissas e dependências identificadas
- [x] Seção **Fontes** com caminhos válidos; constituição referenciada
