param(
    [string]$UnityExe = "C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe",
    [string]$PythonExe = "python",
    [switch]$InstallIfMissing,
    [switch]$RequireCanonicalPin
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
$unityLogPath = Join-Path $env:TEMP "catpose-s0b-unity.log"

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
    throw "Unity Editor not found at '$UnityExe'. The canonical pin is Unity $PinnedUnityVersion. Install it with -InstallIfMissing, or pass -UnityExe for another final-release Unity 6000.3.x editor to run the documented compatibility gate."
}

$licenseCandidates = @(
    (Join-Path $env:PROGRAMDATA "Unity\Unity_lic.ulf"),
    (Join-Path $env:LOCALAPPDATA "Unity\licenses\UnityEntitlementLicense.xml")
)
if (-not ($licenseCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })) {
    Write-Warning "No standard local Unity license file was detected. Unity Personal is normally activated by signing into Unity Hub and activating a license under Settings > Licenses. If the Editor reports a licensing error, do that once and rerun this command."
}

Write-Host "Running Unity S0B export..."
Write-Host "Canonical reproducibility pin: $PinnedUnityVersion"
Write-Host "Editor executable: $UnityExe"

# Windows PowerShell 5.1 can leave $LASTEXITCODE unset for redirected native
# processes. Use the Process.ExitCode returned by Start-Process instead, and
# write Unity's log to a file rather than relying on redirected process streams.
$unityArgs = @(
    "-batchmode",
    "-quit",
    "-projectPath", "`"$projectPath`"",
    "-executeMethod", "CatPose.S0B.S0BProxyExportCommand.Run",
    "-s0Output", "`"$outputPath`"",
    "-logFile", "`"$unityLogPath`""
)
$unityProcess = Start-Process `
    -FilePath $UnityExe `
    -ArgumentList $unityArgs `
    -Wait `
    -PassThru `
    -NoNewWindow
$unityExitCode = $unityProcess.ExitCode

if ($unityExitCode -ne 0) {
    if (Test-Path -LiteralPath $unityLogPath -PathType Leaf) {
        Write-Host "---- Unity log tail ----"
        Get-Content -LiteralPath $unityLogPath -Tail 80
        Write-Host "---- end Unity log tail ----"
    }
    throw "Unity S0B export failed with exit code $unityExitCode."
}
if (-not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw "Unity exited 0 without producing '$outputPath'. See '$unityLogPath'."
}

Write-Host "Running authoritative Unity 6.3 LTS compatibility gate..."
Push-Location $repoRoot
try {
    $comparatorArgs = @(
        "-m", "synthetic.unity_runtime_compat",
        $outputPath,
        "--summary", $summaryPath
    )
    if ($RequireCanonicalPin) {
        $comparatorArgs += "--require-canonical-pin"
    }
    & $PythonExe @comparatorArgs
    if ($LASTEXITCODE -ne 0) {
        if ($RequireCanonicalPin) {
            throw "S0B round-trip did not satisfy the exact canonical Unity pin."
        }
        throw "S0B round-trip did not satisfy the Unity 6.3 LTS compatibility gate."
    }
}
finally {
    Pop-Location
}

$summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
if (-not $summary.compatibility_contract_valid) {
    throw "Round-trip compatibility summary is not contract-valid."
}
if (-not $summary.compatible_runtime_verified) {
    throw "Round-trip completed without verifying a compatible real Unity 6.3 LTS runtime."
}
if ($RequireCanonicalPin -and -not $summary.canonical_pin_verified) {
    throw "Compatible runtime passed, but the exact canonical Editor pin was not executed."
}
if ($summary.performance_analysis_performed) {
    throw "Unexpected performance analysis flag in S0B round-trip report."
}

if ($summary.canonical_pin_verified) {
    Write-Host "S0B canonical Unity runtime verified: zero contract mismatches."
} else {
    Write-Host "S0B compatible Unity 6.3 LTS runtime verified: zero non-version contract mismatches."
    Write-Host "Actual editor:    $($summary.actual_unity_editor_version)"
    Write-Host "Canonical editor: $($summary.canonical_unity_editor_version) (not executed in this run)"
}
Write-Host "Export:  $outputPath"
Write-Host "Summary: $summaryPath"
Write-Host "Unity log: $unityLogPath"
