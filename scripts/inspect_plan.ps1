<#
.SYNOPSIS
  Diagnóstico completo de um plano de modelagem 3D por plan_id (para o assistente
  inspecionar sem pedir dumps manuais). Puxa o plano + o trace rico do backend e
  imprime: status, steps, TEMPOS por passo, diagnóstico de POSICIONAMENTO
  (token -> face/centro), proveniência, veredito e erros.

.EXAMPLE
  pwsh scripts/inspect_plan.ps1 -PlanId m3d_plan_18a681257e654319
  pwsh scripts/inspect_plan.ps1 m3d_plan_xxx -ApiBase http://127.0.0.1:8000
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)] [string] $PlanId,
  [string] $ApiBase = "http://127.0.0.1:8000",
  [int] $TraceLimit = 1000
)

$ErrorActionPreference = "Stop"

function J($obj, $depth = 12) { $obj | ConvertTo-Json -Compress -Depth $depth }

try {
  $plan = Invoke-RestMethod -Uri "$ApiBase/api/3d/plans/$PlanId" -TimeoutSec 15
} catch {
  Write-Host "ERRO ao buscar o plano $PlanId : $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
try {
  $trace = Invoke-RestMethod -Uri "$ApiBase/api/3d/plans/$PlanId/trace?limit=$TraceLimit" -TimeoutSec 30
} catch {
  $trace = @()
  Write-Host "(aviso: trace indisponível: $($_.Exception.Message))" -ForegroundColor Yellow
}

"==================== PLANO $PlanId ===================="
"status={0}  kind={1}  planner={2}  confidence={3}" -f $plan.status, $plan.kind, $plan.planner_source, $plan.confidence
"prompt: " + ($plan.prompt -replace '\s+', ' ').Substring(0, [Math]::Min(280, $plan.prompt.Length))
if ($plan.fallback_reason) { "fallback_reason: " + $plan.fallback_reason }

# ---- Veredito (auto-crítica F8) ----
""
"==================== VEREDITO (model_verdict) ===================="
if ($plan.model_verdict) {
  "overall={0}  resumo: {1}" -f $plan.model_verdict.overall, $plan.model_verdict.summary
  foreach ($f in $plan.model_verdict.findings) {
    "  - [{0}/{1}/{2}] {3}{4}: {5}" -f $f.kind, $f.source, $f.severity, $f.check_id, ($(if ($f.entity_ref) { " ($($f.entity_ref))" } else { "" })), $f.detail
  }
} else { "(sem veredito — flag self_critique OFF ou não rodou)" }

# ---- Steps ----
""
"==================== STEPS ===================="
foreach ($s in ($plan.steps | Sort-Object seq)) {
  $line = "{0,2}. {1,-26} [{2}]" -f $s.seq, $s.tool_name, $s.status
  if ($s.error) { $line += "  ERROR: " + $s.error }
  $line
}

# ---- Tempos (o que importa para a lentidão do /execute) ----
""
"==================== TEMPOS (duration_ms) ===================="
$timed = $trace | Where-Object { $_.duration_ms -ne $null -and $_.duration_ms -gt 0 } | Sort-Object duration_ms -Descending
if ($timed) {
  $total = ($timed | Measure-Object duration_ms -Sum).Sum
  "soma das durações medidas: {0} ms ({1:N1} s)" -f $total, ($total / 1000)
  $timed | Select-Object -First 25 | ForEach-Object {
    "  {0,7} ms  {1,-34} {2}" -f $_.duration_ms, $_.event_type, ($_.message -replace '\s+', ' ')
  }
} else { "(nenhum evento com duration_ms — backend antigo ou trace vazio)" }
if ($trace.Count -gt 0) {
  $t0 = [datetime]($trace[0].created_at); $t1 = [datetime]($trace[-1].created_at)
  "wall-clock (1º->último evento): {0:N1} s sobre {1} eventos" -f (($t1 - $t0).TotalSeconds), $trace.Count
}

# ---- Posicionamento (a parte que explica mis-place) ----
""
"==================== POSICIONAMENTO (spatial_resolved / relation_resolved) ===================="
$place = $trace | Where-Object { $_.event_type -match 'spatial_resolved|relation_resolved' }
if ($place) {
  foreach ($e in $place) {
    "-> {0}  ({1})" -f $e.event_type, $e.message
    if ($e.payload.kind) { "   kind: " + $e.payload.kind }
    if ($e.payload.derived) { "   derived: " + (J $e.payload.derived) }
    if ($e.payload.placement) {
      "   concrete: " + (J $e.payload.placement.concrete)
      "   resolved_faces: " + (J $e.payload.placement.resolved_faces)
      "   bodies: " + (J $e.payload.placement.bodies)
    }
  }
} else { "(nenhum — placement não passou pelo resolver F7/F8; provável coordenada absoluta)" }

# ---- Geometria lida (read-back) — faces + NORMAIS por corpo ----
""
"==================== GEOMETRIA LIDA (query_geometry) ===================="
try {
  $tc = Invoke-RestMethod "$ApiBase/api/3d/tool-calls?plan_id=$PlanId&limit=80" -TimeoutSec 15
  $qg = $tc | Where-Object { $_.tool_name -match 'query_geometry' -and $_.response_json.result.message } |
    Sort-Object created_at -Descending | Select-Object -First 1  # o read-back MAIS RECENTE
  if ($qg) {
    $geo = $qg.response_json.result.message | ConvertFrom-Json
    foreach ($b in $geo.bodies) {
      "  body[{0}] '{1}'  bbox={2}..{3}  faces={4}" -f $b.body_index, $b.name, (($b.bbox_min_mm) -join ','), (($b.bbox_max_mm) -join ','), $b.face_count
      $b.faces | Where-Object { $_.type -eq 'planar' } | ForEach-Object {
        "      planar normal={0,-3} center={1}" -f $_.normal_axis, (($_.center_mm) -join ',')
      }
    }
  } else { "(sem query_geometry persistido nos tool-calls)" }
} catch { "(tool-calls indisponível: $($_.Exception.Message))" }

# ---- Proveniência (o que cada passo mudou) ----
""
"==================== PROVENIÊNCIA (provenance_recorded) ===================="
$prov = $trace | Where-Object { $_.event_type -match 'provenance_recorded' }
if ($prov) {
  foreach ($e in $prov) { "  - " + ($e.message -replace '\s+', ' ') }
} else { "(nenhum — flag provenance OFF)" }

# ---- Visão (crítica visual como input do veredito) ----
$vis = $trace | Where-Object { $_.event_type -match 'visual' }
if ($vis) {
  ""
  "==================== VISÃO (visual.critique) ===================="
  foreach ($e in $vis) { "  - [{0}] {1}  {2}" -f $e.level, ($e.message -replace '\s+', ' '), (J $e.payload) }
}

# ---- Erros ----
""
"==================== ERROS / WARN ===================="
$bad = $trace | Where-Object { $_.level -match 'error|warn' -or $_.event_type -match 'error|exhausted|failure|blocked' }
if ($bad) {
  foreach ($e in $bad) {
    "  [{0}] {1}: {2}  {3}" -f $e.level, $e.event_type, ($e.message -replace '\s+', ' '), (J $e.payload 8)
  }
} else { "(nenhum erro/warn no trace)" }
""
"==================== FIM ===================="
