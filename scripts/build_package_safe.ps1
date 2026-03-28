param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$buildRoot = Join-Path $root ".build_tmp"
$distRoot = Join-Path $root ".dist_verify"
$trackerRoot = Join-Path $buildRoot "pip-build-tracker"
$cacheRoot = Join-Path $buildRoot "pip-cache"
$wheelRoot = Join-Path $buildRoot "pip-wheel"
$ephemRoot = Join-Path $buildRoot "pip-ephem-wheel"

foreach ($path in @($buildRoot, $distRoot, $trackerRoot, $cacheRoot, $wheelRoot, $ephemRoot)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$env:TMP = $buildRoot
$env:TEMP = $buildRoot
$env:PIP_BUILD_TRACKER = $trackerRoot
$env:PIP_CACHE_DIR = $cacheRoot
$env:PIP_WHEEL_DIR = $wheelRoot
$env:PIP_SRC = $buildRoot

Write-Host "Using build temp root: $buildRoot"
Write-Host "Writing wheel to: $distRoot"

& python scripts\build_package.py

if ($LASTEXITCODE -ne 0) {
    throw "package build failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Package build completed."
