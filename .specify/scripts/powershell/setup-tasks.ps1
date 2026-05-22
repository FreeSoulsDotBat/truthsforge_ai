# Instancia tasks.md a partir do template numa pasta de spec existente.
# Uso: setup-tasks.ps1 -FeatureDir "010-chat-orchestration"
param([Parameter(Mandatory = $true)][string]$FeatureDir)
. "$PSScriptRoot/common.ps1"
$root = Get-RepoRoot
$dir  = Join-Path (Get-SpecsDir $root) $FeatureDir
if (-not (Test-Path $dir)) { throw "Pasta da spec não existe: specs/$FeatureDir" }
$tasks = Join-Path $dir "tasks.md"
if (Test-Path $tasks) { Write-Host "tasks.md já existe em specs/$FeatureDir"; exit 0 }
Copy-Item (Join-Path (Get-TemplatesDir $root) "tasks-template.md") $tasks
Write-Host "Criado: specs/$FeatureDir/tasks.md"
