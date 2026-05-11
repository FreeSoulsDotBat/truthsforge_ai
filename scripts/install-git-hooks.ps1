$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

git -C $RepoRoot config core.hooksPath .githooks

Write-Host "Git hooks configured: core.hooksPath=.githooks"
