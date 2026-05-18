---
name: testing-modeling-3d-chat
description: Testa o fluxo e2e chat-first de modelagem 3D MCP. Use ao validar ativação MCP 3D no composer, badge 3D, diagnóstico, settings e migração de estado legado.
---

## Objetivo

Validar pelo browser que o fluxo MCP 3D realmente cria ou mantém uma sessão de chat marcada como 3D, não apenas que o chip do composer aparece antes do envio.

## Devin Secrets Needed

- Nenhum para o caminho local padrão com `dev_store`/DevLLM.
- `OPENAI_API_KEY` é opcional se a validação precisar usar planner LLM real em vez do fallback local.
- `TRUTHS_FORGE_BLENDER_EXECUTABLE` é opcional se a validação precisar provar execução real no Blender.
- `TRUTHS_FORGE_FUSION_BRIDGE_DISCOVERY` e `TRUTHS_FORGE_FUSION_BRIDGE_HOST` são opcionais se a validação precisar provar Fusion bridge real.

## Setup local esperado

- Backend em `http://127.0.0.1:8000`.
- Frontend Vite em `http://127.0.0.1:5173`.
- O ambiente local pode usar fallback JSON/DevLLM; não assumir Blender ou Fusion reais disponíveis.
- Antes de gravar, maximizar o browser e iniciar recording apenas para as interações GUI.

## Fluxo e2e principal

1. Abrir o app no chat e clicar `Novo chat`.
2. Clicar `Menu de execução` (`+`) e escolher `MCP 3D`.
3. Confirmar que o modal mostra `Ativar modelagem 3D no chat` e opções `Auto`, `Blender`, `Fusion 360`.
4. Selecionar `Blender` e confirmar `Ativar no próximo chat`.
5. Verificar que o chip antes do envio mostra `Execução: MCP 3D (blender)`.
6. Enviar um prompt inequívoco, por exemplo `Crie um cubo simples para impressão 3D`.
7. Verificar após o envio, não antes, que a sessão ativa mostra badge `3D` no header e no histórico/sidebar.
8. Clicar `Diagnóstico 3D` e verificar seções `Adapters`, `Tool calls recentes`, `Printability`, `Versões/exportações`.
9. Abrir `Configurações` no painel lateral e verificar `Configuração do MCP 3D`, `Software preferido`, `Auto`, `Blender`, `Fusion 360` e texto de execução `fluida allowlistada`.

## Regressão crítica

Testar migração de localStorage legado quando relevante:

```js
localStorage.setItem(
  "truths-forge-ui-state-v1",
  JSON.stringify({
    state: {
      activeView: "modeling",
      activePanel: "config",
      activeSessionId: null,
      modeling3dEnabled: true,
      modeling3dMode: "safe_auto",
      modeling3dSoftware: "fusion"
    },
    version: 0
  })
);
```

Depois de recarregar, a aplicação deve abrir em `Chat`, o chip deve iniciar como `padrão`, e a navegação esquerda não deve mostrar item dedicado `3D`, `Modelagem` ou `Painel 3D`.

## Armadilhas conhecidas

- Não considerar o teste aprovado só porque o chip `MCP 3D` aparece antes de enviar. O bug pode ocorrer depois do submit, quando a sessão criada não recebe `is_modeling_3d`.
- Se o botão `Diagnóstico 3D` não aparecer, marcar diagnóstico/settings como bloqueados ou não testados; não abrir settings de outro chat para preencher a lacuna.
- Se o console mostrar erro de migração Zustand, registrar como evidência, mas a assertion principal deve ser visual: app em Chat, sem tela branca e sem nav 3D legada.
