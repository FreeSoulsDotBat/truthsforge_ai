---
name: repo-map
description: Use quando precisar mapear o monorepo, decidir onde implementar uma mudança, entender bounded contexts ou localizar a documentação fonte de verdade.
---

## Objetivo

Explicar rapidamente onde vivem código, docs, runtime e responsabilidades no `truthsforge_ai`.

## Sempre consultar primeiro

- `.specify/memory/constitution.md` (invariantes não-negociáveis do projeto)
- `specs/README.md` (catálogo de specs `NNN-` e padrão Spec Kit)
- `README.md`
- `docs/application-map.md`
- `docs/architecture.md`
- `docs/decisions.md`
- `docs/implementation-plan.md`
- `docs/mvp-readiness.md`
- `specs/000-repo-foundation/spec.md`

## Saída esperada

Responder com:

1. diretório principal a alterar;
2. bounded context envolvido;
3. fontes de verdade que devem ser lidas antes da mudança;
4. riscos de tocar mais de uma stack ao mesmo tempo.

## Não faça

- não proponha reestruturação de pastas sem necessidade;
- não trate wrappers desktop/mobile como centros de domínio;
- não ignore `docs/` ou `specs/` ao explicar o repositório.
