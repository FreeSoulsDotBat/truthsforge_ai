# Modelagem 3D via MCP

O módulo 3D nasce como um bounded context local para conectar JUDITE e agentes a Blender e Fusion 360 por MCP, com supervisão humana, trilha de auditoria e execução incremental.

## Estado atual

- Backend FastAPI expõe `/api/3d/*`.
- UI web ganhou a aba `3D`.
- O planner escolhe Blender ou Fusion por heurística e gera um plano estruturado.
- O executor usa adapter MCP local com fallback `mock`.
- Blender já pode executar um subconjunto seguro por `blender --background` quando configurado.
- Fusion 360 permanece em `mock` até o add-in persistente ser implementado.
- Ações mutáveis exigem aprovação humana por padrão.
- Scripts livres, shell e operações destrutivas seguem fora do caminho feliz.
- Artefatos gerados pelo Blender, como `.blend` e `.stl`, entram em `Arquivos` como `generated`.

## Blender local

Para ativar execução real do Blender, configure no ambiente do backend:

```powershell
$env:TRUTHS_FORGE_BLENDER_EXECUTABLE="C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
```

No container, o fallback continua `mock` porque o Blender normalmente não está instalado dentro da imagem de desenvolvimento. Para usar o Blender real no Windows, rode o backend em um contexto que consiga enxergar o executável local ou evolua para um bridge MCP desktop separado.

Variáveis:

- `TRUTHS_FORGE_BLENDER_EXECUTABLE`: caminho absoluto ou comando resolvível no `PATH`.
- `TRUTHS_FORGE_MODELING_TIMEOUT_SECONDS`: timeout por etapa, padrão `90`.

O workspace fica em `.local/modeling/workspaces/<project>/<plan>`. O runner atual só aceita ferramentas allowlistadas:

- `blender.create_mesh_primitive`
- `blender.apply_bevel`
- `blender.export_stl`

Isso é proposital: a LLM cria intenção e plano, mas não injeta Python livre no Blender.

## Endpoints

- `GET /api/3d/capabilities`: lista adapters MCP e ferramentas disponíveis.
- `GET /api/3d/sessions`: lista sessões locais registradas.
- `POST /api/3d/sessions/start`: inicia sessão Blender/Fusion em modo mock/local.
- `GET /api/3d/plans`: lista planos recentes.
- `POST /api/3d/plans`: cria plano estruturado a partir de um prompt.
- `POST /api/3d/plans/{plan_id}/approve`: aprova ou rejeita o plano inteiro.
- `POST /api/3d/plans/{plan_id}/execute`: executa etapas aprovadas.
- `POST /api/3d/steps/{step_id}/approve`: aprova ou rejeita uma etapa específica.
- `GET /api/3d/snapshots`: lista snapshots lógicos.
- `POST /api/3d/snapshots`: cria snapshot lógico do workspace 3D.

## Próximos incrementos

1. Expandir `blender_mcp` para mais operações controladas: boolean, curvas, materiais e câmera.
2. Implementar `fusion_mcp` real por add-in persistente do Fusion 360.
3. Salvar previews renderizados, exports STEP/3MF e relatórios de printabilidade como arquivos da plataforma.
4. Criar approvals passo a passo com diffs semânticos.
5. Conectar recuperação de bases de conhecimento ao planner 3D.

## Limite de segurança

O modelo remoto nunca executa Blender/Fusion diretamente. Ele gera intenção/plano; o backend local aplica política e só então conversa com MCP local. Isso reduz risco de prompt injection, execução arbitrária e automação destrutiva.
