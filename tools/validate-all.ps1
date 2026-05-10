param(
  [string]$Validator = "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$skillsDir = Join-Path $root "skills"

if (-not (Test-Path -LiteralPath $Validator)) {
  throw "Validator not found: $Validator"
}

Get-ChildItem -LiteralPath $skillsDir -Directory | ForEach-Object {
  Write-Host "Validating $($_.Name)..."
  python $Validator $_.FullName
}
