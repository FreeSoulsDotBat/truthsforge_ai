param(
  [switch]$Build
)

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

function Get-DevEnvValue {
  param(
    [string]$Name,
    [string]$DefaultValue
  )

  $EnvironmentValue = [Environment]::GetEnvironmentVariable($Name)
  if (-not [string]::IsNullOrWhiteSpace($EnvironmentValue)) {
    return $EnvironmentValue
  }

  if (Test-Path $EnvFile) {
    $NamePattern = [regex]::Escape($Name)
    foreach ($Line in Get-Content -Path $EnvFile) {
      $TrimmedLine = $Line.Trim()
      if ($TrimmedLine -eq "" -or $TrimmedLine.StartsWith("#")) {
        continue
      }
      if ($TrimmedLine -match "^$NamePattern\s*=\s*(.*)$") {
        return $Matches[1].Trim().Trim('"').Trim("'")
      }
    }
  }

  return $DefaultValue
}

function Get-DevPort {
  param(
    [string]$Name,
    [string]$DefaultValue
  )

  $Value = Get-DevEnvValue -Name $Name -DefaultValue $DefaultValue
  $ParsedPort = 0
  if ((-not [int]::TryParse($Value, [ref]$ParsedPort)) -or $ParsedPort -lt 1 -or $ParsedPort -gt 65535) {
    throw "$Name must be a TCP port between 1 and 65535. Current value: '$Value'."
  }

  return $ParsedPort
}

function Test-DockerContainerPublishesPort {
  param(
    [string]$ContainerName,
    [int]$Port
  )

  try {
    $PublishedContainers = @(docker ps --filter "publish=$Port" --format "{{.Names}}" 2>$null)
  }
  catch {
    return $false
  }

  if ($LASTEXITCODE -ne 0) {
    return $false
  }

  return $PublishedContainers -contains $ContainerName
}

function Test-HostPortBindable {
  param([int]$Port)

  $Listener = $null
  try {
    $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
    $Listener.Start()
    return $true
  }
  catch {
    return $false
  }
  finally {
    if ($null -ne $Listener) {
      $Listener.Stop()
    }
  }
}

function Assert-DevPortAvailable {
  param(
    [string]$ServiceName,
    [string]$EnvName,
    [int]$Port,
    [string]$ContainerName,
    [int]$SuggestedPort
  )

  if (Test-DockerContainerPublishesPort -ContainerName $ContainerName -Port $Port) {
    return
  }

  $ExamplePort = $SuggestedPort
  if ($ExamplePort -eq $Port) {
    $ExamplePort = $Port + 1
  }

  if (-not (Test-HostPortBindable -Port $Port)) {
    throw @"
Porta local $Port indisponivel para $ServiceName.
Altere $EnvName em infra\.env para uma porta livre, por exemplo:
  $EnvName=$ExamplePort
Depois rode novamente:
  .\scripts\dev.ps1
Se preferir liberar a porta, pare o processo/container que ja usa $Port.
"@
  }
}

$DocsPort = Get-DevPort -Name "DOCS_PORT" -DefaultValue "3000"
$PgAdminPort = Get-DevPort -Name "PGADMIN_PORT" -DefaultValue "8080"
$RedisCommanderPort = Get-DevPort -Name "REDIS_COMMANDER_PORT" -DefaultValue "8081"

Assert-DevPortAvailable -ServiceName "docs" -EnvName "DOCS_PORT" -Port $DocsPort -ContainerName "truths-forge-docs" -SuggestedPort 13000
Assert-DevPortAvailable -ServiceName "pgAdmin" -EnvName "PGADMIN_PORT" -Port $PgAdminPort -ContainerName "truths-forge-pgadmin" -SuggestedPort 18080
Assert-DevPortAvailable -ServiceName "redis-commander" -EnvName "REDIS_COMMANDER_PORT" -Port $RedisCommanderPort -ContainerName "truths-forge-redis-commander" -SuggestedPort 18081

Write-Host "Starting Truth's Forge AI full container dev stack..."
# `--build` so quando -Build (Dockerfile mudou). No caminho rapido,
# verificar imagens travava o script por minutos no Windows/WSL2 mesmo
# sem mudancas; sem o flag, ``up -d`` retorna em segundos.
$ComposeUpArgs = @(
  "compose",
  "--env-file", $EnvFile,
  "-f", $ComposeFile,
  "-f", $ComposeDevFile,
  "up", "-d"
)
if ($Build) {
  $ComposeUpArgs += "--build"
}
docker @ComposeUpArgs
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed"
}

& (Join-Path $PSScriptRoot "reset-pgadmin.ps1")

Write-Host ""
Write-Host "Stack started:"
Write-Host "  app web:      http://127.0.0.1:5173"
Write-Host "  backend:      http://127.0.0.1:8000"
Write-Host "  API docs:     http://127.0.0.1:8000/docs"
Write-Host "  project docs: http://127.0.0.1:$DocsPort"
Write-Host "  pgAdmin:      http://localhost:$PgAdminPort"
Write-Host "  redis UI:     http://127.0.0.1:$RedisCommanderPort"
Write-Host "  qdrant UI:    http://127.0.0.1:6333/dashboard"
