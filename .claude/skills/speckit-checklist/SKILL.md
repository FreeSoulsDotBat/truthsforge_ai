---
name: speckit-checklist
description: Use quando gerar um checklist de qualidade customizado para uma spec ou área (opcional). Para o gate de entrega ao dono, use docs/delivery-checklist.md.
---

## Objetivo

Produzir um checklist focado de validação (qualidade da spec, prontidão de uma área) a partir de `.specify/templates/checklist-template.md`.

## Passos

1. Copie `.specify/templates/checklist-template.md` para `specs/NNN-slug/checklists/<foco>.md`.
2. Customize os itens ao foco (ex.: qualidade de requisitos, segurança, acessibilidade).
3. Rode a validação item a item; documente falhas citando trechos da spec.

## Saída

Checklist preenchido em `specs/NNN-slug/checklists/`.

## Não faça

- não substituir o checklist obrigatório de entrega (`docs/delivery-checklist.md`);
- não embutir o checklist dentro da `spec.md`.
