# Plano de implementação: Shells Mobile/Desktop e Pareamento

**Pasta da spec**: `specs/100-mobile-desktop-shells/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Consolida o legado `mobile-pairing` e registra dívida (DT-001..004).

## Resumo

Desktop (Tauri, `apps/desktop/src-tauri/`) é o centro; mobile (Capacitor, `apps/mobile/`) é cliente pareado via QR local, sem auth no MVP, com cache offline. QR/online-offline/cache ainda não implementados.

## Contexto técnico

- **Plataforma-alvo**: Tauri (Windows desktop), Capacitor (Android).
- **Tipo de projeto**: shells · **Testes**: e2e/manual (futuro).

## Constitution Check

- [x] P1 Local-first, desktop no centro (núcleo).
- [x] P3 Preservar arquitetura (doc-only).
- [x] P9 Qualidade/PT-BR.

Sem violações.

## Estrutura

```text
apps/desktop/src-tauri/   # wrapper Windows
apps/mobile/              # wrapper Android (Capacitor)
```

## Estratégia / Ondas

1. Esta onda: consolidar spec + migrar legado + dívida.
2. Futuro: QR local; indicador online/offline; cache offline; instaladores.

## Validação

- Doc-only: cross-links resolvem; legado em `_legacy/`. Futuro: e2e de pareamento/offline.

## Riscos e trade-offs

- Pareamento sem auth no MVP exige rede privada/VPN (ADR-006) — risco se exposto publicamente.

## Rastreamento de complexidade

Sem violações.
