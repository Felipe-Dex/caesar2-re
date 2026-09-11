@echo off
cd /d "%~dp0"

set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 set "PYTHON=py -3"
if not defined PYTHON (
  where python >nul 2>&1
  if not errorlevel 1 set "PYTHON=python"
)
if not defined PYTHON (
  if exist "%LocalAppData%\Programs\Python\Python314\python.exe" (
    set "PYTHON=%LocalAppData%\Programs\Python\Python314\python.exe"
  )
)

if not defined PYTHON (
  echo Python not found. Tried: py -3, python, Python 3.14.
  pause
  exit /b 1
)

%PYTHON% -m app --new --city-only
if errorlevel 1 (
  echo Failed: %PYTHON% -m app --new --city-only
  pause
  exit /b 1
)
