@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Skills Repository Validation

for %%I in ("%~dp0..\..") do set "REPO_ROOT=%%~fI"
set "SKILLS_DIR=%REPO_ROOT%\skills"
set "VALIDATOR=%REPO_ROOT%\tools\validators\quick_validate.py"
set "PYTHON_CMD="
set "PAUSE_ON_EXIT=1"
set "VALIDATED_COUNT=0"
set "EXIT_CODE=0"

:parse_args
if "%~1"=="" goto after_args

if /I "%~1"=="--validator" (
  if "%~2"=="" (
    echo Missing value for --validator
    call :usage
    set "EXIT_CODE=1"
    goto finish
  )
  set "VALIDATOR=%~2"
  shift
  shift
  goto parse_args
)

if /I "%~1"=="--pause" (
  set "PAUSE_ON_EXIT=1"
  shift
  goto parse_args
)

if /I "%~1"=="--no-pause" (
  set "PAUSE_ON_EXIT=0"
  shift
  goto parse_args
)

if /I "%~1"=="-h" (
  call :usage
  goto finish
)

if /I "%~1"=="--help" (
  call :usage
  goto finish
)

echo Unknown argument: %~1
call :usage
set "EXIT_CODE=1"
goto finish

:after_args
echo Skills validation
echo Repository: "%REPO_ROOT%"
echo Validator: "%VALIDATOR%"
echo.

if not exist "%SKILLS_DIR%" (
  echo Skills directory not found: "%SKILLS_DIR%"
  set "EXIT_CODE=1"
  goto finish
)

if not exist "%VALIDATOR%" (
  echo Validator not found: "%VALIDATOR%"
  set "EXIT_CODE=1"
  goto finish
)

if not defined PYTHON_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
  echo Python not found. Install Python and make it available on PATH.
  set "EXIT_CODE=1"
  goto finish
)

for /d %%S in ("%SKILLS_DIR%\*") do (
  echo Validating %%~nxS...
  "%PYTHON_CMD%" "%VALIDATOR%" "%%~fS"
  if errorlevel 1 (
    set "EXIT_CODE=!ERRORLEVEL!"
    echo.
    echo Validation failed for %%~nxS.
    goto finish
  )
  set /a VALIDATED_COUNT+=1
)

goto finish

:usage
echo Usage: tools\windows\validate-all.cmd [--validator PATH] [--no-pause]
exit /b 0

:finish
echo.
if "%EXIT_CODE%"=="0" (
  echo Validation completed. %VALIDATED_COUNT% skills valid.
) else (
  echo Validation stopped with errors. Exit code: %EXIT_CODE%
)

if "%PAUSE_ON_EXIT%"=="1" (
  echo.
  pause
)

exit /b %EXIT_CODE%
