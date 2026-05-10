param(
  [string]$Destination = "$env:USERPROFILE\.codex\skills"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$skillsDir = Join-Path $root "skills"

New-Item -ItemType Directory -Force -Path $Destination | Out-Null

Get-ChildItem -LiteralPath $skillsDir -Directory | ForEach-Object {
  $target = Join-Path $Destination $_.Name
  if (Test-Path -LiteralPath $target) {
    Remove-Item -LiteralPath $target -Recurse -Force
  }
  Copy-Item -LiteralPath $_.FullName -Destination $target -Recurse
  Write-Host "Synced $($_.Name) -> $target"
}
