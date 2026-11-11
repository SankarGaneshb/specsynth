<#
.SYNOPSIS
    Runs specsynth test suite using .venv Python and cleans up test artifacts automatically.
.EXAMPLE
    .\test.ps1
    .\test.ps1 -k test_benchmark
    .\test.ps1 -NoClean
#>

[CmdletBinding()]
param(
    [switch]$NoClean,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$RootDir = $PSScriptRoot

# Locate virtualenv Python or fallback
$VenvPy = "$RootDir\.venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $PythonExe = $VenvPy
} else {
    $PythonExe = "python"
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Running specsynth test suite using: $PythonExe" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Combine arguments
$ArgsList = @("-m", "pytest", "-v") + $PytestArgs

$ExitCode = 0
try {
    & $PythonExe $ArgsList
    $ExitCode = $LASTEXITCODE
} finally {
    if (-not $NoClean) {
        Write-Host "`n[*] Cleaning up test caches and temporary artifacts..." -ForegroundColor DarkGray
        & "$RootDir\.venv\Scripts\python.exe" "$RootDir\scripts\clean.py"
    }
}

exit $ExitCode
