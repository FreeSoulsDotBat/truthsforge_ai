# Decisão de escopo — G4: assemblies, componentes, joints e materiais

> **Status:** AGUARDANDO DECISÃO DO DONO DO PRODUTO. Não implementar antes.
> **Autor:** Claude Code, 2026-05-20.
> **Contexto:** fase G4 da `adapter-gaps-roadmap.md`. As fases G1-G3/G5 foram
> entregues; G4 foi deixada para o fim porque muda a arquitetura e precisa
> de decisão de produto antes de virar código.

## 1. Por que isto é uma decisão, não só mais uma onda

Todas as 47 tools atuais operam no **root component** com **bodies soltos**.
Assemblies introduzem um nível estrutural novo (componentes, ocorrências,
juntas) que afeta:

- **O modelo de dados** do plano 3D (hoje "um design = N bodies"; viraria
  "um design = árvore de componentes com ocorrências e juntas").
- **Os selectors e refs** (G2.2/G2.3): referenciar `Componente > ocorrência
  > body > face` é mais profundo que `body > face`.
- **A UI/diagnóstico** (o card e o modal assumem lista linear de steps sobre
  um design plano).
- **Printability** (peças de assembly podem precisar ser exportadas
  separadas ou montadas; afeta `validate_printability` e exports).

Construir isso "às cegas" sem alinhar o produto correria risco de retrabalho
grande. Daí a spec separada de decisão.

## 2. O que assemblies habilitariam

- **Montagens reais**: caixa + tampa + parafusos como peças distintas que se
  encaixam, com folga e juntas (revolute/slider) — não um body monolítico.
- **Reuso**: um componente "parafuso M3" instanciado N vezes (vs. patternar
  geometria).
- **Movimento/cinemática**: dobradiças, gavetas, mecanismos.
- **BOM / contagem de peças** para fabricação.
- **Materiais físicos por componente** (massa, centro de gravidade reais em
  `validate_dimensions`).

## 3. O que NÃO precisa de assemblies (já cobre hoje)

- Peças únicas imprimíveis (a vasta maioria de print 3D doméstico).
- Multi-body num design (já dá pra ter vários bodies; `combine_bodies` junta).
- Padrões de geometria repetida (`pattern_*`).

Ou seja: **para impressão 3D de peça única, assemblies é over-kill.** O valor
aparece em produtos montados, mecanismos e fabricação com BOM.

## 4. Opções de escopo

### Opção A — Não fazer (manter single-body)
- **Prós:** zero risco arquitetural; foco no caso dominante (peça imprimível);
  G1.2/G2/G3 já dão muita capacidade.
- **Contras:** sem montagens/mecanismos; reuso só por pattern de geometria.
- **Quando faz sentido:** se o produto é "modele uma peça pra imprimir".

### Opção B — Componentes leves, sem juntas
- Escopo: `create_component`, `add_body_to_component`, `move_component`,
  multi-export (um STL por componente). Sem juntas/cinemática.
- **Prós:** habilita montagens estáticas (caixa+tampa separadas) e BOM
  simples; risco arquitetural moderado.
- **Contras:** sem movimento; ainda exige mudança no modelo de plano.
- **Quando faz sentido:** se o produto quer "kits" de peças relacionadas.

### Opção C — Assemblies completo (componentes + juntas + materiais)
- Escopo: B + `create_joint` (rigid/revolute/slider/cylindrical), materiais
  físicos, contact sets.
- **Prós:** modelagem mecânica de verdade.
- **Contras:** maior esforço; muda data model, UI, printability, exports;
  APIs de joint do Fusion são complexas e version-sensitive (alto risco G5).
- **Quando faz sentido:** se o produto vira ferramenta de engenharia mecânica.

## 5. Recomendação

**Opção A por enquanto**, reavaliar para **B** quando surgir demanda real de
montagens. Razões:

1. O caso dominante (peça única imprimível) está bem servido pelas 47 tools +
   G1-G3.
2. B/C exigem mudança no **data model do plano** e na **UI** — fora do
   bounded context atual do adapter; seria uma nova épica multi-camada.
3. Sem evidência de uso (os testes até agora foram peças únicas), construir
   assemblies é especular. Melhor esperar um pedido concreto.

Se aprovarem B/C, o próximo passo é uma **spec de arquitetura** cobrindo:
data model do plano com componentes, mudanças em selectors/refs, UI do card,
printability/export por componente, e plano de risco das APIs de joint.

## 6. Decisão registrada

- [ ] Opção A — manter single-body (recomendada)
- [ ] Opção B — componentes leves sem juntas
- [ ] Opção C — assemblies completo
- [ ] Adiar decisão

**Decidido por:** ____________  **Data:** ____________
