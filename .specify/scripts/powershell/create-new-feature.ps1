# Cria specs/NNN-<slug>/ a partir do template e um handoff stub.
# Uso: create-new-feature.ps1 -Slug "chat-orchestration" [-Number "010"]
param(
    [Parameter(Mandatory = $true)][string]$Slug,
    [string]$Number
)
. "$PSScriptRoot/common.ps1"
$root  = Get-RepoRoot
$specs = Get-SpecsDir $root
if (-not $Number) { $Number = Get-NextFeatureNumber $specs }
$dirName    = "$Number-$Slug"
$featureDir = Join-Path $specs $dirName
if (Test-Path $featureDir) { throw "Já existe: specs/$dirName" }

New-Item -ItemType Directory -Path $featureDir | Out-Null
Copy-Item (Join-Path (Get-TemplatesDir $root) "spec-template.md") (Join-Path $featureDir "spec.md")
"# handoff.md`n`nContinuidade entre agentes (Codex, Claude Code, Devin, humanos) para ``$dirName``.`n`n## Estado atual`n`n- _vazio_`n" |
    Set-Content -Path (Join-Path $featureDir "handoff.md") -Encoding utf8

Write-Host "Criado: specs/$dirName/ (spec.md, handoff.md)"
Write-Host "Edite spec.md, depois rode setup-plan.ps1 -FeatureDir $dirName"
