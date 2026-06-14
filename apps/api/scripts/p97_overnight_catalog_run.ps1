#Requires -Version 5.1
<#
.SYNOPSIS
  P97 continuous overnight catalog acquisition (series queue, then publisher mode + post-processing).
.PARAMETER WhatIf
  Print configuration and planned commands; run safety checks only.
#>
param(
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

# --- continuous mode configuration ---
$TargetRuntimeHours = 12
$MinimumRuntimeHours = 9
$SeriesPhaseMaxHours = 3
$PerSeriesLimit = 1000
$SeriesCooldownSeconds = 60
$PostProcessingEveryHours = 3
$ThrottleRetryMax = 6
$ThrottleSleepSeconds = 900

$env:DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"

$ApiRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $ApiRoot ".env"
$LogDir = Join-Path $ApiRoot "data\p97"
$LogFile = Join-Path $LogDir "overnight_catalog_run.log"
$ProgressFile = Join-Path $LogDir "overnight_series_progress.json"
$SummaryFile = Join-Path $LogDir "overnight_catalog_run_summary.json"

$Script:ComicVineKeySource = $null
$Script:RunStats = @{
    start_time = $null
    end_time = $null
    series_attempted = 0
    series_successful = 0
    series_failed = 0
    throttle_events = 0
    post_processing_runs = 0
    issues_created_total = 0
    cover_images_created_total = 0
    last_series = ""
    last_publisher = ""
    last_offset = 0
    queue_passes = 0
    publisher_passes = 0
    publishers_attempted = 0
    publishers_successful = 0
    publishers_failed = 0
    acquisition_phase = "series"
}

$SeriesTargets = @(
    # DC
    "Batman", "Detective Comics", "Superman", "Action Comics", "Wonder Woman", "The Flash", "Green Lantern",
    "Justice League", "Aquaman", "Green Arrow", "Nightwing", "Robin", "Catwoman", "Batgirl", "Harley Quinn",
    "Suicide Squad", "Joker", "Teen Titans", "New Teen Titans", "Legion of Super-Heroes", "Swamp Thing",
    "Sandman", "Watchmen", "Constantine", "Hellblazer", "Birds of Prey", "Supergirl", "Shazam",
    "Justice Society of America", "Hawkman", "Firestorm", "Booster Gold", "Blue Beetle", "Zatanna",
    "Young Justice", "Static", "Black Lightning", "Plastic Man", "Animal Man", "Doom Patrol",
    # Marvel
    "Amazing Spider-Man", "Spectacular Spider-Man", "Web of Spider-Man", "Spider-Man", "Ultimate Spider-Man",
    "Miles Morales", "Spider-Gwen", "Venom", "Carnage", "Avengers", "New Avengers", "Uncanny X-Men", "X-Men",
    "Astonishing X-Men", "Wolverine", "X-Force", "X-Factor", "New Mutants", "Excalibur", "Deadpool",
    "Fantastic Four", "Daredevil", "Punisher", "Captain America", "Iron Man", "Thor", "Incredible Hulk", "Hulk",
    "Doctor Strange", "Moon Knight", "Ghost Rider", "Silver Surfer", "Black Panther", "Captain Marvel",
    "Ms. Marvel", "Guardians of the Galaxy", "Nova", "She-Hulk", "Immortal Hulk", "Defenders", "Champions",
    "Eternals", "Shang-Chi", "Iron Fist", "Luke Cage", "Runaways", "Young Avengers", "Thunderbolts",
    "Alpha Flight", "Man-Thing", "Howard the Duck",
    # Image / Skybound
    "Spawn", "Invincible", "Savage Dragon", "The Walking Dead", "Saga", "Radiant Black", "Department of Truth",
    "Something is Killing the Children", "Monstress", "East of West", "Deadly Class", "Chew", "Fire Power",
    "Geiger", "Rook", "Void Rivals", "Witchblade", "Cyberforce", "Stormwatch", "The Authority", "WildC.A.T.s",
    "Gen13", "Supreme", "King Spawn", "Paper Girls", "Outcast", "Locke & Key", "BRZRKR",
    # Dark Horse / IDW / Boom / Dynamite / Valiant / others
    "Hellboy", "B.P.R.D.", "The Goon", "Usagi Yojimbo", "Grendel", "Sin City", "Umbrella Academy",
    "Teenage Mutant Ninja Turtles", "Transformers", "G.I. Joe", "Sonic the Hedgehog", "Power Rangers",
    "Buffy the Vampire Slayer", "Angel", "Firefly", "Star Wars", "Alien", "Predator", "Conan", "Red Sonja",
    "The Boys", "Invader Zim", "Bloodshot", "X-O Manowar", "Harbinger", "Ninjak", "Shadowman", "Rai", "Solar",
    "Turok", "Star Trek", "Doctor Who", "Rocketeer", "Baltimore", "Black Hammer", "Lazarus", "Critical Role"
)

$PublisherTargets = @(
    "Marvel",
    "DC Comics",
    "Image",
    "Dark Horse",
    "Boom",
    "IDW",
    "Dynamite",
    "Valiant",
    "Skybound",
    "Titan",
    "Oni",
    "Aftershock",
    "AWA",
    "Mad Cave",
    "DSTLRY"
)

function Enter-PublisherAcquisitionPhase {
    param([Parameter(Mandatory = $true)][string]$Reason)
    if ($Progress.series_exhausted) {
        return
    }
    $Progress.series_exhausted = $true
    $Progress.acquisition_phase = "publisher"
    $Script:RunStats.acquisition_phase = "publisher"
    Save-ProgressDocument -Progress $Progress
    Write-Log $Reason
}

function Test-SeriesPhaseActive {
    param([Parameter(Mandatory = $true)][datetime]$RunStartTime)
    if ($Progress.series_exhausted) {
        return $false
    }
    return (Get-ElapsedHours -Since $RunStartTime) -lt $SeriesPhaseMaxHours
}

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

function Get-ElapsedHours {
    param([Parameter(Mandatory = $true)][datetime]$Since)
    return ((Get-Date) - $Since).TotalHours
}

function New-ProgressDocument {
    $doc = [ordered]@{
        version = 2
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
        acquisition_phase = "series"
        series_exhausted = $false
        queue_pass = 0
        publisher_queue_pass = 0
        series = @{}
        publishers = @{}
    }
    foreach ($name in $SeriesTargets) {
        $doc.series[$name] = New-SeriesProgressEntry -SeriesName $name
    }
    foreach ($name in $PublisherTargets) {
        $doc.publishers[$name] = New-PublisherProgressEntry -PublisherName $name
    }
    return $doc
}

function New-SeriesProgressEntry {
    param([Parameter(Mandatory = $true)][string]$SeriesName)
    return [ordered]@{
        series_name = $SeriesName
        last_offset = 0
        last_run_at = $null
        success_count = 0
        failure_count = 0
        last_exit_code = 0
    }
}

function New-PublisherProgressEntry {
    param([Parameter(Mandatory = $true)][string]$PublisherName)
    return [ordered]@{
        publisher_name = $PublisherName
        last_offset = 0
        last_run_at = $null
        success_count = 0
        failure_count = 0
        last_exit_code = 0
    }
}

function Load-ProgressDocument {
    if (-not (Test-Path -LiteralPath $ProgressFile)) {
        return New-ProgressDocument
    }
    try {
        $raw = Get-Content -LiteralPath $ProgressFile -Raw -Encoding utf8 | ConvertFrom-Json
        $doc = New-ProgressDocument
        if ($null -ne $raw.queue_pass) { $doc.queue_pass = [int]$raw.queue_pass }
        if ($null -ne $raw.publisher_queue_pass) { $doc.publisher_queue_pass = [int]$raw.publisher_queue_pass }
        if ($null -ne $raw.acquisition_phase) { $doc.acquisition_phase = [string]$raw.acquisition_phase }
        if ($null -ne $raw.series_exhausted) { $doc.series_exhausted = [bool]$raw.series_exhausted }
        foreach ($name in $SeriesTargets) {
            if ($raw.series.PSObject.Properties.Name -contains $name) {
                $entry = $raw.series.$name
                $doc.series[$name].last_offset = [int]$entry.last_offset
                $doc.series[$name].last_run_at = $entry.last_run_at
                $doc.series[$name].success_count = [int]$entry.success_count
                $doc.series[$name].failure_count = [int]$entry.failure_count
                $doc.series[$name].last_exit_code = [int]$entry.last_exit_code
            }
        }
        if ($null -ne $raw.publishers) {
            foreach ($name in $PublisherTargets) {
                if ($raw.publishers.PSObject.Properties.Name -contains $name) {
                    $entry = $raw.publishers.$name
                    $doc.publishers[$name].last_offset = [int]$entry.last_offset
                    $doc.publishers[$name].last_run_at = $entry.last_run_at
                    $doc.publishers[$name].success_count = [int]$entry.success_count
                    $doc.publishers[$name].failure_count = [int]$entry.failure_count
                    $doc.publishers[$name].last_exit_code = [int]$entry.last_exit_code
                }
            }
        } else {
            foreach ($name in $PublisherTargets) {
                $doc.publishers[$name] = New-PublisherProgressEntry -PublisherName $name
            }
        }
        return $doc
    } catch {
        Write-Log "Progress file corrupt; starting fresh: $($_.Exception.Message)" -Level "WARN"
        return New-ProgressDocument
    }
}

function Save-ProgressDocument {
    param([Parameter(Mandatory = $true)]$Progress)
    $Progress.updated_at = (Get-Date).ToUniversalTime().ToString("o")
    $Progress | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ProgressFile -Encoding utf8
}

function Test-OutputThrottle420 {
    param([string]$OutputBlob)
    return ($OutputBlob -match "\b420\b") -or ($OutputBlob -match "(?i)too many requests") -or ($OutputBlob -match "(?i)throttle")
}

function Parse-ImportMetrics {
    param([string[]]$Lines)
    $metrics = @{
        final_offset = $null
        total_candidates_seen = 0
        issues_created = 0
        cover_images_created = 0
    }
    foreach ($line in $Lines) {
        if ($line -match "^final_offset=(\d+)") { $metrics.final_offset = [int]$Matches[1] }
        if ($line -match "^total_candidates_seen=(\d+)") { $metrics.total_candidates_seen = [int]$Matches[1] }
        if ($line -match "^issues_created=(\d+)") { $metrics.issues_created = [int]$Matches[1] }
        if ($line -match "^cover_images_created=(\d+)") { $metrics.cover_images_created = [int]$Matches[1] }
    }
    return $metrics
}

function Invoke-PostProcessing {
    param([Parameter(Mandatory = $true)][string]$Reason)
    Write-Log "Post-processing checkpoint: $Reason"
    $steps = @(
        @{
            Label = "harvest covers"
            Command = @("python", "scripts\p97_harvest_catalog_covers.py", "--limit", "50000", "--resume", "--batch-size", "50", "--sleep-seconds", "0.25")
        },
        @{
            Label = "generate fingerprints"
            Command = @("python", "scripts\p97_generate_catalog_fingerprints.py", "--limit", "50000", "--batch-size", "200")
        },
        @{
            Label = "generate OCR"
            Command = @("python", "scripts\p97_generate_catalog_ocr.py", "--limit", "50000", "--batch-size", "200")
        }
    )
    foreach ($step in $steps) {
        Write-Log "START $($step.Label)"
        Write-Log ("  > " + ($step.Command -join " "))
        if ($WhatIf) {
            Write-Log "  (WhatIf: skipped)"
            continue
        }
        & $step.Command[0] @($step.Command[1..($step.Command.Length - 1)])
        $code = $LASTEXITCODE
        if ($null -eq $code) { $code = 0 }
        if ($code -ne 0) {
            Write-Log "Post-processing step failed: $($step.Label) (exit $code)" -Level "WARN"
        } else {
            Write-Log "DONE $($step.Label)"
        }
    }
    if (-not $WhatIf) {
        $Script:RunStats.post_processing_runs++
    }
}

function Invoke-ImportWithThrottle {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$ImportScript,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $throttleAttempts = 0
    $importResult = $null
    do {
        $importResult = & $ImportScript
        if ($importResult.throttled -and $throttleAttempts -lt $ThrottleRetryMax) {
            $throttleAttempts++
            $Script:RunStats.throttle_events++
            Write-Log "HTTP 420/throttle for $Label; sleeping ${ThrottleSleepSeconds}s (retry $throttleAttempts/$ThrottleRetryMax)" -Level "WARN"
            if (-not $WhatIf) { Start-Sleep -Seconds $ThrottleSleepSeconds }
        } else {
            break
        }
    } while ($true)
    return @{
        result = $importResult
        throttle_attempts = $throttleAttempts
    }
}

function Invoke-ComicVineImport {
    param(
        [Parameter(Mandatory = $true)][string[]]$ImportArgs,
        [Parameter(Mandatory = $true)][string]$Label
    )
    Write-Log "START $Label"
    Write-Log ("  > python " + ($ImportArgs -join " "))
    if ($WhatIf) {
        Write-Log "  (WhatIf: skipped)"
        return @{
            exit_code = 0
            output = @()
            throttled = $false
            metrics = @{ final_offset = 0; total_candidates_seen = 0; issues_created = 0; cover_images_created = 0 }
        }
    }
    $output = & python @ImportArgs 2>&1 | ForEach-Object { $_.ToString() }
    foreach ($line in $output) {
        Write-Host $line
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    }
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    $blob = $output -join "`n"
    return @{
        exit_code = $exitCode
        output = $output
        throttled = (Test-OutputThrottle420 -OutputBlob $blob)
        metrics = (Parse-ImportMetrics -Lines $output)
    }
}

function Invoke-SeriesImport {
    param(
        [Parameter(Mandatory = $true)][string]$SeriesName,
        [Parameter(Mandatory = $true)][int]$Offset
    )
    $importArgs = @(
        "scripts\p97_import_comicvine_catalog.py",
        "--series-name", $SeriesName,
        "--limit", "$PerSeriesLimit",
        "--offset", "$Offset",
        "--import-issues",
        "--sleep-seconds", "1",
        "--resume"
    )
    return Invoke-ComicVineImport -ImportArgs $importArgs -Label "import series: $SeriesName (offset=$Offset)"
}

function Invoke-PublisherImport {
    param(
        [Parameter(Mandatory = $true)][string]$PublisherName,
        [Parameter(Mandatory = $true)][int]$Offset
    )
    # Publisher volumes API filter + strict client match; English/US gate remains default (no --allow-international-editions).
    $importArgs = @(
        "scripts\p97_import_comicvine_catalog.py",
        "--publisher", $PublisherName,
        "--strict-publisher",
        "--limit", "$PerSeriesLimit",
        "--offset", "$Offset",
        "--import-issues",
        "--sleep-seconds", "1",
        "--resume"
    )
    return Invoke-ComicVineImport -ImportArgs $importArgs -Label "import publisher: $PublisherName (offset=$Offset)"
}

function Update-ProgressFromImport {
    param(
        $Entry,
        $ImportResult,
        [int]$ThrottleAttempts,
        [int]$OffsetBefore,
        [scriptblock]$OnSuccess,
        [scriptblock]$OnFailure
    )
    $Entry.last_run_at = (Get-Date).ToUniversalTime().ToString("o")
    $Entry.last_exit_code = [int]$ImportResult.exit_code
    $maxThrottle = ($ImportResult.throttled -and $ThrottleAttempts -ge $ThrottleRetryMax)
    if ($ImportResult.exit_code -eq 0 -and -not $maxThrottle) {
        $Entry.success_count++
        if ($null -ne $ImportResult.metrics.final_offset) {
            $Entry.last_offset = [int]$ImportResult.metrics.final_offset
        }
        & $OnSuccess
    } else {
        $Entry.failure_count++
        if ($maxThrottle) {
            Write-Log "Max throttle retries reached; leaving last_offset=$OffsetBefore unchanged" -Level "WARN"
        }
        & $OnFailure
    }
    $Script:RunStats.issues_created_total += [int]$ImportResult.metrics.issues_created
    $Script:RunStats.cover_images_created_total += [int]$ImportResult.metrics.cover_images_created
}

function Write-SummaryJson {
    param(
        [Parameter(Mandatory = $true)][datetime]$StartTime,
        [Parameter(Mandatory = $true)][datetime]$EndTime,
        [switch]$Interrupted
    )
    $runtimeHours = (($EndTime - $StartTime).TotalHours)
    $seriesExhaustedFlag = $false
    if ($null -ne $Progress -and $Progress.series_exhausted) {
        $seriesExhaustedFlag = [bool]$Progress.series_exhausted
    }
    $summary = [ordered]@{
        start_time = $StartTime.ToString("yyyy-MM-dd HH:mm:ss")
        end_time = $EndTime.ToString("yyyy-MM-dd HH:mm:ss")
        runtime_hours = [math]::Round($runtimeHours, 4)
        target_runtime_hours = $TargetRuntimeHours
        series_phase_max_hours = $SeriesPhaseMaxHours
        minimum_runtime_hours = $MinimumRuntimeHours
        series_attempted = $Script:RunStats.series_attempted
        series_successful = $Script:RunStats.series_successful
        series_failed = $Script:RunStats.series_failed
        throttle_events = $Script:RunStats.throttle_events
        post_processing_runs = $Script:RunStats.post_processing_runs
        issues_created_total = $Script:RunStats.issues_created_total
        cover_images_created_total = $Script:RunStats.cover_images_created_total
        last_series = $Script:RunStats.last_series
        last_publisher = $Script:RunStats.last_publisher
        last_offset = $Script:RunStats.last_offset
        queue_passes = $Script:RunStats.queue_passes
        publisher_passes = $Script:RunStats.publisher_passes
        publishers_attempted = $Script:RunStats.publishers_attempted
        publishers_successful = $Script:RunStats.publishers_successful
        publishers_failed = $Script:RunStats.publishers_failed
        acquisition_phase = $Script:RunStats.acquisition_phase
        series_exhausted = $seriesExhaustedFlag
        interrupted = [bool]$Interrupted
        log_file = $LogFile
        progress_file = $ProgressFile
        per_series_limit = $PerSeriesLimit
        series_queue_count = $SeriesTargets.Count
        publisher_queue_count = $PublisherTargets.Count
    }
    $summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $SummaryFile -Encoding utf8
}

function Show-WhatIfPlan {
    $publisherPhaseHours = [math]::Max(0, $TargetRuntimeHours - $SeriesPhaseMaxHours)
    Write-Host "TargetRuntimeHours=$TargetRuntimeHours"
    Write-Host "SeriesPhaseMaxHours=$SeriesPhaseMaxHours"
    Write-Host "PublisherPhase expected runtime hours=$publisherPhaseHours"
    Write-Host "MinimumRuntimeHours=$MinimumRuntimeHours"
    Write-Host "PerSeriesLimit=$PerSeriesLimit"
    Write-Host "Series count=$($SeriesTargets.Count)"
    Write-Host "Publisher count=$($PublisherTargets.Count)"
    Write-Host "PostProcessingEveryHours=$PostProcessingEveryHours"
    Write-Host "Progress file=$ProgressFile"
    Write-Host "Log file=$LogFile"
    Write-Host "Summary file=$SummaryFile"
    Write-Host "First 20 planned series:"
    $SeriesTargets | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    Write-Host "Example series import command:"
    Write-Host "  python scripts\p97_import_comicvine_catalog.py --series-name `"$($SeriesTargets[0])`" --limit $PerSeriesLimit --offset 0 --import-issues --sleep-seconds 1 --resume"
    Write-Host "Example publisher import command (after series exhausted):"
    Write-Host "  python scripts\p97_import_comicvine_catalog.py --publisher `"$($PublisherTargets[0])`" --strict-publisher --limit $PerSeriesLimit --offset 0 --import-issues --sleep-seconds 1 --resume"
    Write-Host "Phases: priority series for up to $SeriesPhaseMaxHours h (or zero-candidate pass), then publisher acquisition for remaining target runtime (up to $TargetRuntimeHours h total)."
}

function Get-DotEnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name
    )
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding utf8) {
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        if ($trimmed -match "^\s*$([regex]::Escape($Name))\s*=\s*(.*)$") {
            $raw = $Matches[1].Trim()
            if ($raw.Length -ge 2 -and (($raw.StartsWith('"') -and $raw.EndsWith('"')) -or ($raw.StartsWith("'") -and $raw.EndsWith("'")))) {
                return $raw.Substring(1, $raw.Length - 2)
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
    if ([string]::IsNullOrWhiteSpace($key)) { throw "COMICVINE_API_KEY is missing. Set it in the environment or in apps/api/.env" }
    if ($key.Trim().Equals("your_key_here", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'COMICVINE_API_KEY is still the placeholder "your_key_here". Use a real ComicVine API key.'
    }
    if ($key.Trim().Length -lt 20) { throw "COMICVINE_API_KEY is too short (minimum 20 characters)." }
    if ([string]::IsNullOrWhiteSpace($Script:ComicVineKeySource)) { throw "COMICVINE_API_KEY source could not be determined." }
}

function Write-ComicVineKeyStatus {
    Write-Host "COMICVINE_API_KEY loaded: YES"
    Write-Host "COMICVINE_API_KEY source: $($Script:ComicVineKeySource)"
    Write-Log "COMICVINE_API_KEY loaded: YES"
    Write-Log "COMICVINE_API_KEY source: $($Script:ComicVineKeySource)"
}

function Test-ComicVineApiAccess {
    Write-Log "ComicVine API validation (Spawn --limit 1 --dry-run)"
    $validationArgs = @("scripts\p97_import_comicvine_catalog.py", "--series-name", "Spawn", "--limit", "1", "--dry-run", "--sleep-seconds", "1")
    Write-Log ("  > python " + ($validationArgs -join " "))
    $output = & python @validationArgs 2>&1 | ForEach-Object { $_.ToString() }
    foreach ($line in $output) {
        Write-Host $line
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    }
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }
    $blob = $output -join "`n"
    if ($blob -match "401" -or $blob -match "(?i)Unauthorized") {
        throw "ComicVine API returned HTTP 401 Unauthorized. Fix COMICVINE_API_KEY and retry."
    }
    if ($exitCode -ne 0) { throw "ComicVine validation failed (exit $exitCode). See log for details." }
    Write-Log "ComicVine API validation passed."
}

function Test-SafetyChecks {
    Write-Log "Safety checks"
    if ((Get-Location).Path -ne $ApiRoot) {
        throw "Current directory must be apps/api. Expected: $ApiRoot Actual: $((Get-Location).Path)"
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "python is not on PATH." }
    Write-Log "  python: $($python.Source)"
    foreach ($rel in @(
            "scripts\p97_import_comicvine_catalog.py",
            "scripts\p97_harvest_catalog_covers.py",
            "scripts\p97_generate_catalog_fingerprints.py",
            "scripts\p97_generate_catalog_ocr.py"
        )) {
        if (-not (Test-Path -LiteralPath (Join-Path $ApiRoot $rel))) {
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
$StartTime = Get-Date
$Script:RunStats.start_time = $StartTime
$endAt = $StartTime.AddHours($TargetRuntimeHours)
$lastPostProcessingAt = $StartTime
$Progress = $null
$interrupted = $false

try {
    Write-Host ""
    Write-Host "DATABASE_URL=$($env:DATABASE_URL)"
    Write-Host "TESSERACT_CMD=$($env:TESSERACT_CMD)"
    Write-Host ""

    if (-not (Test-Path -LiteralPath $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }

    Set-Location -LiteralPath $ApiRoot
    Write-Log "Continuous overnight catalog run starting (WhatIf=$WhatIf)"
    Write-Log "TargetRuntimeHours=$TargetRuntimeHours SeriesPhaseMaxHours=$SeriesPhaseMaxHours MinimumRuntimeHours=$MinimumRuntimeHours PerSeriesLimit=$PerSeriesLimit"
    Write-Log "Log file: $LogFile"
    Write-Log "Progress file: $ProgressFile"

    if ($WhatIf) { Show-WhatIfPlan }

    Test-SafetyChecks
    Initialize-ComicVineApiKey
    Test-ComicVineApiKeyConfigured
    Write-ComicVineKeyStatus
    if (-not $WhatIf) {
        Test-ComicVineApiAccess
    } else {
        Write-Log "(WhatIf: skipping ComicVine API validation call)"
    }

    $Progress = Load-ProgressDocument
    $Script:RunStats.acquisition_phase = [string]$Progress.acquisition_phase
    if ($Progress.series_exhausted) {
        $Script:RunStats.acquisition_phase = "publisher"
    }

    if ($WhatIf) {
        Write-Log "WhatIf: skipping continuous acquisition loop (see plan above)"
    } else {
        while ((Get-Date) -lt $endAt) {
            if ((Get-ElapsedHours -Since $lastPostProcessingAt) -ge $PostProcessingEveryHours) {
                Invoke-PostProcessing -Reason "scheduled every $PostProcessingEveryHours h"
                $lastPostProcessingAt = Get-Date
                if ((Get-Date) -ge $endAt) { break }
            }

            if ((Get-ElapsedHours -Since $StartTime) -ge $SeriesPhaseMaxHours) {
                Enter-PublisherAcquisitionPhase -Reason "Series phase max hours ($SeriesPhaseMaxHours) reached; switching to publisher acquisition mode"
            }

            if (Test-SeriesPhaseActive -RunStartTime $StartTime) {
                $Script:RunStats.acquisition_phase = "series"
                $Script:RunStats.queue_passes++
                $passCandidatesTotal = 0
                Write-Log "Series queue pass $($Script:RunStats.queue_passes) (elapsed h=$([math]::Round((Get-ElapsedHours -Since $StartTime), 2)) / max $SeriesPhaseMaxHours h)"

                foreach ($series in $SeriesTargets) {
                    if ((Get-Date) -ge $endAt) { break }
                    if ((Get-ElapsedHours -Since $StartTime) -ge $SeriesPhaseMaxHours) {
                        Enter-PublisherAcquisitionPhase -Reason "Series phase max hours ($SeriesPhaseMaxHours) reached mid-pass; switching to publisher acquisition mode"
                        break
                    }

                    $entry = $Progress.series[$series]
                    $offset = [int]$entry.last_offset
                    $Script:RunStats.series_attempted++
                    $Script:RunStats.last_series = $series
                    $Script:RunStats.last_publisher = ""
                    $Script:RunStats.last_offset = $offset

                    $wrapped = Invoke-ImportWithThrottle -Label "series=$series" -ImportScript {
                        Invoke-SeriesImport -SeriesName $series -Offset $offset
                    }
                    $importResult = $wrapped.result
                    $passCandidatesTotal += [int]$importResult.metrics.total_candidates_seen

                    Update-ProgressFromImport -Entry $entry -ImportResult $importResult -ThrottleAttempts $wrapped.throttle_attempts -OffsetBefore $offset `
                        -OnSuccess { $Script:RunStats.series_successful++; if ($null -ne $importResult.metrics.final_offset) { $Script:RunStats.last_offset = $entry.last_offset } } `
                        -OnFailure { $Script:RunStats.series_failed++ }

                    Save-ProgressDocument -Progress $Progress
                    if ($SeriesCooldownSeconds -gt 0) { Start-Sleep -Seconds $SeriesCooldownSeconds }
                }

                $Progress.queue_pass = $Script:RunStats.queue_passes
                if ($passCandidatesTotal -eq 0) {
                    Enter-PublisherAcquisitionPhase -Reason "Priority series queue exhausted (zero candidates in pass); switching to publisher acquisition mode"
                } else {
                    Write-Log "Series pass saw $passCandidatesTotal candidates; continuing series phase while under $SeriesPhaseMaxHours h"
                }
            }

            if ($Progress.series_exhausted -and (Get-Date) -lt $endAt) {
                $Script:RunStats.acquisition_phase = "publisher"
                $Script:RunStats.publisher_passes++
                Write-Log "Publisher queue pass $($Script:RunStats.publisher_passes) (elapsed h=$([math]::Round((Get-ElapsedHours -Since $StartTime), 2)))"

                foreach ($publisher in $PublisherTargets) {
                    if ((Get-Date) -ge $endAt) { break }

                    $entry = $Progress.publishers[$publisher]
                    $offset = [int]$entry.last_offset
                    $Script:RunStats.publishers_attempted++
                    $Script:RunStats.last_publisher = $publisher
                    $Script:RunStats.last_series = ""
                    $Script:RunStats.last_offset = $offset

                    $wrapped = Invoke-ImportWithThrottle -Label "publisher=$publisher" -ImportScript {
                        Invoke-PublisherImport -PublisherName $publisher -Offset $offset
                    }
                    $importResult = $wrapped.result

                    Update-ProgressFromImport -Entry $entry -ImportResult $importResult -ThrottleAttempts $wrapped.throttle_attempts -OffsetBefore $offset `
                        -OnSuccess { $Script:RunStats.publishers_successful++; if ($null -ne $importResult.metrics.final_offset) { $Script:RunStats.last_offset = $entry.last_offset } } `
                        -OnFailure { $Script:RunStats.publishers_failed++ }

                    Save-ProgressDocument -Progress $Progress
                    if ($SeriesCooldownSeconds -gt 0) { Start-Sleep -Seconds $SeriesCooldownSeconds }
                }

                $Progress.publisher_queue_pass = $Script:RunStats.publisher_passes
                Save-ProgressDocument -Progress $Progress
                Write-Log "Publisher queue pass complete; continuing publisher mode until target runtime"
            }
        }
    }

    if (-not $WhatIf) {
        Invoke-PostProcessing -Reason "final checkpoint at target runtime"
        $lastPostProcessingAt = Get-Date
    }

} catch {
    Write-Log $_.Exception.Message -Level "ERROR"
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($null -ne $Progress) {
        Save-ProgressDocument -Progress $Progress
    }
    $EndTime = Get-Date
    $Script:RunStats.end_time = $EndTime
    Write-SummaryJson -StartTime $StartTime -EndTime $EndTime -Interrupted:$interrupted

    Write-Log "========== SUMMARY =========="
    Write-Log "start_time=$($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    Write-Log "end_time=$($EndTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    Write-Log "runtime_hours=$([math]::Round((Get-ElapsedHours -Since $StartTime), 4))"
    Write-Log "summary_file=$SummaryFile"
    Write-Log "progress_file=$ProgressFile"

    Write-Host ""
    Write-Host "========== SUMMARY =========="
    Write-Host "runtime_hours=$([math]::Round((Get-ElapsedHours -Since $StartTime), 4))"
    Write-Host "summary_file=$SummaryFile"
    Write-Host "progress_file=$ProgressFile"

    $healthScript = Join-Path $ApiRoot "scripts\p97_catalog_health.py"
    if (Test-Path -LiteralPath $healthScript) {
        if ($WhatIf) {
            Write-Log "(WhatIf: would run p97_catalog_health.py)"
        } else {
            Write-Log "Running catalog health report"
            & python $healthScript 2>&1 | ForEach-Object {
                Write-Host $_
                Add-Content -Path $LogFile -Value $_ -Encoding utf8
            }
        }
    }

    if ($WhatIf) {
        Write-Log "WhatIf complete - no imports or post-processing were executed."
    }
}

exit 0
