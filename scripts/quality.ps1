param(
  [switch]$Fix
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $RepoRoot "infra\.env"
$EnvExampleFile = Join-Path $RepoRoot "infra\.env.example"
$ComposeFile = Join-Path $RepoRoot "infra\docker-compose.yml"
$ComposeDevFile = Join-Path $RepoRoot "infra\docker-compose.dev.yml"

if (-not (Test-Path $EnvFile)) {
  if (-not (Test-Path $EnvExampleFile)) {
    throw "Couldn't find env file: $EnvFile or $EnvExampleFile"
  }
  $EnvFile = $EnvExampleFile
}

function Invoke-Compose {
  param([Parameter(Mandatory = $true)][string[]]$Args)

  docker compose --env-file $EnvFile -f $ComposeFile -f $ComposeDevFile @Args
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose command failed: $($Args -join ' ')"
  }
}

Push-Location $RepoRoot
try {
  if ($Fix) {
    Invoke-Compose @("exec", "-T", "backend", "python", "-m", "ruff", "format", "app", "tests")
    Invoke-Compose @("exec", "-T", "backend", "python", "-m", "ruff", "check", "--fix", "app", "tests")
    Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "format")
    Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "lint:fix")
  }

  Invoke-Compose @("exec", "-T", "backend", "python", "-m", "ruff", "format", "--check", "app", "tests")
  Invoke-Compose @("exec", "-T", "backend", "python", "-m", "ruff", "check", "app", "tests")
  Invoke-Compose @("exec", "-T", "backend", "python", "-m", "pytest")

  Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "format:check")
  Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "lint")
  Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "test:unit")
  Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "typecheck")
} finally {
  Pop-Location
}
