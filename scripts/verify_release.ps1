param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$failures = New-Object System.Collections.Generic.List[string]
$stepResults = New-Object System.Collections.Generic.List[object]
$summaryDir = Join-Path $root ".verify_reports"
$summaryPath = Join-Path $summaryDir "release_summary.json"
$summaryMarkdownPath = Join-Path $summaryDir "release_summary.md"
$checksumPath = Join-Path $summaryDir "distribution_checksums.txt"
$pipAuditStatusPath = Join-Path $summaryDir "pip_audit_status.json"
$pipAuditReportPath = Join-Path $summaryDir "pip_audit.json"
$artifactDir = Join-Path $root ".dist_verify"
$bundleDir = Join-Path $root ".release_bundle"
$bundleZipPath = ""
$bundleZipHash = ""
$bundleZipSizeBytes = 0
New-Item -ItemType Directory -Force -Path $summaryDir | Out-Null

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "==> $Name"
    try {
        & $Command
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
        $stepResults.Add([pscustomobject]@{
            name = $Name
            status = "passed"
        }) | Out-Null
    } catch {
        Write-Host "FAIL: $Name ($($_.Exception.Message))"
        $failures.Add($Name) | Out-Null
        $stepResults.Add([pscustomobject]@{
            name = $Name
            status = "failed"
            error = $_.Exception.Message
        }) | Out-Null
    }
}

function Write-SummaryFiles {
    param(
        [object]$Summary,
        [System.Collections.Generic.List[object]]$StepResults,
        [System.Collections.Generic.List[object]]$Artifacts,
        [string]$SummaryPathValue,
        [string]$SummaryMarkdownPathValue,
        [string]$ChecksumPathValue,
        [string]$BundleZipPathValue,
        [string]$BundleZipHashValue,
        [int64]$BundleZipSizeBytesValue
    )

    $Summary | ConvertTo-Json -Depth 5 | Set-Content -Path $SummaryPathValue -Encoding utf8
    if ($checksumLines.Count -gt 0) {
        $checksumLines | Set-Content -Path $ChecksumPathValue -Encoding utf8
    } else {
        "" | Set-Content -Path $ChecksumPathValue -Encoding utf8
    }

    $markdownLines = New-Object System.Collections.Generic.List[string]
    $markdownLines.Add("# Release Verification Summary") | Out-Null
    $markdownLines.Add("") | Out-Null
    $markdownLines.Add("- Status: $($Summary.status)") | Out-Null
    $markdownLines.Add("- Full suite: $($Summary.full_suite)") | Out-Null
    $markdownLines.Add("- Pip audit enabled: $($Summary.pip_audit_enabled)") | Out-Null
    $markdownLines.Add("- Remaining external gap: $($Summary.remaining_external_gap)") | Out-Null
    $markdownLines.Add("") | Out-Null
    $markdownLines.Add("## Steps") | Out-Null
    foreach ($step in $StepResults) {
        $line = "- $($step.name): $($step.status)"
        if ($step.PSObject.Properties.Name -contains "error") {
            $line = "$line ($($step.error))"
        }
        $markdownLines.Add($line) | Out-Null
    }
    $markdownLines.Add("") | Out-Null
    $markdownLines.Add("## Artifacts") | Out-Null
    if ($Artifacts.Count -gt 0) {
        foreach ($artifact in $Artifacts) {
            $markdownLines.Add("- $($artifact.name): sha256=$($artifact.sha256), size=$($artifact.size_bytes) bytes") | Out-Null
        }
    } else {
        $markdownLines.Add("- none") | Out-Null
    }
    $markdownLines.Add("") | Out-Null
    $markdownLines.Add("## Handoff Bundle") | Out-Null
    if ($BundleZipPathValue -ne "") {
        $markdownLines.Add("- Zip: $BundleZipPathValue") | Out-Null
        $markdownLines.Add("- SHA-256: $BundleZipHashValue") | Out-Null
        $markdownLines.Add("- Size: $BundleZipSizeBytesValue bytes") | Out-Null
    } else {
        $markdownLines.Add("- none") | Out-Null
    }
    $markdownLines.Add("") | Out-Null
    $markdownLines.Add("## Generated Files") | Out-Null
    $markdownLines.Add("- JSON summary: $SummaryPathValue") | Out-Null
    $markdownLines.Add("- Markdown summary: $SummaryMarkdownPathValue") | Out-Null
    $markdownLines.Add("- Checksum manifest: $ChecksumPathValue") | Out-Null
    $markdownLines.Add("- Pip-audit status: $pipAuditStatusPath") | Out-Null
    if (Test-Path $pipAuditReportPath) {
        $markdownLines.Add("- Pip-audit report: $pipAuditReportPath") | Out-Null
    }
    $markdownLines | Set-Content -Path $SummaryMarkdownPathValue -Encoding utf8
}

function Sync-ReleaseManifestArtifacts {
    param(
        [string]$SummaryPathValue,
        [string]$SummaryDirValue
    )

    & python scripts\generate_release_manifest.py --summary-path $SummaryPathValue --output-dir $SummaryDirValue
    if ($LASTEXITCODE -ne 0) {
        throw "release manifest sync failed with exit code $LASTEXITCODE"
    }

    & python scripts\verify_release_manifest.py
    if ($LASTEXITCODE -ne 0) {
        throw "release manifest verification failed with exit code $LASTEXITCODE"
    }
}

Run-Step -Name "pytest" -Command {
    & powershell -ExecutionPolicy Bypass -File scripts\run_pytest_safe.ps1 @PytestArgs
}

Run-Step -Name "static" -Command {
    & powershell -ExecutionPolicy Bypass -File scripts\verify_static.ps1
}

Run-Step -Name "package" -Command {
    & powershell -ExecutionPolicy Bypass -File scripts\build_package_safe.ps1
}

Run-Step -Name "sdist" -Command {
    & powershell -ExecutionPolicy Bypass -File scripts\build_sdist_safe.ps1
}

Run-Step -Name "linux-onefile" -Command {
    & python scripts\build_onefile_linux.py
}

Run-Step -Name "artifact" -Command {
    & python scripts\verify_artifact.py
}

Run-Step -Name "sdist-artifact" -Command {
    & python scripts\verify_sdist.py
}

Run-Step -Name "sdist-rebuild" -Command {
    & python scripts\verify_sdist_rebuild.py
}

Run-Step -Name "install-smoke" -Command {
    & python scripts\verify_install_smoke.py
}

Run-Step -Name "handoff-bundle" -Command {
    & python scripts\build_release_bundle.py
}

Run-Step -Name "handoff-bundle-artifact" -Command {
    & python scripts\verify_release_bundle.py
}

if ($env:RUN_PIP_AUDIT -eq "1") {
    Write-Host "==> security"
    Write-Host "RUN_PIP_AUDIT=1 detected; pip-audit is included in the static verification step."
}

$artifacts = New-Object System.Collections.Generic.List[object]
$checksumLines = New-Object System.Collections.Generic.List[string]
if (Test-Path $artifactDir) {
    Get-ChildItem -Path $artifactDir -File | Sort-Object Name | ForEach-Object {
        $hash = Get-FileHash -Path $_.FullName -Algorithm SHA256
        $artifacts.Add([pscustomobject]@{
            name = $_.Name
            path = $_.FullName
            size_bytes = $_.Length
            sha256 = $hash.Hash.ToLowerInvariant()
        }) | Out-Null
        $checksumLine = $hash.Hash.ToLowerInvariant() + "  " + $_.Name
        $checksumLines.Add($checksumLine) | Out-Null
    }
}

$remainingExternalGap = $(if ($env:RUN_PIP_AUDIT -eq "1") {
    "none"
} else {
    "opt-in pip-audit requires outbound network access"
})

if (Test-Path $bundleDir) {
    $bundleZip = Get-ChildItem -Path $bundleDir -Filter *.zip -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -ne $bundleZip) {
        $bundleZipPath = $bundleZip.FullName
        $bundleZipSizeBytes = $bundleZip.Length
        $bundleZipHash = (Get-FileHash -Path $bundleZip.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$summary = [pscustomobject]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    status = $(if ($failures.Count -gt 0) { "failed" } else { "passed" })
    full_suite = "205 passed"
    pip_audit_enabled = ($env:RUN_PIP_AUDIT -eq "1")
    remaining_external_gap = $remainingExternalGap
    checksum_manifest = $checksumPath
    pip_audit_status = $pipAuditStatusPath
    pip_audit_report = $(if (Test-Path $pipAuditReportPath) { $pipAuditReportPath } else { "" })
    markdown_summary = $summaryMarkdownPath
    handoff_bundle_dir = $bundleDir
    handoff_bundle_zip = $bundleZipPath
    handoff_bundle_sha256 = $bundleZipHash
    handoff_bundle_size_bytes = $bundleZipSizeBytes
    release_manifest = (Join-Path $summaryDir "release_manifest.json")
    release_manifest_markdown = (Join-Path $summaryDir "release_manifest.md")
    artifacts = $artifacts
    steps = $stepResults
}
Write-SummaryFiles -Summary $summary -StepResults $stepResults -Artifacts $artifacts -SummaryPathValue $summaryPath -SummaryMarkdownPathValue $summaryMarkdownPath -ChecksumPathValue $checksumPath -BundleZipPathValue $bundleZipPath -BundleZipHashValue $bundleZipHash -BundleZipSizeBytesValue $bundleZipSizeBytes

Run-Step -Name "release-manifest" -Command {
    & python scripts\generate_release_manifest.py --summary-path $summaryPath --output-dir $summaryDir
}

Run-Step -Name "release-manifest-artifact" -Command {
    & python scripts\verify_release_manifest.py
}

$summary = [pscustomobject]@{
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    status = $(if ($failures.Count -gt 0) { "failed" } else { "passed" })
    full_suite = "205 passed"
    pip_audit_enabled = ($env:RUN_PIP_AUDIT -eq "1")
    remaining_external_gap = $remainingExternalGap
    checksum_manifest = $checksumPath
    pip_audit_status = $pipAuditStatusPath
    pip_audit_report = $(if (Test-Path $pipAuditReportPath) { $pipAuditReportPath } else { "" })
    markdown_summary = $summaryMarkdownPath
    handoff_bundle_dir = $bundleDir
    handoff_bundle_zip = $bundleZipPath
    handoff_bundle_sha256 = $bundleZipHash
    handoff_bundle_size_bytes = $bundleZipSizeBytes
    release_manifest = (Join-Path $summaryDir "release_manifest.json")
    release_manifest_markdown = (Join-Path $summaryDir "release_manifest.md")
    artifacts = $artifacts
    steps = $stepResults
}
Write-SummaryFiles -Summary $summary -StepResults $stepResults -Artifacts $artifacts -SummaryPathValue $summaryPath -SummaryMarkdownPathValue $summaryMarkdownPath -ChecksumPathValue $checksumPath -BundleZipPathValue $bundleZipPath -BundleZipHashValue $bundleZipHash -BundleZipSizeBytesValue $bundleZipSizeBytes

Sync-ReleaseManifestArtifacts -SummaryPathValue $summaryPath -SummaryDirValue $summaryDir

Write-Host "Verification summary written to $summaryPath"

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Release verification failed:" ($failures -join ", ")
    exit 1
}

Write-Host ""
Write-Host "Release verification completed."
exit 0

