# Instancia plan.md a partir do template numa pasta de spec existente.
# Uso: setup-plan.ps1 -FeatureDir "010-chat-orchestration"
param([Parameter(Mandatory = $true)][string]$FeatureDir)
. "$PSScriptRoot/common.ps1"
$root = Get-RepoRoot
$dir  = Join-Path (Get-SpecsDir $root) $FeatureDir
if (-not (Test-Path $dir)) { throw "Pasta da spec não existe: specs/$FeatureDir" }
$plan = Join-Path $dir "plan.md"
if (Test-Path $plan) { Write-Host "plan.md já existe em specs/$FeatureDir"; exit 0 }
Copy-Item (Join-Path (Get-TemplatesDir $root) "plan-template.md") $plan
Write-Host "Criado: specs/$FeatureDir/plan.md"
