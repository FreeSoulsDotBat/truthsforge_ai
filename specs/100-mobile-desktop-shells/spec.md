# Especificação: Shells Mobile/Desktop e Pareamento

**Pasta da spec**: `specs/100-mobile-desktop-shells/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Cobrir os wrappers desktop (Tauri) e mobile (Capacitor) e o pareamento local. **Migra e supersede** o legado `mobile-pairing` (arquivada em `specs/_legacy/mobile-pairing/`).

> Onda 10 do refactor SDD. Documenta os shells e o pareamento QR local; registra a dívida (QR, online/offline, cache).

## Cenários de usuário e testes

### História 1 — Desktop como centro (Prioridade: P1) 🎯 MVP

O frontend web empacotado em Tauri roda como centro local do produto.

**Cenários de aceitação**:

1. **Dado** o app desktop, **Quando** empacotado (Tauri), **Então** continua tratando o desktop como centro local (`apps/desktop/src-tauri/`).

### História 2 — Mobile como cliente pareado (Prioridade: P1)

Android (Capacitor) pareia com o desktop via QR local, sem autenticação de usuário no MVP, com cache offline.

**Cenários de aceitação**:

1. **Dado** o app mobile, **Quando** pareia, **Então** usa QR code local sem exigir autenticação de usuário (ADR-011).
2. **Dado** servidor indisponível, **Quando** offline, **Então** o sistema oferece cache offline e indica online/offline claramente.

### Casos de borda

- Acesso remoto prioriza VPN/rede privada, não porta pública ingênua (ADR-006).

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO o frontend for empacotado para desktop, O SISTEMA DEVE tratar o desktop como centro local (`apps/desktop/`). _(migrado)_
- **RF-002**: QUANDO o mobile parear com o desktop, O SISTEMA DEVE usar QR code local. _(migrado)_
- **RF-003**: QUANDO o mobile estiver pareado, O SISTEMA NÃO DEVE exigir autenticação de usuário no MVP. _(migrado)_
- **RF-004**: QUANDO o servidor ficar indisponível, O SISTEMA DEVE oferecer cache offline completo. _(migrado)_
- **RF-005**: QUANDO a conectividade mudar, O SISTEMA DEVE indicar online/offline. _(migrado)_

### Requisitos não funcionais

- **RNF-001**: O desktop continua centro computacional; acesso remoto prioriza VPN (ADR-006). _(migrado)_

## Critérios de sucesso

- **CS-001**: Pareamento mobile ocorre via QR local sem autenticação no MVP.
- **CS-002**: Estado online/offline é claro e o cache offline funciona quando o servidor cai.

## Premissas

- Empacotamento final (instaladores) é trabalho posterior ao dev loop estável (ADR-003).

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `apps/desktop/src-tauri/` (`tauri.conf.json`, `src/lib.rs`, `src/main.rs`), `apps/desktop/package.json`; `apps/mobile/capacitor.config.ts`, `apps/mobile/README.md`
- Docs: `docs/decisions.md` (ADR-003, ADR-006, ADR-011), `docs/architecture.md`
- Legado migrado: `specs/_legacy/mobile-pairing/`
- Specs relacionadas: `specs/090-frontend-web-shell/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: Contrato de QR local não implementado. Direção: endpoint de pairing + geração/leitura de QR. Esforço: M.
- **DT-002**: Indicador online/offline ausente. Direção: estado de conectividade no shell. Esforço: S.
- **DT-003**: Cache offline completo no mobile não implementado. Direção: cache local no cliente pareado. Esforço: L.
- **DT-004**: Empacotamento Tauri/Capacitor como instalador final pendente (`docs/mvp-readiness.md`). Esforço: L.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Conteúdo do legado migrado; dívida documentada
