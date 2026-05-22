---
name: speckit-clarify
description: Use quando reduzir ambiguidade de uma spec antes do plano, via perguntas estruturadas ao dono do produto.
---

## Objetivo

Resolver pontos subespecificados de `specs/NNN-slug/spec.md` antes de planejar.

## Passos

1. Extraia os marcadores `[ESCLARECER: ...]` da spec (e ambiguidades implícitas de alto impacto).
2. Priorize por impacto: escopo > segurança/privacidade > experiência > detalhe técnico. Máximo de 3 perguntas.
3. Apresente cada pergunta com opções em tabela (Opção / Resposta / Implicações) e aguarde a escolha do dono.
4. Aplique as respostas na spec, removendo os marcadores e ajustando requisitos/premissas.

## Saída

Spec sem `[ESCLARECER]` pendentes e com decisões registradas.

## Não faça

- não inventar respostas para decisões de alto impacto;
- não fazer mais de 3 perguntas por rodada.
