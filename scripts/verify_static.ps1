param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$runPipAudit = $env:RUN_PIP_AUDIT -eq "1"
$reportsDir = Join-Path $root ".verify_reports"
$pipAuditReportPath = Join-Path $reportsDir "pip_audit.json"
$pipAuditStatusPath = Join-Path $reportsDir "pip_audit_status.json"

New-Item -ItemType Directory -Force -Path $reportsDir | Out-Null

$pythonFiles = @(
    "src",
    "tests"
)

$failures = New-Object System.Collections.Generic.List[string]

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command,
        [switch]$Optional
    )

    Write-Host "==> $Name"
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
    } catch {
        if ($Optional) {
            Write-Host "SKIP: $Name ($($_.Exception.Message))"
            return
        }
        Write-Host "FAIL: $Name ($($_.Exception.Message))"
        $failures.Add($Name) | Out-Null
    }
}

Run-Step -Name "compileall" -Command {
    & python -m compileall @pythonFiles
}

Run-Step -Name "ruff" -Optional -Command {
    & python -m ruff check src tests
}

Run-Step -Name "mypy" -Optional -Command {
    & python -m mypy src
}

Run-Step -Name "bandit" -Optional -Command {
    & python -m bandit -r src
}

if ($runPipAudit) {
    Write-Host "==> pip-audit"
    try {
        & python -m pip_audit -f json -o $pipAuditReportPath
        if ($LASTEXITCODE -ne 0) {
            throw "pip-audit failed with exit code $LASTEXITCODE"
        }

        [pscustomobject]@{
            generated_at_utc = [DateTime]::UtcNow.ToString("o")
            enabled = $true
            status = "passed"
            report_path = $pipAuditReportPath
        } | ConvertTo-Json -Depth 3 | Set-Content -Path $pipAuditStatusPath -Encoding utf8
    } catch {
        Write-Host "SKIP: pip-audit ($($_.Exception.Message))"
        [pscustomobject]@{
            generated_at_utc = [DateTime]::UtcNow.ToString("o")
            enabled = $true
            status = "skipped"
            report_path = $pipAuditReportPath
            error = $_.Exception.Message
        } | ConvertTo-Json -Depth 3 | Set-Content -Path $pipAuditStatusPath -Encoding utf8
    }
} else {
    Write-Host "==> pip-audit"
    Write-Host "SKIP: pip-audit (set RUN_PIP_AUDIT=1 to enable the online dependency audit)"
    [pscustomobject]@{
        generated_at_utc = [DateTime]::UtcNow.ToString("o")
        enabled = $false
        status = "skipped"
        report_path = $pipAuditReportPath
        error = "set RUN_PIP_AUDIT=1 to enable the online dependency audit"
    } | ConvertTo-Json -Depth 3 | Set-Content -Path $pipAuditStatusPath -Encoding utf8
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Static verification failed:" ($failures -join ", ")
    exit 1
}

Write-Host ""
Write-Host "Static verification completed."
exit 0
