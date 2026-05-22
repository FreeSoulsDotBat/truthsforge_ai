# Verifica se a casca do Spec Kit está presente antes de specify/plan/tasks.
. "$PSScriptRoot/common.ps1"
$root = Get-RepoRoot
$ok = $true
$checks = @(
    @{ Name = ".specify/memory/constitution.md"; Path = (Get-ConstitutionPath $root) },
    @{ Name = ".specify/templates";              Path = (Get-TemplatesDir $root) },
    @{ Name = "specs/";                          Path = (Get-SpecsDir $root) }
)
foreach ($c in $checks) {
    if (Test-Path $c.Path) { Write-Host "[ok]    $($c.Name)" }
    else { Write-Host "[falta] $($c.Name)"; $ok = $false }
}
if (-not $ok) { Write-Host "Pré-requisitos do Spec Kit ausentes."; exit 1 }
Write-Host "Pré-requisitos do Spec Kit OK."
