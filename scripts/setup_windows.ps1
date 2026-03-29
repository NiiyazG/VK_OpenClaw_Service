param(
    [switch]$NonInteractive,
    [string]$ConfigPath = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.12+ and retry."
}

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .

$Args = @("setup")
if ($NonInteractive) { $Args += "--non-interactive" }
if ($DryRun) { $Args += "--dry-run" }
if ($ConfigPath) { $Args += @("--config", $ConfigPath) }

& .\.venv\Scripts\vk-openclaw.exe @Args
