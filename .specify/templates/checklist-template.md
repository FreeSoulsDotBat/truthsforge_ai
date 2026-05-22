# Checklist: [NOME DA FEATURE]

**Propósito**: validar [qualidade da spec / prontidão de uma área] antes de avançar de fase.
**Criado em**: [DATA] | **Spec**: `specs/[NNN-slug]/spec.md`

> Gerado na fase `checklist`. Customize os itens ao foco do checklist. Para o gate de entrega ao dono do produto, use sempre `docs/delivery-checklist.md` (obrigatório) — este arquivo é complementar.

## Qualidade de conteúdo

- [ ] Sem detalhe de implementação (linguagem/framework/API) nos requisitos
- [ ] Foco em valor para o operador e regra de domínio
- [ ] Seções obrigatórias da spec preenchidas

## Completude dos requisitos

- [ ] Nenhum marcador `[ESCLARECER]` pendente
- [ ] Requisitos (EARS RF-###) testáveis e sem ambiguidade
- [ ] Critérios de sucesso mensuráveis e agnósticos de tecnologia
- [ ] Cenários de aceitação definidos; casos de borda identificados
- [ ] Escopo delimitado; premissas e dependências identificadas

## Aderência à constituição

- [ ] Spec cita `.specify/memory/constitution.md` em **Fontes**
- [ ] Nenhum requisito viola um princípio sem justificativa em "Rastreamento de complexidade"
- [ ] Caminhos citados em **Fontes** existem (cross-links válidos)

## Prontidão da feature

- [ ] Todo requisito funcional tem critério de aceitação claro
- [ ] Histórias cobrem os fluxos primários
- [ ] **Dívida de código documentada** registrada (não executada nesta frente)

## Notas

- Itens incompletos exigem atualização da spec antes de `clarify`/`plan`.
- Antes da entrega final: aplicar `docs/delivery-checklist.md` e `.github/pull_request_template.md`.
