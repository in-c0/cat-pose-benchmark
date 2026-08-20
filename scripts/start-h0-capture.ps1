[CmdletBinding()]
param(
    [string]$SubjectId,
    [string]$HouseholdId,
    [string]$SessionId,
    [string]$OutputDir,
    [switch]$NoPersistDefaults
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LocalRoot = Join-Path $RepoRoot "local-data"
$ConfigPath = Join-Path $LocalRoot "h0-launcher-config.json"
if (-not $OutputDir) {
    $OutputDir = Join-Path $LocalRoot "ct1-h0"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path $RepoRoot $OutputDir
}

function Assert-SafeId {
    param([string]$Value, [string]$Field)
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -notmatch '^[A-Za-z0-9._+\-]{1,128}$') {
        throw "$Field must contain only letters, digits, '.', '_', '+', '-' and be <=128 characters."
    }
    return $Value
}

function Resolve-Python {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return [pscustomobject]@{ Exe = $py.Source; Prefix = @('-3') }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return [pscustomobject]@{ Exe = $python.Source; Prefix = @() }
    }
    throw "Python 3 was not found. Install Python 3 or make 'py'/'python' available on PATH."
}

New-Item -ItemType Directory -Force -Path $LocalRoot | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# When this is a Git checkout, fail closed if the private local-data path is not ignored.
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git -and (Test-Path (Join-Path $RepoRoot ".git"))) {
    Push-Location $RepoRoot
    try {
        & $git.Source check-ignore -q -- "local-data/h0-launcher-config.json"
        if ($LASTEXITCODE -ne 0) {
            throw "Privacy preflight failed: local-data/ is not ignored by Git. Do not capture household data."
        }
    } finally {
        Pop-Location
    }
}

$defaults = $null
if (Test-Path $ConfigPath) {
    try {
        $defaults = Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json
    } catch {
        throw "Could not parse local H0 launcher defaults at $ConfigPath. Delete or repair that ignored file and retry."
    }
}

if (-not $SubjectId -and $defaults -and $defaults.subject_id) {
    $SubjectId = [string]$defaults.subject_id
}
if (-not $HouseholdId -and $defaults -and $defaults.household_id) {
    $HouseholdId = [string]$defaults.household_id
}
if (-not $SubjectId) {
    $SubjectId = Read-Host "Pseudonymous subject ID (example: cat-01)"
}
if (-not $HouseholdId) {
    $HouseholdId = Read-Host "Pseudonymous household ID (example: hh-01)"
}
if (-not $SessionId) {
    $SessionId = "session-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}

$SubjectId = Assert-SafeId $SubjectId "SubjectId"
$HouseholdId = Assert-SafeId $HouseholdId "HouseholdId"
$SessionId = Assert-SafeId $SessionId "SessionId"

if (-not $NoPersistDefaults) {
    # Deliberately persist only stable pseudonymous IDs. Never write episode, outcome,
    # audio, hypothesis, model, or performance data to this launcher config.
    $localDefaults = [ordered]@{
        subject_id = $SubjectId
        household_id = $HouseholdId
    }
    $localDefaults | ConvertTo-Json | Set-Content -Encoding UTF8 -Path $ConfigPath
}

$python = Resolve-Python
Push-Location $RepoRoot
try {
    Write-Host ""
    Write-Host "CT1.3 H0 household capture" -ForegroundColor Cyan
    Write-Host "  Natural episodes only; never provoke, delay ordinary care, restrain, or startle."
    Write-Host "  H0 ends after the first 10 eligible strict-valid episodes."
    Write-Host "  Do NOT inspect predictor coefficients, model scores, feature/target associations, or audio incremental performance during H0."
    Write-Host "  Allowed H0 planning quantities: prevalence, missingness, episode rate, temporal dependence."
    Write-Host ""
    Write-Host "subject=$SubjectId household=$HouseholdId session=$SessionId"
    Write-Host "private output=$OutputDir"
    Write-Host ""

    # Lightweight import preflight: this exercises the canonical secure launcher import
    # without opening a port or starting any analysis/model code.
    $preflightArgs = @($python.Prefix) + @(
        '-c',
        "from audio.a1_capture_station_secure import SECURE_SERVER_VERSION; print('preflight:', SECURE_SERVER_VERSION)"
    )
    & $python.Exe @preflightArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Secure capture-station import preflight failed."
    }

    $launchArgs = @($python.Prefix) + @(
        '-m', 'audio.a1_capture_station_secure',
        '--output-dir', $OutputDir,
        '--subject-id', $SubjectId,
        '--household-id', $HouseholdId,
        '--session-id', $SessionId,
        '--open-browser'
    )
    & $python.Exe @launchArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Secure capture station exited with code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
