#
.SYNOPSIS
    Automated environment bootstrapper and launcher for Voucher Forge.
.DESCRIPTION
    Checks Python availability, creates local .venv, installs dependencies 
    from pyproject.toml (editable + dev), and launches the app or test suite.
.PARAMETER Test
    Runs the pytest test suite instead of starting the web UI.
#
param (
    [switch]$Test
)

$ErrorActionPreference = Stop
$ScriptDir = Split-Path -Parent$MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host == [Voucher Forge Bootstrapper] -ForegroundColor Cyan

# 1. Locate or install Python
$PythonCmd =$null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = py -3.12
    if (-not (& py -3.12 --version 2$null)) {$PythonCmd = py
    }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = python
} else {
    Write-Warning Python was not found in PATH.
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host Attempting automatic installation via winget... -ForegroundColor Yellow
        winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
        # Refresh environment PATH in current session
        $envPath = [System.Environment]GetEnvironmentVariable(Path,Machine) + ; + [System.Environment]GetEnvironmentVariable(Path,User)
        $PythonCmd = python
    } else {
        Write-Error CRITICAL Python 3.11+ is not installed and winget is unavailable. Please install Python manually.
        exit 1
    }
}

Write-Host - Using Python launcher $PythonCmd -ForegroundColor DarkGray

# 2. Virtual Environment management
$VenvDir = Join-Path$ScriptDir .venv
$VenvPython = Join-Path$VenvDir Scriptspython.exe
$VenvPytest = Join-Path$VenvDir Scriptspytest.exe

if (-not (Test-Path $VenvPython)) {
    Write-Host - Creating virtual environment at .venv... -ForegroundColor Yellow
    Invoke-Expression $PythonCmd -m venv `$VenvDir`
}

# 3. Dependency check and synchronization
$StampFile = Join-Path$VenvDir .installed.stamp
$PyprojectFile = Join-Path$ScriptDir pyproject.toml
$NeedsInstall =$true

if (Test-Path $StampFile) {
    $StampTime = (Get-Item$StampFile).LastWriteTimeUtc
    $TomlTime = (Get-Item$PyprojectFile).LastWriteTimeUtc
    if ($StampTime -ge$TomlTime) {
        $NeedsInstall =$false
    }
}

if ($NeedsInstall) {
    Write-Host - Installing  updating project dependencies from pyproject.toml... -ForegroundColor Yellow
    & $VenvPython -m pip install --upgrade pip --quiet
    & $VenvPython -m pip install -e .[dev] --quiet
    Set-Content -Path $StampFile -Value (Get-Date).ToString(o)
    Write-Host - Environment is up to date. -ForegroundColor Green
}

# 4. Execution mode Test Suite vs Web App
if ($Test) {
    Write-Host - Running test suite via pytest... -ForegroundColor Cyan
    & $VenvPytest -v
    exit $LASTEXITCODE
} else {
    Write-Host - Starting Voucher Forge application... -ForegroundColor Green
    & $VenvPython run.py
}