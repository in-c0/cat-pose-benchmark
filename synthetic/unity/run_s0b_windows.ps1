param(
    [string]$UnityExe = "C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$projectPath = Join-Path $scriptDir "S0AProxy"
$outputPath = Join-Path $env:TEMP "catpose-s0b-unity.json"
$summaryPath = Join-Path $env:TEMP "catpose-s0b-roundtrip.json"

if (-not (Test-Path -LiteralPath $UnityExe -PathType Leaf)) {
    throw "Pinned Unity Editor not found at '$UnityExe'. Install Unity 6000.3.18f1 or pass -UnityExe with its exact Unity.exe path."
}

Write-Host "Running pinned Unity S0B export..."
& $UnityExe `
    -batchmode `
    -quit `
    -projectPath $projectPath `
    -executeMethod CatPose.S0B.S0BProxyExportCommand.Run `
    -s0Output $outputPath `
    -logFile -

if ($LASTEXITCODE -ne 0) {
    throw "Unity S0B export failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Unity exited without producing '$outputPath'."
}

Write-Host "Running authoritative Python round-trip gate..."
Push-Location $repoRoot
try {
    & $PythonExe -m synthetic.unity_roundtrip $outputPath --summary $summaryPath
    if ($LASTEXITCODE -ne 0) {
        throw "S0B round-trip comparator reported a contract mismatch."
    }
}
finally {
    Pop-Location
}

$summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
if (-not $summary.contract_valid) {
    throw "Round-trip summary is not contract-valid."
}
if (-not $summary.unity_runtime_verified) {
    throw "Round-trip completed without verifying a real Unity runtime source."
}
if ($summary.performance_analysis_performed) {
    throw "Unexpected performance analysis flag in S0B round-trip report."
}

Write-Host "S0B Unity runtime verified: zero contract mismatches."
Write-Host "Export:  $outputPath"
Write-Host "Summary: $summaryPath"
