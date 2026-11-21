# Perandam Space Intelligence - SpecSynth HTTP Bridge Launcher
$PythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

Write-Host "Launching PerandamΨ SpecSynth HTTP Bridge..." -ForegroundColor Cyan
& $PythonExe -m specsynth.mcp.bridge --port 8000
