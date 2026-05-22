---
name: mobile-shells
description: Use ao trabalhar com Tauri, Capacitor, empacotamento desktop/mobile, pareamento, conectividade local e cache do cliente móvel.
---

## Objetivo

Manter desktop e mobile como shells coerentes com o frontend principal e com o modelo local-first.

## Sempre consultar primeiro

- `apps/mobile/README.md`
- `apps/desktop/src-tauri/tauri.conf.json`
- `docs/architecture.md`
- `docs/local-dev.md`
- `docs/mvp-readiness.md`
- `specs/000-repo-foundation/spec.md`

## Regras

- o desktop continua sendo o centro computacional do produto;
- o mobile continua cliente pareado do desktop;
- não trate o mobile como backend independente;
- HTTPS público não é o caminho padrão inicial;
- preserve a ideia de cache offline completo quando esse fluxo for evoluído.

## Entrega mínima

- explicitar impacto em desktop, web e mobile;
- documentar qualquer novo requisito de ambiente;
- registrar dependências de pareamento, rede local ou VPN.
