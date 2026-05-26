# Spec — Roadmap de gaps do adapter Fusion (pós-MVP)

> **Status:** proposta, aguardando priorização do dono do produto.
> **Autor:** Claude Code, 2026-05-20.
> **Pré-requisito:** Ondas A-F entregues (47 tools). Ver
> `adapter-tools-mvp.md` (escopo MVP) e `handoff.md` (Onda 8).
> **Relacionado:** `fusion_mcp_scripts.py`, `tool_registry.py`,
> `planner.py`, `observability-plan.md`.

## 1. Contexto

Com as Ondas A-F o adapter monta a maioria das peças (primitivas, revolução,
furos, padrões, booleanos). Mas a auditoria pós-MVP identificou 4 classes de
limitação que impedem modelagem profissional plena. Esta spec organiza a
cobertura desses gaps em fases priorizadas por **valor / custo**.

Resumo das fases:

| Fase | Tema | Valor | Custo | Prioridade |
|---|---|---|---|---|
| G1 | Parametrização real | altíssimo | médio | P0 |
| G2 | Selectors finos | alto | médio-alto | P1 |
| G3 | Gaps de features | médio | médio (incremental) | P2 |
| G4 | Assemblies/componentes | médio | alto | P3 (epic) |
| G5 | Validação real C-F | confiabilidade | baixo | P1 (contínuo) |

## 2. Fase G1 — Parametrização real (P0)

### Problema

As tools resolvem valores para número fixo em mm na hora de desenhar
(`_eval_param` → `createByReal(numero)`). O sketch nasce com `22.0 cm`
literal, **sem vínculo** ao user parameter. Mudar `Diameter_mm` depois no
Fusion **não atualiza** a geometria. Os parâmetros existem mas não dirigem
o modelo — ele não é editável-por-parâmetro.

### Insight central

`adsk.core.ValueInput.createByString("Diameter_mm")` cria um **vínculo
paramétrico** (dependência real ao parâmetro/expressão), enquanto
`createByReal(22.0)` **assa** o número. A maior parte da fidelidade
paramétrica vem de trocar `createByReal` por `createByString` **quando o
arg original era uma referência a parâmetro/expressão**.

### Abordagem incremental

**G1.1 — Distâncias de feature (ganho rápido, baixo risco).**
Para extrude `distance_mm`, revolve `angle_deg`, fillet `radius_mm`,
chamfer `distance_mm`, shell `thickness_mm`, hole `depth_mm`,
primitivas (`add_box` w/d/h, `add_cylinder`, etc.): se o arg veio como
nome de parâmetro ou expressão, passar via `createByString(expr)` em vez
de `createByReal`. Geometria de feature passa a referenciar o parâmetro.

Novo helper em `fusion_mcp_scripts.py`:
```
def _param_value_input(arg, design, fallback_mm_to_cm=True):
    # Se arg é número -> createByReal(numero/10).
    # Se arg é nome de param existente OU expressão que referencia params
    #   -> createByString(expr) (Fusion resolve + cria dependência).
    # Senão, se string numérica -> createByReal.
```
`_eval_param` continua existindo para validação (checar > 0 etc.); o
`_param_value_input` é usado no ponto onde se cria o ValueInput.

**G1.2 — Dimensões de sketch (ganho profundo, maior custo).**
Para que retângulos/círculos/polígonos sejam editáveis, após desenhar é
preciso adicionar **sketch dimensions** e setar a expressão para o
parâmetro (`sketchDimensions.addDistanceDimension(...)` + `.parameter.expression = "album_width_mm"`). Isso amarra a geometria 2D ao parâmetro.
Mais complexo (precisa escolher os pontos certos para dimensionar). Fazer
por tool, começando por `add_rectangle` e `add_circle`.

**G1.3 — Auto-criar parâmetros faltantes.** Quando uma tool recebe uma
expressão referenciando um parâmetro que não existe, criar
automaticamente (ou retornar erro claro). Hoje `_eval_param` retorna
default silencioso — pegar isso no trace.

### Arquivos
`fusion_mcp_scripts.py` (helper + call sites de cada tool dimensional),
`planner.py` (system prompt: instruir o LLM a passar nomes de parâmetro
nos campos dimensionais quando quiser modelo editável), testes.

### Risco
`createByString` com expressão inválida lança no Fusion — capturar e
retornar `fusion.invalid_expression` com a expressão no payload do trace.

## 3. Fase G2 — Selectors finos (P1)

### Problema

`_select_edges`/`_select_faces` só fazem `all`/`top`/`bottom`/`vertical`/
`horizontal` por heurística de Z. Impossível mirar faces laterais,
cilíndricas, "as arestas daquele bolso", tangent chains, ou geometria
diagonal. Pattern/mirror operam só sobre bodies inteiros, não features.

### Abordagem

**G2.1 — Mais selectors semânticos** em `_select_edges`/`_select_faces`:
- orientação: `+x`/`-x`/`+y`/`-y`/`+z`/`-z` (normal da face / direção da aresta)
- tipo de face: `planar`/`cylindrical`/`conical`
- tamanho: `longest`/`shortest`, `longer_than_mm`, `largest_face`
- posição: `near=[x,y,z]` com raio de tolerância (aresta/face mais próxima)
- contagem: `top_n` para limitar

**G2.2 — Tool read-only `fusion.query_geometry`.** Retorna lista de
faces/arestas/bodies com id estável + metadados (posição do centroide,
área, tipo, bbox). O LLM chama, recebe ids, e os usa em selectors do
tipo `edge_ids=[...]`. Resolve o problema de "não sei o que selecionar"
sem o LLM precisar adivinhar tokens. Categoria `read_only`.

**G2.3 — Referência estável a features.** Tools que criam feature
(extrude, revolve, primitivas) passam a aceitar `result_name` e o adapter
nomeia a feature/body de forma estável. pattern/mirror passam a aceitar
`feature_ref` por esse nome (não só body). Ataca o "drift de identidade"
do handoff.

### Arquivos
`fusion_mcp_scripts.py` (selectors + nova tool + nomeação de features),
`tool_registry.py` (query_geometry read_only), `planner.py` (prompt:
fluxo query → select), testes.

### Risco
`query_geometry` retorna payloads grandes em peças complexas — usar o
truncate de payload do tracer (já existe) e limitar contagem.

## 4. Fase G3 — Gaps de features (P2, incremental)

Cada item é independente; implementar sob demanda conforme prompts reais
pedirem. Ordenados por frequência esperada:

| Tool | Nota |
|---|---|
| `fusion.hole` v2 | usar `holeFeatures` real: counterbore/countersink/tapped via `type` |
| `fusion.add_ellipse`, `fusion.add_slot` | primitivas de sketch comuns |
| `fusion.draft_faces` | ângulo de saída (peças moldadas/impressas) |
| `fusion.rib` | reforços |
| `fusion.thicken` | surface→solid (depende de surfaces, ver G4) |
| `fusion.split_body` | dividir corpo por plano/face |
| fillet variável | raio por aresta / chord-length |
| chamfer 2-distâncias | distância+ângulo |
| construction plane | por ângulo / 3 pontos / tangente |
| ~~`move_body` rotação~~ ✅ Fase 4 | `rotation_deg` + `axis` (x/y/z ou vetor) + `center_mm`; backward-compat com translação |
| `fusion.add_text` | texto gravado/em relevo |

### Arquivos
Mesmo padrão das ondas A-F (template + dispatch + tupla + registry +
prompt + teste de compile/contrato).

## 5. Fase G4 — Assemblies, componentes e materiais (P3, epic separado)

Grande o suficiente para spec própria quando priorizado. Inclui:

- **Componentes** (multi-body → componentes nomeados), ocorrências.
- **Joints** (rigid/revolute/slider/...) e as-built joints.
- **Materiais físicos** (afeta massa/volume em `validate_dimensions`) e
  aparência/cor.
- **Posicionamento relativo** (align, joint-based) — hoje só translação.

Decisão pendente: assemblies fazem parte do produto 3D ou ficam fora do
escopo local-first? Alinhar com o dono antes de specar.

## 6. Fase G5 — Validação real de C-F (P1, contínuo)

As ondas C-F nunca rodaram contra Fusion real. APIs sensíveis a versão:

- `chamferFeatures.createInput` vs `createInput2`
- `moveFeatures.createInput` / `scaleFeatures.createInput` (deprecadas)
- `rectangularPatternFeatures.createInput` (assinatura + `PatternDistanceType`)
- `createPath` no sweep
- selectors de aresta/face em geometria curva

### Abordagem
- Smoke manual por tool com prompt representativo; capturar trace_id.
- Onde a API varia por versão, envolver em `try/except` testando
  `createInput2` primeiro com fallback para `createInput` — registrar qual
  caminho funcionou no payload do trace.
- Adicionar ao `scripts/smoke-modeling-trace.ps1` uma bateria por tool.

## 7. Ordem recomendada

1. **G5** em paralelo a tudo (valida o que já existe conforme o usuário testa).
2. **G1.1** — parametrização de distâncias de feature (ganho rápido, alto valor).
3. **G2.1 + G2.2** — selectors semânticos + `query_geometry`.
4. **G1.2** — dimensões de sketch paramétricas.
5. **G2.3** — referência estável a features.
6. **G3** — features sob demanda.
7. **G4** — epic de assemblies (decisão de escopo primeiro).

## 8. Fora de escopo (mesmo pós-gaps)

Sheet metal, sculpt/T-Spline, surfaces NURBS avançadas, simulação (FEA),
CAM/usinagem, generative design, drawings 2D, render fotorrealista,
import de CAD externo. Reavaliar só se o produto pedir explicitamente.
