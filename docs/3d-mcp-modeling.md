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
- `GET /api/3d/snapshots`: lista snapshots persistidos.
- `POST /api/3d/snapshots`: cria snapshot real do workspace 3D (cópia + manifesto + hash).
- `GET /api/3d/snapshots/{snapshot_id}`: retorna o snapshot com arquivos e manifesto.
- `POST /api/3d/snapshots/{snapshot_id}/restore`: restaura o snapshot sobre o workspace original.
- `GET /api/3d/tool-calls`: lista tool calls auditadas, com filtros opcionais `plan_id` e `step_id`.

## Snapshots e rollback

Snapshots são feitos por par `(project_id, plan_id)`. O serviço resolve o workspace canônico em
`.local/modeling/workspaces/<project>/<plan>/` e copia todo o conteúdo relevante (exceto arquivos
de job intermediários) para `.local/modeling/snapshots/<snapshot_id>/files/`, junto com um
`manifest.json` contendo:

- `id`, `project_id`, `plan_id`, `step_id`, `parent_snapshot_id`, `label`, `reason`
- `workspace_path` e `storage_path` absolutos
- lista de arquivos capturados com `relative_path`, `sha256` e `size_bytes`

Restaurar copia os arquivos do snapshot de volta ao `workspace_path` original (criando-o se
preciso), sobrescrevendo o conteúdo atual. O snapshot ganha `restored_at` no banco e a operação
é registrada como `modeling.snapshot_restored` na trilha de auditoria.

A operação só roda dentro de `settings.modeling_dir`. Snapshots cujo `workspace_path` ou
`storage_path` apontem para fora dessa raiz são rejeitados com `HTTP 400`.

## Tool calls e envelope de erro

Toda execução de etapa gera um `ModelingToolCall` persistido em `modeling_tool_calls`, com:

- `mcp_server`, `tool_name`, `software`, `transport`
- `request_json` (input do step) e `response_json` (output bruto do adapter)
- `status` (`ok`, `error`, `blocked`)
- `duration_ms`, `artifact_paths`
- Quando há falha: `error_code`, `error_message`, `retryable`,
  `safe_to_retry_after_snapshot_restore`

O adapter Blender já emite `error_code` (`blender.timeout`, `blender.runner_failed`) e indica
retentativa segura após restore para fluxos onde a corrupção do workspace é possível.

## Novas tabelas

- `modeling_tool_calls`: trilha completa de tool calls (Postgres + dev store).
- `modeling_printability_reports`: reservada para o PR de printability.
- `modeling_model_versions`: reservada para versões nomeadas de modelos derivados.

## Próximos incrementos

1. Expandir `blender_mcp` para mais operações controladas: boolean, curvas, materiais e câmera.
2. Validador de printability rodando dentro do runner Blender (bmesh).
3. Trocar planner heurístico por Responses API com Structured Outputs (`strict: true`).
4. Implementar `fusion_mcp` real por add-in persistente do Fusion 360.
5. UI estendida com painel de plano, aprovação por etapa, snapshots e tool calls.
6. Extração dos adapters para servidores MCP `stdio` reais.

## Limite de segurança

O modelo remoto nunca executa Blender/Fusion diretamente. Ele gera intenção/plano; o backend local aplica política e só então conversa com MCP local. Isso reduz risco de prompt injection, execução arbitrária e automação destrutiva.
