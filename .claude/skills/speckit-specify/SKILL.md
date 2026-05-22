---
name: speckit-specify
description: Use quando transformar a intenção do dono do produto numa spec nova (specs/NNN-slug/spec.md). Foco no "o quê/por quê", nunca no "como".
---

## Objetivo

Criar uma especificação rastreável a partir de uma descrição em linguagem natural, seguindo `.specify/templates/spec-template.md` e a constituição.

## Passos

1. Crie a pasta e a spec a partir do template (numeração `NNN-` automática, múltiplo de 10):
   - Windows: `.specify/scripts/powershell/create-new-feature.ps1 -Slug <slug> [-Number NNN]`
   - bash: `.specify/scripts/bash/create-new-feature.sh <slug> [number]`
2. Preencha `spec.md`: histórias priorizadas (P1/P2/P3) com teste independente; requisitos funcionais em **EARS** (`RF-###`: "QUANDO … O SISTEMA DEVE …"); requisitos não funcionais; critérios de sucesso mensuráveis e agnósticos de tecnologia.
3. Preencha a seção **Fontes** com cross-links válidos (constituição + `docs/` + caminhos de código reais) e o bloco **Dívida de código documentada** (documentar, não reescrever).
4. Máximo de 3 marcadores `[ESCLARECER]`; o resto vira **Premissa**.
5. Valide pela "Verificação de qualidade da spec" no fim do template.

## Saída

`specs/NNN-slug/spec.md` + `handoff.md` stub; pronto para `speckit-clarify` ou `speckit-plan`.

## Não faça

- não incluir stack, API ou estrutura de código (isso é do `plan`);
- não exceder 3 esclarecimentos;
- não deixar caminhos inexistentes em **Fontes**.
