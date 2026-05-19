# Smoke test ponta-a-ponta da observabilidade de modelagem 3D.
#
# Valida que:
#   1. O backend está saudável.
#   2. O endpoint /api/3d/traces/events aceita um evento de cliente sem
#      precisar de chat ativo (auto-trace simples).
#   3. O evento aparece na consulta /api/3d/traces/{trace_id}.
#   4. A tabela modeling_trace_events tem o registro persistido.
#
# Não exercita o LLM real — esse fluxo precisa de OPENAI_API_KEY e de
# uma sessão de chat 3D ativa. Veja docs/local-dev.md para o teste
# manual completo com "uma esfera".
#
# Uso:
#   pwsh scripts/smoke-modeling-trace.ps1
#   pwsh scripts/smoke-modeling-trace.ps1 -BackendUrl http://127.0.0.1:8000

[CmdletBinding()]
param(
    [string]$BackendUrl = "http://127.0.0.1:8000",
    [string]$PostgresContainer = "truths-forge-postgres",
    [string]$PostgresUser = "forge",
    [string]$PostgresDb = "truths_forge_ai"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Write-Pass([string]$message) {
    Write-Host "    PASS $message" -ForegroundColor Green
}

function Write-Fail([string]$message) {
    Write-Host "    FAIL $message" -ForegroundColor Red
    throw $message
}

Write-Step "Health check do backend em $BackendUrl"
try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get -TimeoutSec 5
    Write-Pass "backend respondeu /health"
} catch {
    Write-Fail "backend não respondeu /health — suba com docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d"
}

# Gera trace_id no formato esperado pelo tracer (ULID-like: mt_<hex>).
$traceId = "mt_smoke_" + ([guid]::NewGuid().ToString("N").Substring(0, 12))
$eventPayload = @{
    trace_id   = $traceId
    event_type = "ui.smoke_test"
    level      = "info"
    message    = "Smoke test do módulo de observabilidade"
    payload    = @{
        run_at = (Get-Date).ToUniversalTime().ToString("o")
        ci     = $false
    }
} | ConvertTo-Json -Depth 4 -Compress

Write-Step "POST /api/3d/traces/events (trace_id=$traceId)"
try {
    $posted = Invoke-RestMethod `
        -Uri "$BackendUrl/api/3d/traces/events" `
        -Method Post `
        -ContentType "application/json" `
        -Body $eventPayload `
        -TimeoutSec 10
    if (-not $posted.id) { Write-Fail "POST não devolveu id" }
    Write-Pass "evento posto, id=$($posted.id), sequence=$($posted.sequence)"
} catch {
    Write-Fail "falha no POST: $($_.Exception.Message)"
}

Write-Step "GET /api/3d/traces/$traceId"
try {
    Start-Sleep -Milliseconds 200
    $events = Invoke-RestMethod -Uri "$BackendUrl/api/3d/traces/$traceId" -Method Get -TimeoutSec 10
    if ($events.Count -lt 1) { Write-Fail "trace está vazio" }
    $first = $events | Where-Object { $_.event_type -eq "ui.smoke_test" } | Select-Object -First 1
    if (-not $first) { Write-Fail "evento ui.smoke_test não foi encontrado no GET" }
    if ($first.source -ne "ui") { Write-Fail "source deveria ter sido forçado para 'ui', veio '$($first.source)'" }
    Write-Pass "GET devolveu $($events.Count) evento(s); source forçado corretamente para 'ui'"
} catch {
    Write-Fail "falha no GET: $($_.Exception.Message)"
}

Write-Step "Verifica persistência direta no Postgres"
try {
    $count = docker exec $PostgresContainer psql -U $PostgresUser -d $PostgresDb -t -A -c "SELECT COUNT(*) FROM modeling_trace_events WHERE trace_id = '$traceId';"
    if ([int]$count -lt 1) { Write-Fail "Postgres não tem linha para trace_id=$traceId" }
    Write-Pass "Postgres tem $count linha(s) para o trace"
} catch {
    Write-Fail "consulta Postgres falhou: $($_.Exception.Message)"
}

Write-Step "Verifica logs JSON do backend (últimas 5 linhas com este trace_id)"
$logs = docker logs truths-forge-backend --since 30s 2>&1 | Where-Object { $_ -match $traceId } | Select-Object -Last 5
if ($logs) {
    Write-Pass "logs estruturados contêm o trace_id:"
    $logs | ForEach-Object { Write-Host "      $_" -ForegroundColor DarkGray }
} else {
    Write-Host "    SKIP nenhum log com trace_id $traceId nos últimos 30s (esperado se o nível default filtrar info)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Smoke test completo. Trace_id: $traceId" -ForegroundColor Green
Write-Host "Para inspecionar manualmente:" -ForegroundColor DarkGray
Write-Host "  curl $BackendUrl/api/3d/traces/$traceId | jq" -ForegroundColor DarkGray
Write-Host "  docker logs truths-forge-backend | jq 'select(.trace_id == \`"$traceId\`")'" -ForegroundColor DarkGray
