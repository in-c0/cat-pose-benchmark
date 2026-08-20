param(
    [string]$UnityExe = "C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe",
    [string]$PythonExe = "python",
    [switch]$InstallIfMissing
)

$ErrorActionPreference = "Stop"

$PinnedUnityVersion = "6000.3.18f1"
$PinnedUnityChangeset = "5ebeb53e4c07"
$DefaultHubExe = "C:\Program Files\Unity Hub\Unity Hub.exe"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
$projectPath = Join-Path $scriptDir "S0AProxy"
$outputPath = Join-Path $env:TEMP "catpose-s0b-unity.json"
$summaryPath = Join-Path $env:TEMP "catpose-s0b-roundtrip.json"

function Install-PinnedUnityEditor {
    Write-Host "Pinned Unity Editor $PinnedUnityVersion is missing; installation was explicitly requested."

    $unityCli = Get-Command unity -ErrorAction SilentlyContinue
    if ($null -ne $unityCli) {
        Write-Host "Installing with Unity CLI..."
        & $unityCli.Source install $PinnedUnityVersion -c $PinnedUnityChangeset
        if ($LASTEXITCODE -ne 0) {
            throw "Unity CLI failed to install $PinnedUnityVersion (changeset $PinnedUnityChangeset)."
        }
        return
    }

    if (Test-Path -LiteralPath $DefaultHubExe -PathType Leaf) {
        Write-Host "Unity CLI was not found; falling back to the Unity Hub headless CLI."
        Write-Warning "Unity documents the Hub CLI as deprecated from Hub 3.18; install the standalone Unity CLI for new automation if this fallback fails."
        & $DefaultHubExe -- --headless install --version $PinnedUnityVersion --changeset $PinnedUnityChangeset --errors
        if ($LASTEXITCODE -ne 0) {
            throw "Unity Hub CLI failed to install $PinnedUnityVersion (changeset $PinnedUnityChangeset)."
        }
        return
    }

    throw "Neither the standalone Unity CLI nor Unity Hub was found. Install one of them, then rerun with -InstallIfMissing."
}

if (-not (Test-Path -LiteralPath $UnityExe -PathType Leaf)) {
    if ($InstallIfMissing) {
        Install-PinnedUnityEditor
    }
}

if (-not (Test-Path -LiteralPath $UnityExe -PathType Leaf)) {
    throw "Pinned Unity Editor not found at '$UnityExe'. Install Unity $PinnedUnityVersion or rerun with -InstallIfMissing; if installed elsewhere, pass -UnityExe with its exact Unity.exe path."
}

$licenseCandidates = @(
    (Join-Path $env:PROGRAMDATA "Unity\Unity_lic.ulf"),
    (Join-Path $env:LOCALAPPDATA "Unity\licenses\UnityEntitlementLicense.xml")
)
if (-not ($licenseCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })) {
    Write-Warning "No standard local Unity license file was detected. Unity Personal is normally activated by signing into Unity Hub and activating a license under Settings > Licenses. If the Editor reports a licensing error, do that once and rerun this command."
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