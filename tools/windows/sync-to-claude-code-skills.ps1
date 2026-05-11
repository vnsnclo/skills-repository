param(
  [string]$Destination = (Join-Path $env:USERPROFILE ".claude\skills")
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$skillsDir = Join-Path $repoRoot "skills"

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

Get-ChildItem -LiteralPath $skillsDir -Directory | ForEach-Object {
  $target = Join-Path $Destination $_.Name
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
  Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse
  Write-Host "Synced $($_.Name) -> $target"
}
