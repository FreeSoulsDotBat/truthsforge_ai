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

function Invoke-Compose {
  param([Parameter(Mandatory = $true)][string[]]$Args)

  docker compose --env-file $EnvFile -f $ComposeFile -f $ComposeDevFile @Args
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose command failed: $($Args -join ' ')"
  }
}

$TestDataDir = "/tmp/truths_forge_test_$([Guid]::NewGuid().ToString('N'))"
Invoke-Compose @(
  "exec",
  "-T",
  "-e", "TRUTHS_FORGE_STORAGE_BACKEND=dev",
  "-e", "TRUTHS_FORGE_ENV=test",
  "-e", "TRUTHS_FORGE_DATA_DIR=$TestDataDir",
  "backend",
  "python",
  "-m",
  "pytest"
)
Invoke-Compose @("exec", "-T", "backend", "python", "-m", "ruff", "format", "--check", "app", "tests")
Invoke-Compose @("exec", "-T", "backend", "python", "-m", "ruff", "check", "app", "tests")
Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "format:check")
Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "lint")
Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "test:unit")
Invoke-Compose @("exec", "-T", "web", "pnpm", "--filter", "@truths-forge/web", "typecheck")
Invoke-Compose @("exec", "-T", "web", "pnpm", "build:web")
Invoke-Compose @("exec", "-T", "docs", "pnpm", "build:docs")
