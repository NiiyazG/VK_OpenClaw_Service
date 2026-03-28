param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$buildRoot = Join-Path $root ".build_tmp"
$distRoot = Join-Path $root ".dist_verify"

foreach ($path in @($buildRoot, $distRoot)) {
    New-Item -ItemType Directory -Force -Path $path | Out-Null
}

$env:TMP = $buildRoot
$env:TEMP = $buildRoot

Write-Host "Using build temp root: $buildRoot"
Write-Host "Writing sdist to: $distRoot"

& python scripts\build_sdist.py

if ($LASTEXITCODE -ne 0) {
    throw "sdist build failed with exit code $LASTEXITCODE"
}

Write-Host ""
Write-Host "Source distribution build completed."
