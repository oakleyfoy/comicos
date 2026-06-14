#Requires -Version 5.1
<#
.SYNOPSIS
  Overnight P97 catalog population: ComicVine series imports, harvest, fingerprints, OCR.
.DESCRIPTION
  Run from apps/api. Logs to data/p97/overnight_catalog_run.log
.PARAMETER WhatIf
  Print planned commands and pass safety checks without executing imports or post-processing.
#>
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

$env:DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
# Do not set COMICVINE_API_KEY here — resolve from ENV or apps/api/.env below.

$ApiRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $ApiRoot ".env"
$Script:ComicVineKeySource = $null
$LogDir = Join-Path $ApiRoot "data\p97"
$LogFile = Join-Path $LogDir "overnight_catalog_run.log"
$StartTime = Get-Date

$SeriesTargets = @(
    "Batman",
    "Detective Comics",
    "Superman",
    "Action Comics",
    "Amazing Spider-Man",
    "Uncanny X-Men",
    "X-Men",
    "Wolverine",
    "Venom",
    "Fantastic Four",
    "Avengers",
    "Justice League",
    "Teenage Mutant Ninja Turtles",
    "Hellboy",
    "B.P.R.D.",
    "The Goon",
    "Spawn",
    "Invincible",
    "Savage Dragon"
)

function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")][string]$Level = "INFO"
    )
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [$Level] $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Command
    )
    Write-Log "START $Label"
    Write-Log ("  > " + ($Command -join " "))
    if ($WhatIf) {
        Write-Log "  (WhatIf: skipped)"
        return 0
    }
    & $Command[0] @($Command[1..($Command.Length - 1)])
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    if ($exitCode -ne 0) {
        Write-Log "FAILED $Label (exit $exitCode)" -Level "WARN"
    } else {
        Write-Log "DONE $Label"
    }
    return $exitCode
}

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($trimmed -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)$") {
            $raw = $Matches[1].Trim()
            if ($raw.Length -ge 2) {
                if (($raw.StartsWith('"') -and $raw.EndsWith('"')) -or ($raw.StartsWith("'") -and $raw.EndsWith("'"))) {
                    return $raw.Substring(1, $raw.Length - 2)
                }
            }
            return $raw
        }
    }
    return $null
}

function Initialize-ComicVineApiKey {
    $existing = $env:COMICVINE_API_KEY
    if (-not [string]::IsNullOrWhiteSpace($existing)) {
        $env:COMICVINE_API_KEY = $existing.Trim()
        $Script:ComicVineKeySource = "ENV"
        return
    }
    $fromFile = Get-DotEnvValue -Path $EnvFile -Name "COMICVINE_API_KEY"
    if (-not [string]::IsNullOrWhiteSpace($fromFile)) {
        $env:COMICVINE_API_KEY = $fromFile.Trim()
        $Script:ComicVineKeySource = ".ENV"
        return
    }
    $Script:ComicVineKeySource = $null
}

function Test-ComicVineApiKeyConfigured {
    $key = $env:COMICVINE_API_KEY
    if ([string]::IsNullOrWhiteSpace($key)) {
        throw "COMICVINE_API_KEY is missing. Set it in the environment or in apps/api/.env"
    }
    if ($key.Trim().Equals("your_key_here", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'COMICVINE_API_KEY is still the placeholder "your_key_here". Use a real ComicVine API key.'
    }
    if ($key.Trim().Length -lt 20) {
        throw "COMICVINE_API_KEY is too short (minimum 20 characters)."
    }
    if ([string]::IsNullOrWhiteSpace($Script:ComicVineKeySource)) {
        throw "COMICVINE_API_KEY source could not be determined."
    }
}

function Write-ComicVineKeyStatus {
    Write-Host "COMICVINE_API_KEY loaded: YES"
    Write-Host "COMICVINE_API_KEY source: $($Script:ComicVineKeySource)"
    Write-Log "COMICVINE_API_KEY loaded: YES"
    Write-Log "COMICVINE_API_KEY source: $($Script:ComicVineKeySource)"
}

function Test-ComicVineApiAccess {
    Write-Log "ComicVine API validation (Spawn --limit 1 --dry-run)"
    $validationArgs = @(
        "scripts\p97_import_comicvine_catalog.py",
        "--series-name", "Spawn",
        "--limit", "1",
        "--dry-run",
        "--sleep-seconds", "1"
    )
    Write-Log ("  > python " + ($validationArgs -join " "))
    $output = & python @validationArgs 2>&1 | ForEach-Object { $_.ToString() }
    foreach ($line in $output) {
        Write-Host $line
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    }
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    $blob = ($output -join "`n")
    if ($blob -match "401" -or $blob -match "(?i)Unauthorized") {
        throw "ComicVine API returned HTTP 401 Unauthorized. Fix COMICVINE_API_KEY and retry."
    }
    if ($exitCode -ne 0) {
        throw "ComicVine validation failed (exit $exitCode). See log for details."
    }
    Write-Log "ComicVine API validation passed."
}

function Test-SafetyChecks {
    Write-Log "Safety checks"
    if ((Get-Location).Path -ne $ApiRoot) {
        throw "Current directory must be apps/api. Expected: $ApiRoot Actual: $((Get-Location).Path)"
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "python is not on PATH."
    }
    Write-Log "  python: $($python.Source)"

    $requiredScripts = @(
        "scripts\p97_import_comicvine_catalog.py",
        "scripts\p97_harvest_catalog_covers.py",
        "scripts\p97_generate_catalog_fingerprints.py",
        "scripts\p97_generate_catalog_ocr.py"
    )
    foreach ($rel in $requiredScripts) {
        $full = Join-Path $ApiRoot $rel
        if (-not (Test-Path -LiteralPath $full)) {
            throw "Missing required script: $rel"
        }
    }

    if ($env:DATABASE_URL -notmatch "localhost:5433" -or $env:DATABASE_URL -notmatch "comic_os") {
        throw "DATABASE_URL must target localhost:5433/comic_os. Got: $($env:DATABASE_URL)"
    }
    if (-not (Test-Path -LiteralPath $env:TESSERACT_CMD)) {
        throw "TESSERACT_CMD not found on disk: $($env:TESSERACT_CMD)"
    }
    Write-Log "  All safety checks passed."
}

# --- bootstrap ---
Write-Host ""
Write-Host "DATABASE_URL=$($env:DATABASE_URL)"
Write-Host "TESSERACT_CMD=$($env:TESSERACT_CMD)"
Write-Host ""

if (-not (Test-Path -LiteralPath $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Set-Location -LiteralPath $ApiRoot
Write-Log "Overnight catalog run starting (WhatIf=$WhatIf)"
Write-Log "Log file: $LogFile"
Write-Log "DATABASE_URL=$($env:DATABASE_URL)"
Write-Log "TESSERACT_CMD=$($env:TESSERACT_CMD)"

try {
    Test-SafetyChecks
    Initialize-ComicVineApiKey
    Test-ComicVineApiKeyConfigured
    Write-ComicVineKeyStatus
    if (-not $WhatIf) {
        Test-ComicVineApiAccess
    } else {
        Write-Log "  (WhatIf: skipping ComicVine API validation call)"
    }
} catch {
    Write-Log $_.Exception.Message -Level "ERROR"
    Write-Error $_.Exception.Message
    exit 1
}

$importFailures = 0
foreach ($series in $SeriesTargets) {
    $args = @(
        "scripts\p97_import_comicvine_catalog.py",
        "--series-name", $series,
        "--limit", "250",
        "--import-issues",
        "--sleep-seconds", "1"
    )
    $code = Invoke-LoggedCommand -Label "import series: $series" -Command (@("python") + $args)
    if ($code -ne 0) {
        $importFailures += 1
    }
}

Write-Log "Series import phase complete (failures=$importFailures)"

$postSteps = @(
    @{
        Label = "harvest covers"
        Command = @(
            "python", "scripts\p97_harvest_catalog_covers.py",
            "--limit", "50000", "--resume", "--batch-size", "50", "--sleep-seconds", "0.25"
        )
    },
    @{
        Label = "generate fingerprints"
        Command = @(
            "python", "scripts\p97_generate_catalog_fingerprints.py",
            "--limit", "50000", "--batch-size", "200"
        )
    },
    @{
        Label = "generate OCR"
        Command = @(
            "python", "scripts\p97_generate_catalog_ocr.py",
            "--limit", "50000", "--batch-size", "200"
        )
    }
)

foreach ($step in $postSteps) {
    $code = Invoke-LoggedCommand -Label $step.Label -Command $step.Command
    if ($code -ne 0 -and -not $WhatIf) {
        Write-Log "Post-import step failed but continuing: $($step.Label)" -Level "WARN"
    }
}

$EndTime = Get-Date
$runtime = $EndTime - $StartTime

Write-Log "========== SUMMARY =========="
Write-Log "start_time=$($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Log "end_time=$($EndTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Log "total_runtime=$($runtime.ToString())"
Write-Log "log_file=$LogFile"
Write-Log "series_import_failures=$importFailures"

Write-Host ""
Write-Host "========== SUMMARY =========="
Write-Host "start_time=$($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "end_time=$($EndTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "total_runtime=$($runtime.ToString())"
Write-Host "log_file=$LogFile"
Write-Host ""

$healthScript = Join-Path $ApiRoot "scripts\p97_catalog_health.py"
if (Test-Path -LiteralPath $healthScript) {
    Write-Log "Running catalog health report"
    if ($WhatIf) {
        Write-Log "  (WhatIf: would run python scripts\p97_catalog_health.py)"
    } else {
        Write-Log "START catalog health"
        & python $healthScript 2>&1 | ForEach-Object {
            Write-Host $_
            Add-Content -Path $LogFile -Value $_ -Encoding utf8
        }
        Write-Log "DONE catalog health"
    }
} else {
    $msg = "scripts/p97_catalog_health.py not found - request a catalog health summary from Cursor."
    Write-Log $msg -Level "WARN"
    Write-Host $msg
}

if ($WhatIf) {
    Write-Log "WhatIf complete - no imports or post-processing were executed."
}

exit 0
