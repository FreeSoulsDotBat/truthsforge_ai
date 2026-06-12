<#
.SYNOPSIS
  Gate F8.R1 — relação genérica `relate_bodies` (flush_mate) via PLANO LITERAL.

.DESCRIPTION
  O `relate_bodies` está DARK no planner (não validado), então este gate o dirige
  por plano literal — isolando 100% o LLM. Monta: add_box 'Caixa' + add_box 'Tampa'
  + relate_bodies{kind:flush_mate, moving:Tampa, reference:Caixa}. O backend deve
  DERIVAR medindo (face de baixo da Tampa ↔ face de cima da Caixa) e expandir em
  make_component + joint → a Tampa ENCOSTA no topo da Caixa, sem token chutado.

  PRÉ: ligue MODELING_RELATION_PLACEMENT_ENABLED (já ON) + Fusion conectado.
  USO: crie um plano qualquer no chat 3D, pegue o <PLAN_ID> com o card AINDA em
  aprovação (NÃO aprove), e rode:  .\scripts\gate_f8r1.ps1 <PLAN_ID>

.NOTES
  Patch só funciona em plano draft/waiting_approval. Se já avançou (auto-exec/
  aprovado), crie um plano novo e não o aprove.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)] [string] $PlanId,
    [string] $ApiBase = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$api = "$ApiBase/api/3d"

# Plano literal: 2 corpos na origem + a RELAÇÃO. A Tampa nasce dentro/sobreposta;
# o relate_bodies a move pra cima do topo da Caixa MEDINDO as faces (a prova do F8.R1).
$body = @{
    steps = @(
        @{ title = "Caixa"; tool_name = "fusion.add_box"; risk_level = "low";
            input_json = @{ width_mm = 50; depth_mm = 50; height_mm = 20; name = "Caixa" } },
        @{ title = "Tampa"; tool_name = "fusion.add_box"; risk_level = "low";
            input_json = @{ width_mm = 50; depth_mm = 50; height_mm = 3; name = "Tampa" } },
        @{ title = "Relacao flush_mate (Tampa encosta na Caixa)"; tool_name = "fusion.relate_bodies";
            risk_level = "low"; input_json = @{ kind = "flush_mate"; moving = "Tampa"; reference = "Caixa" } }
    )
} | ConvertTo-Json -Depth 8

try {
    Write-Host "1) PATCH dos 3 steps literais no plano $PlanId ..." -ForegroundColor Cyan
    Invoke-RestMethod "$api/plans/$PlanId" -Method Patch -ContentType 'application/json' -Body $body | Out-Null
}
catch {
    Write-Host "FALHA no PATCH (o plano provavelmente já saiu de waiting_approval)." -ForegroundColor Red
    Write-Host "Crie um plano NOVO no chat e NÃO o aprove; rode de novo com o novo PLAN_ID." -ForegroundColor Yellow
    throw
}

Write-Host "2) Aprovando ..." -ForegroundColor Cyan
$appr = @{ decision = "approve"; reason = "gate F8.R1 (plano literal)" } | ConvertTo-Json
Invoke-RestMethod "$api/plans/$PlanId/approve" -Method Post -ContentType 'application/json' -Body $appr | Out-Null

Write-Host "3) Executando no Fusion (pode levar alguns segundos) ..." -ForegroundColor Cyan
Invoke-RestMethod "$api/plans/$PlanId/execute" -Method Post -ContentType 'application/json' | Out-Null

Write-Host "4) Resultado:`n" -ForegroundColor Cyan
& "$PSScriptRoot\inspect_plan.ps1" $PlanId -ApiBase $ApiBase
