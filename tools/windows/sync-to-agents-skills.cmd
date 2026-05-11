@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "DESTINATION=%~1"
if not defined DESTINATION set "DESTINATION=%USERPROFILE%\.agents\skills"

for %%I in ("%~dp0..\..") do set "REPO_ROOT=%%~fI"
set "SKILLS_DIR=%REPO_ROOT%\skills"

if not exist "%SKILLS_DIR%" (
  echo Skills directory not found: "%SKILLS_DIR%"
  exit /b 1
)

if not exist "%DESTINATION%" (
  mkdir "%DESTINATION%"
  if errorlevel 1 exit /b 1
)

for /d %%S in ("%SKILLS_DIR%\*") do (
  set "TARGET=%DESTINATION%\%%~nxS"
  robocopy "%%~fS" "!TARGET!" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
  if errorlevel 8 (
    echo Failed to copy %%~nxS to !TARGET!
    exit /b !ERRORLEVEL!
  )
  echo Copied %%~nxS -^> !TARGET!
)

exit /b 0
