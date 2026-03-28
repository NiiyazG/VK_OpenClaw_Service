param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$root = Get-Location
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$baseTemp = Join-Path $root ".pytest_tmp_runs\$timestamp"
New-Item -ItemType Directory -Path $baseTemp -Force | Out-Null
$env:PYTEST_DISABLE_DEAD_SYMLINK_CLEANUP = "1"

$args = @("-m", "pytest", "--basetemp", $baseTemp)
$args += @("-p", "no:cacheprovider")
if ($PytestArgs) {
    $args += $PytestArgs
}

Write-Host "Using pytest base temp: $baseTemp"
Write-Host "Pytest cacheprovider disabled to reduce sandbox cache permission noise"
& python @args
exit $LASTEXITCODE
