param (
    [switch]$Test
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==> [Voucher Forge Bootstrapper]" -ForegroundColor Cyan

function Test-PythonVersion($cmd, $argsList) {
    try {
        $output = & $cmd $argsList -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($output -match '^3\.(\d+)$') {
            $minor = [int]$matches[1]
            if ($minor -ge 11) {
                return $true
            }
        }
    } catch {}
    return $false
}

# 1. Dynamic Python runtime detection (requires >= 3.11)
$ResolvedExe = $null
$ResolvedArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    if (Test-PythonVersion "py" @("-3")) {
        $ResolvedExe = "py"
        $ResolvedArgs = @("-3")
    }
}

if (-not $ResolvedExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Test-PythonVersion "python" @()) {
        $ResolvedExe = "python"
        $ResolvedArgs = @()
    }
}

# 2. Interactive prompt if no compatible Python >= 3.11 is found
if (-not $ResolvedExe) {
    Write-Warning "Python >= 3.11 is required, but no compatible runtime was found."
    
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        $choice = Read-Host "Would you like to automatically install Python using winget? [Y/n]"
        if ($choice -eq "" -or $choice -match '^[Yy]') {
            Write-Host "Installing Python via winget..." -ForegroundColor Yellow
            winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
            
            # Refresh PATH for the current session
            $machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
            $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
            $env:Path = "$machinePath;$userPath"

            if (Test-PythonVersion "python" @()) {
                $ResolvedExe = "python"
                $ResolvedArgs = @()
            } elseif (Get-Command py -ErrorAction SilentlyContinue) {
                $ResolvedExe = "py"
                $ResolvedArgs = @("-3")
            }
        }
    }
}

if (-not $ResolvedExe) {
    Write-Error "STOPPED: No compatible Python >= 3.11 runtime found. Please install Python manually."
    exit 1
}

$verDisplay = & $ResolvedExe $ResolvedArgs -c "import sys; print(sys.version.split()[0])"
Write-Host "-> Found compatible Python runtime: $verDisplay ($ResolvedExe $ResolvedArgs)" -ForegroundColor Green

# 3. Virtual environment management (.venv)
$VenvDir = Join-Path $ScriptDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPytest = Join-Path $VenvDir "Scripts\pytest.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "-> Creating virtual environment at .venv..." -ForegroundColor Yellow
    & $ResolvedExe $ResolvedArgs -m venv $VenvDir
}

# 4. Dependency synchronization with pyproject.toml
$StampFile = Join-Path $VenvDir ".installed.stamp"
$PyprojectFile = Join-Path $ScriptDir "pyproject.toml"
$NeedsInstall = $true

if (Test-Path $StampFile) {
    $StampTime = (Get-Item $StampFile).LastWriteTimeUtc
    $TomlTime = (Get-Item $PyprojectFile).LastWriteTimeUtc
    if ($StampTime -ge $TomlTime) {
        $NeedsInstall = $false
    }
}

if ($NeedsInstall) {
    Write-Host "-> Installing / updating project dependencies from pyproject.toml..." -ForegroundColor Yellow
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERROR: Failed to upgrade pip."
        exit $LASTEXITCODE
    }

    & $VenvPython -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERROR: Failed to install project dependencies via pip."
        exit $LASTEXITCODE
    }

    Set-Content -Path $StampFile -Value (Get-Date).ToString("o")
    Write-Host "-> Environment synchronized successfully." -ForegroundColor Green
}

# 5. Execution mode: Test Suite vs Web App
if ($Test) {
    Write-Host "-> Running test suite via pytest..." -ForegroundColor Cyan
    & $VenvPytest -v
    exit $LASTEXITCODE
} else {
    Write-Host "-> Launching Voucher Forge..." -ForegroundColor Green
    & $VenvPython run.py
}