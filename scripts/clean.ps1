<#
.SYNOPSIS
    Cleans temporary test caches, Zarr data stores, and build artifacts.
.EXAMPLE
    .\scripts\clean.ps1
    .\scripts\clean.ps1 -All
#>

[CmdletBinding()]
param(
    [switch]$All
)

$RootDir = Split-Path -Parent $PSScriptRoot

Write-Host "[*] Cleaning workspace: $RootDir" -ForegroundColor Cyan

# 1. Folders to delete
$TargetDirs = @(
    "$RootDir\.pytest_cache",
    "$RootDir\.benchmarks",
    "$RootDir\test_run",
    "$RootDir\run",
    "$RootDir\run_demo",
    "$RootDir\htmlcov",
    "$RootDir\.coverage"
)

if ($All) {
    $TargetDirs += "$RootDir\build"
    $TargetDirs += "$RootDir\dist"
    $TargetDirs += "$RootDir\.eggs"
}

foreach ($dir in $TargetDirs) {
    if (Test-Path $dir) {
        Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
        Write-Host "  [-] Removed $(Split-Path -Leaf $dir)" -ForegroundColor Yellow
    }
}

# 2. Any root *.zarr folders
Get-ChildItem -Path $RootDir -Directory -Filter "*.zarr" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
    Write-Host "  [-] Removed $($_.Name)" -ForegroundColor Yellow
}

# 3. Clean __pycache__ (excluding .venv)
Get-ChildItem -Path $RootDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "\\\.venv\\" } |
    ForEach-Object {
        Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue
    }

# 4. Clean leftover report files
$Report = "$RootDir\benchmark_report.json"
if (Test-Path $Report) {
    Remove-Item -Force $Report -ErrorAction SilentlyContinue
    Write-Host "  [-] Removed benchmark_report.json" -ForegroundColor Yellow
}

Write-Host "[+] Workspace clean complete!`n" -ForegroundColor Green
