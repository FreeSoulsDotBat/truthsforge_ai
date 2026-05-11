$commands = @("git", "docker", "node", "npm", "pnpm", "python", "py", "rustc", "cargo", "java", "adb")

foreach ($command in $commands) {
  $resolved = Get-Command $command -ErrorAction SilentlyContinue
  if ($resolved) {
    Write-Host "$command -> $($resolved.Source)"
  } else {
    Write-Host "$command -> missing"
  }
}
