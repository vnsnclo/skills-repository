param(
  [string]$Validator = (Join-Path $env:USERPROFILE ".codex\skills\.system\skill-creator\scripts\quick_validate.py"),
  [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$skillsDir = Join-Path $repoRoot "skills"

if (-not (Test-Path -LiteralPath $Validator)) {
  throw "Validator not found: $Validator"
}

if (-not $Python) {
  $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
  if (-not $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
  }
  if (-not $pythonCommand) {
    throw "Python not found. Install Python or pass -Python <path>."
  }
  $Python = $pythonCommand.Source
}

Get-ChildItem -LiteralPath $skillsDir -Directory | ForEach-Object {
  Write-Host "Validating $($_.Name)..."
  & $Python $Validator $_.FullName
}
