$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $RepoRoot "infra\.env"
$EnvExampleFile = Join-Path $RepoRoot "infra\.env.example"
$ComposeFile = Join-Path $RepoRoot "infra\docker-compose.yml"
$ComposeDevFile = Join-Path $RepoRoot "infra\docker-compose.dev.yml"
$LocalDockerConfigDir = Join-Path $RepoRoot ".local\docker-config"

if (-not $env:DOCKER_CONFIG) {
  New-Item -ItemType Directory -Force -Path $LocalDockerConfigDir | Out-Null
  $ConfigPath = Join-Path $LocalDockerConfigDir "config.json"
  if (-not (Test-Path $ConfigPath)) {
    "{}" | Set-Content -Path $ConfigPath -Encoding UTF8
  }
  $env:DOCKER_CONFIG = $LocalDockerConfigDir
}

if (-not (Test-Path $EnvFile)) {
  if (-not (Test-Path $EnvExampleFile)) {
    throw "Couldn't find env file: $EnvFile or $EnvExampleFile"
  }
  $EnvFile = $EnvExampleFile
}

Write-Host "Starting Truth's Forge AI full container dev stack..."
docker compose --env-file $EnvFile -f $ComposeFile -f $ComposeDevFile up --build -d
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed"
}

& (Join-Path $PSScriptRoot "reset-pgadmin.ps1")

Write-Host ""
Write-Host "Stack started:"
Write-Host "  app web:      http://127.0.0.1:5173"
Write-Host "  backend:      http://127.0.0.1:8000"
Write-Host "  API docs:     http://127.0.0.1:8000/docs"
Write-Host "  project docs: http://127.0.0.1:3000"
Write-Host "  pgAdmin:      http://localhost:8080"
Write-Host "  redis UI:     http://127.0.0.1:8081"
Write-Host "  qdrant UI:    http://127.0.0.1:6333/dashboard"
