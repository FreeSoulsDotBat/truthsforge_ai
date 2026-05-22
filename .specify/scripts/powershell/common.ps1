# Funções compartilhadas pelos scripts do Spec Kit (Truth's Forge AI).
# Não duplicam scripts/quality.ps1 — apenas localizam paths e numeram features.
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    $root = (git rev-parse --show-toplevel 2>$null)
    if (-not $root) { throw "Não é um repositório git." }
    return $root
}

function Get-SpecsDir        { param($Root) return (Join-Path $Root "specs") }
function Get-TemplatesDir    { param($Root) return (Join-Path $Root ".specify/templates") }
function Get-ConstitutionPath{ param($Root) return (Join-Path $Root ".specify/memory/constitution.md") }

# Próximo número de feature: múltiplo de 10 acima do maior NNN- existente
# (pastas em specs/_legacy/ são ignoradas). Use -Number para forçar (ex.: 005).
function Get-NextFeatureNumber {
    param($SpecsDir)
    $max = 0
    if (Test-Path $SpecsDir) {
        Get-ChildItem -Path $SpecsDir -Directory | Where-Object { $_.Name -ne "_legacy" } | ForEach-Object {
            if ($_.Name -match '^(\d{3})-') {
                $n = [int]$Matches[1]
                if ($n -gt $max) { $max = $n }
            }
        }
    }
    return ('{0:000}' -f ([math]::Floor($max / 10) * 10 + 10))
}
