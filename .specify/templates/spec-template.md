# Especificação: [NOME DA FEATURE]

**Pasta da spec**: `specs/[NNN-slug]/` | **Criada em**: [DATA] | **Status**: Rascunho

**Entrada**: Descrição do dono do produto: "$ARGUMENTS"

> Idioma: PT-BR (nomes/comandos Spec Kit em inglês). Seções marcadas *(obrigatória)* são exigidas; remova seções opcionais que não se aplicam (não deixe "N/A").

## Cenários de usuário e testes *(obrigatória)*

Histórias priorizadas como jornadas (P1 = mais crítica). Cada história deve ser **testável de forma independente**: implementar só ela ainda entrega valor (MVP fatiável).

### História 1 — [Título breve] (Prioridade: P1)

[Descreva a jornada em linguagem simples.]

**Por que esta prioridade**: [valor e justificativa]

**Teste independente**: [como validar isoladamente]

**Cenários de aceitação**:

1. **Dado** [estado inicial], **Quando** [ação], **Então** [resultado esperado]
2. **Dado** [estado inicial], **Quando** [ação], **Então** [resultado esperado]

---

### História 2 — [Título breve] (Prioridade: P2)

[...]

---

### Casos de borda

- O que acontece quando [condição-limite]?
- Como o sistema trata [cenário de erro]?

## Requisitos *(obrigatória)*

### Requisitos funcionais

Use a forma EARS já adotada no repo ("QUANDO … O SISTEMA DEVE …", "ENQUANTO …", "O SISTEMA PODE …") com ID rastreável:

- **RF-001**: QUANDO [evento/condição], O SISTEMA DEVE [capacidade testável].
- **RF-002**: QUANDO [condição não suportada], O SISTEMA DEVE [falhar de forma explícita / degradar].
- **RF-003**: O SISTEMA PODE [comportamento opcional permitido pela policy].

Marque incertezas com no máximo 3: `[ESCLARECER: pergunta específica]`.

### Requisitos não funcionais

- **RNF-001**: O SISTEMA DEVE [arquitetura/segurança/custo/performance]. _(Aderência aos princípios da constituição.)_

### Entidades-chave *(se houver dados)*

- **[Entidade]**: [o que representa, atributos e relações — sem detalhe de implementação]

## Critérios de sucesso *(obrigatória)*

Mensuráveis e agnósticos de tecnologia:

- **CS-001**: [métrica verificável, ex.: "o operador conclui X em menos de N segundos"]
- **CS-002**: [métrica de qualidade/volume]

## Premissas

- [Premissa/depêndencia assumida como default razoável.]

## Fontes *(obrigatória neste repo)*

Links cruzados para a fonte de verdade (todos os caminhos devem existir):

- Constituição: `.specify/memory/constitution.md`
- Docs: `docs/...`
- Código (bounded context): `backend/app/...` e/ou `apps/web/src/...`
- Specs relacionadas: `specs/...`

## Dívida de código documentada *(neste repo; não executar aqui)*

Registre a dívida técnica deste domínio para trabalho futuro guiado por LLM. **Documentar, não reescrever.**

- **DT-001**: [problema] em `caminho/arquivo` → [direção proposta]. Esforço: [S/M/L]. ADR necessário? [sim/não].

## Verificação de qualidade da spec

- [ ] Sem detalhe de implementação nos requisitos (linguagem/framework/API)
- [ ] Foco em valor; requisitos testáveis e sem ambiguidade
- [ ] Critérios de sucesso mensuráveis e agnósticos de tecnologia
- [ ] Sem marcadores `[ESCLARECER]` pendentes
- [ ] Escopo delimitado; premissas e dependências identificadas
- [ ] Seção **Fontes** com caminhos válidos; constituição referenciada
