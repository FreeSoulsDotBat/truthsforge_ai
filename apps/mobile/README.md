# Truth's Forge AI Mobile

Scaffold Capacitor para Android. O app mobile usa o mesmo build de `apps/web` e acessa o backend desktop via Tailscale/WireGuard ou Wi-Fi local.

Primeiro ciclo esperado:

```powershell
pnpm build:web
pnpm --filter @truths-forge/mobile cap add android
pnpm --filter @truths-forge/mobile sync
```

O cache offline somente leitura entra na fase M6.
