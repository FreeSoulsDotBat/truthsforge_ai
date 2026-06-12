# Débito técnico — Refatoração de POSICIONAMENTO (motor genérico)

**Status**: aberto · **Criado**: 2026-06-02 · **Spec**: [`spec.md`](./spec.md) · **Índice**: [`tasks.md`](./tasks.md)

> Decisão do dono (2026-06-02): o gargalo que falta — **posicionamento relativo
> de bodies** — é arquitetural e **não fecha só com os fixes incrementais**
> atuais. Será endereçado numa **refatoração grande dedicada** (a ser planejada
> pelo dono). Este documento **congela o débito** acumulado para essa
> refatoração resolver. Os fixes incrementais ficam pausados.

## 1. O problema central (mandato da refatoração)

O sistema já compõe peças de primitivas + features genéricas, renderiza, critica
por visão e replaneja (motor genérico, validado no Fusion real). **O que falha é
o POSICIONAMENTO**: o LLM coloca/orienta cada body por **coordenadas absolutas
chutadas** (`origin_mm`/`center_mm`) em vez de **ancorar de forma robusta à
geometria real** (arestas/faces/bodies consultados). Sintomas reais dos gates:

- knuckles da dobradiça no **lado errado** / orientação errada;
- pino **flutuando** gigante fora da peça;
- tampa **deslocada** e **não conectada**;
- bodies construídos **fora de lugar** / referência a bodies que não existem.

A camada de inteligência (F1 estado rico, F2 hierárquico, loop visual) **expõe**
o estado e **critica** o erro, mas a **decisão de posição** continua frágil.

## 2. Por que o incremental não fecha (diagnóstico)

- **Não há primitiva de ancoragem.** Para pôr um nó "na aresta de cima de 60 mm
  centrado na espessura", o LLM precisa **calcular coordenadas na mão** a partir
  do `query_geometry`. Isso é exatamente onde ele erra. Falta um conceito de
  "ancorar a/alinhar com/distribuir ao longo de" uma face/aresta/eixo.
- **Primitivas com origem/eixo ad-hoc.** `add_box` é XY; `add_cylinder` ganhou
  `axis` (2026-06-02) mas o posicionamento da base ainda é coordenada crua.
- **As macros mascaravam isso.** `knuckle_hinge`/`metric_screw` (deprecados)
  escondiam o posicionamento num molde rígido; removê-los expôs a fraqueza —
  que é a coisa certa a resolver, não a esconder de novo.
- **O loop visual ajuda mas não converge** em mecanismos intrincados: a crítica
  é precisa, mas a **edição corretiva** não consegue traduzir "está no lado
  errado" em reposicionamento confiável (mesmo gargalo de coordenadas).

> Candidatos a explorar na refatoração (NÃO decididos — a cargo do dono):
> sistema de **referências/constraints geométricas** (ancorar a token de
> face/aresta F1), **frames/datums** por body, distribuição paramétrica ao longo
> de aresta, montagem por **joints/as-built** em vez de coordenadas, ou um
> solver de posição que consome o `ModelState` + a crítica visual.

## 3. Itens de débito acumulados (para a refatoração varrer)

### 3.1 Posicionamento e orientação (núcleo) — ▶ ENDEREÇADO por **F7** (ADR-022, `micro/fase-F7-posicionamento.md`)
- [ ] Primitiva/conceito de **ancoragem** a face/aresta/eixo (token F1) — colar,
  alinhar, centrar na espessura, distribuir N ao longo de aresta.
- [ ] Posição **relativa** entre bodies (encostar A em B, offset por face) sem
  coordenada crua.
- [ ] `add_box`/demais primitivas com **origem/eixo** explícitos e consistentes.
- [ ] Knuckles de dobradiça: distribuição automática (N nós, largura axial,
  folga) ao longo da aresta — hoje o LLM enumera cada cilindro.

### 3.2 Validação no Fusion de geometria escrita ÀS CEGAS (preciso de gate)
> Foram implementadas sem Fusion à mão; lógica plausível, **não confirmada**.
- [ ] `add_cylinder` `axis` (rotação Z→eixo via `_rotate_body`/`setToRotation`) —
  direção do giro, pivô e posição final.
- [ ] `participantBodies` no cut/intersect de `_extrude_profile`.
- [ ] `thread` (ThreadFeatures Modeled), `joint` (JointGeometry), `make_component`.
- [ ] `_capture_viewport` (`saveAsImageFile`) — render real + tamanho do payload.

### 3.3 Loop de verificação visual (`visual_critique.py`)
- [ ] **Convergência** em mecanismos difíceis (hoje teto 2 rodadas; correção nem
  sempre traduz a crítica em conserto).
- [ ] **Multi-view** (iso+top+front) numa crítica; hoje 1 view (iso).
- [ ] Comparar contra a **imagem de referência** (image-to-model), não só a
  intenção textual.
- [ ] Custo/latência (1 render + 1 vision call + 1 replan por rodada).

### 3.4 Resíduos das frentes F1–F6
- [ ] **F1**: selectors por token nas surface tools (patch/extend/offset/unstitch).
- [ ] **F2**: `replan_next_block` explícito (hoje aborta no bloco que falha);
  verifier de aceite via LLM (hoje usa status do bloco).
- [ ] **F4.2**: bloco de imagem direto no `generate_structured` do planner (ver o
  pixel, não só a descrição); múltiplas imagens; modelo de visão mais forte.
- [ ] **F5**: diff estruturado snapshot↔ao-vivo (hoje só anexa os dois blocos).
- [ ] **F6**: 9.4 verifier LLM atrás de flag; 9.5 templates por padrão frequente.

### 3.5 Limpeza / dívida de manutenção — ▶ parcialmente em **F7** (combine×joint via combine-DENTRO/joint-ENTRE)
- [ ] **Macros deprecadas** (`knuckle_hinge`/`metric_screw`): handlers ainda no
  adapter (`DEPRECATED_PLANNER_TOOLS`) — decidir remover de vez vs. manter p/
  smoke. `add_circle`/`add_cylinder` têm batch; padronizar batch nas primitivas.
- [ ] **DT-005**: snapshot/rollback nativo do Fusion (loop ainda
  `rollback_skipped`).
- [ ] `trim_surface` known-issue (seleção de cells).
- [ ] E501 pré-existentes em `fusion_mcp_scripts.py` (15) e `tool_registry.py`
  (1) — baseline herdado, fora do escopo dos fixes recentes.

### 3.6 Paradigma não suportado
- [ ] **Print-flat / flat-pack** (padrão plano dobrável / living hinge — o que a
  imagem da Panini realmente é): mais perto do *flat pattern* de chapa
  (congelado, DT-011) que do solid modeling. Decidir se entra no escopo.

## 4. O que JÁ está validado (não é débito)
Núcleo (Fases 2–5), F1, F2 com gate Fusion aprovado; **motor genérico validado
no Fusion real (2026-06-02)**: o loop visual renderizou, criticou com precisão
("knuckle hinge missing", "pin missing", "wrong place") e replanejou 3 rodadas.
A pipeline funciona; o **posicionamento** é o que a refatoração ataca.

## 5. Como esta dívida foi acumulada (rastro)
Commits da virada motor-genérico + fixes do gate (branch `feat/3d-modelling-updates`,
PR #46): `f198f6b` (add_cylinder batch), `dce2450` (add_cylinder axis),
`1f01db7` (chat novo = doc novo), `1e68ab4` (loop visual), `146fe8f`
(capture_viewport), `a211826` (deprecа macros). Ver `gate-homologacao.md` ›
Gate Visual.
