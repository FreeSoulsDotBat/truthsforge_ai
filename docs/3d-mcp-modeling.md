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

- `blender.create_mesh_primitive` — primitivos `cube`, `cylinder`, `uv_sphere`, `plane`, `cone`
  com `dimensions_mm` e `location` opcional.
- `blender.apply_bevel` — bevel uniforme em todos os meshes da cena.
- `blender.apply_boolean` — `union`, `difference`, `intersect` entre dois objetos; remove o objeto
  auxiliar por padrão (`delete_other`). Classificada como HIGH_RISK pela política, exige
  aprovação humana.
- `blender.validate_mesh` — checks rápidos (non-manifold, loose verts, loose parts); read-only.
- `blender.validate_printability` — relatório completo via `bmesh` (read-only). Veja seção
  Printability abaixo.
- `blender.export_stl`, `blender.export_obj`, `blender.export_3mf` — exporta a cena para
  `.local/modeling/workspaces/.../exports/`.

Isso é proposital: a LLM cria intenção e plano, mas não injeta Python livre no Blender. Tools
read-only (validates) são auto-executadas mesmo em modo `approval_required`; tools destrutivas
como `apply_boolean` permanecem em HIGH_RISK e exigem aprovação humana explícita.

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
- `POST /api/3d/snapshots/{snapshot_id}/restore`: restaura o snapshot sobre o workspace original e
  devolve `ModelingSnapshotRestoreResult` (`snapshot`, `auto_snapshot`, `restored_file_count`).
- `GET /api/3d/tool-calls`: lista tool calls auditadas, com filtros opcionais `plan_id` e `step_id`.
- `POST /api/3d/validate/printability`: roda o relatório de printability sobre o workspace
  referenciado por `plan_id` e devolve `ModelingPrintabilityReport`. Quando o Blender real não
  está conectado, devolve um relatório placeholder identificado pelo `summary`.
- `GET /api/3d/printability-reports`: lista relatórios persistidos, com filtros opcionais
  `plan_id` e `file_id`.

## Snapshots e rollback

Snapshots são feitos por par `(project_id, plan_id)`. O serviço resolve o workspace canônico em
`.local/modeling/workspaces/<project>/<plan>/` e copia todo o conteúdo relevante para
`.local/modeling/snapshots/<snapshot_id>/files/`, junto com um `manifest.json` contendo:

- `id`, `project_id`, `plan_id`, `step_id`, `parent_snapshot_id`, `label`, `reason`
- `workspace_path` e `storage_path` absolutos
- lista de arquivos capturados com `relative_path`, `sha256` e `size_bytes`

Arquivos de scaffolding do runner Blender (`*.job.json`, `*.result.json`) e o próprio
`manifest.json` ficam fora dos snapshots porque não fazem parte do estado canônico.

O step inicial `project_store.create_snapshot` que o planner gera roda como tool real (não mock):
durante a execução do plano, o executor intercepta e chama o serviço de snapshot diretamente,
retornando `transport: "local"` e `snapshot_id` no `output_json` da etapa.

### Rollback seguro

Restaurar copia os arquivos do snapshot de volta ao `workspace_path` original (criando-o se
preciso), sobrescrevendo o conteúdo atual. Por padrão, **antes** de qualquer escrita o serviço
cria um snapshot automático do estado atual com `label="auto: pré-restore de <id>"` e
`parent_snapshot_id` apontando para o snapshot sendo restaurado — assim "desfazer o desfazer"
é só restaurar esse auto-snapshot.

`POST /api/3d/snapshots/{id}/restore` aceita no corpo:

- `reason` (opcional): registrado na auditoria e usado como `reason` do auto-snapshot.
- `force: true`: pula o auto-snapshot pré-restore. Caminho explícito quando o chamador aceita
  perder o estado atual.

A resposta `ModelingSnapshotRestoreResult` traz `snapshot` (o restaurado, com `restored_at`),
`auto_snapshot` (`null` quando `force=true` ou quando o workspace estava vazio) e
`restored_file_count`. O snapshot original ganha `restored_at` no banco e a operação é registrada
como `modeling.snapshot_restored` na trilha de auditoria, com `auto_snapshot_id` em metadata.

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

O adapter Blender constrói `ModelingErrorEnvelope` em timeout e runner failed; o serviço usa o
mesmo schema na falha do `project_store.create_snapshot`. O envelope é o caminho único de erro
para tool calls — `host_details` carrega contexto estruturado (software, workspace_dir,
returncode, stdout/stderr tail, timeout configurado).

## Printability via bmesh

A tool `blender.validate_printability` roda dentro do runner Blender em background e usa
`bmesh` para checks geométricos:

| Check | O que faz |
|---|---|
| `non_manifold` | conta arestas não-manifold por objeto (issue `error`) |
| `loose_parts` | conta ilhas desconectadas e vértices soltos (issue `warning`) |
| `volume` | sinaliza volume não-positivo, sugerindo malha aberta (issue `warning`) |
| `normals` | heurística baseada em centróide para estimar faces invertidas (issue `warning`) |
| `overhang_approx` | faces com normal abaixo de 45° em relação ao plano (issue `info`) |
| `thickness_approx` | faces com área absurdamente pequena (issue `info`) |
| `bounding_box` | dimensões em mm |

O `risk_score` (0–1) agrega severidades com pesos: `error=0.5`, `warning=0.2`, `info=0.05`,
saturado em 1.0. Cada execução vira um `ModelingPrintabilityReport` persistido em
`modeling_printability_reports`, com `metrics` por objeto e a lista completa de `issues`.

A documentação da arquitetura proposta separa três níveis de printability — geométrica (MVP),
intermediária (overhang/orientação/encaixes) e avançada (slicer, material, warping). Este PR
entrega o nível geométrico inteiro; os demais ficam para PRs futuros.

## Novas tabelas

- `modeling_tool_calls`: trilha completa de tool calls (Postgres + dev store).
- `modeling_printability_reports`: relatórios geométricos do `blender.validate_printability`.
- `modeling_model_versions`: reservada para versões nomeadas de modelos derivados.

## Próximos incrementos

1. Trocar planner heurístico por Responses API com Structured Outputs (`strict: true`),
   incluindo as novas tools no toolset.
2. Tools tier 2: `apply_subdivision`, `apply_solidify`, `assign_material`, `measure_object`,
   `repair_non_manifold`, `icosphere`, `torus`.
3. Implementar `fusion_mcp` real por add-in persistente do Fusion 360.
4. UI estendida com painel de plano, aprovação por etapa, snapshots, tool calls e relatórios
   de printability.
5. Extração dos adapters para servidores MCP `stdio` reais.

## Limite de segurança

O modelo remoto nunca executa Blender/Fusion diretamente. Ele gera intenção/plano; o backend local aplica política e só então conversa com MCP local. Isso reduz risco de prompt injection, execução arbitrária e automação destrutiva.
