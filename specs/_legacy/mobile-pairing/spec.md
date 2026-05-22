# spec.md

## Título

Mobile, pareamento local e cache offline

## Status

Decisões de produto aprovadas; implementação futura.

## Objetivo

Permitir Android como cliente pareado do backend desktop via QR code local, sem autenticação de usuário no MVP, com cache offline completo.

## Requisitos funcionais

- QUANDO o mobile parear com o desktop, O SISTEMA DEVE usar QR code local.
- QUANDO o mobile estiver pareado, O SISTEMA NÃO DEVE exigir autenticação de usuário no MVP.
- QUANDO o servidor desktop ficar indisponível, O SISTEMA DEVE oferecer cache offline completo disponível no dispositivo.
- QUANDO o estado de conectividade mudar, O SISTEMA DEVE indicar online/offline claramente.

## Requisitos não funcionais

- O desktop continua centro computacional.
- Acesso remoto deve priorizar rede privada/VPN, não porta pública ingênua.

## Fontes

- `docs/decisions.md`
- `docs/architecture.md`
- `specs/repo-foundation/spec.md`
