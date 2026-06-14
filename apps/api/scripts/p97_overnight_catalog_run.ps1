#Requires -Version 5.1
<#
.SYNOPSIS
  P97 continuous overnight catalog acquisition (series queue, then publisher mode + post-processing).
.PARAMETER Forever
  Run publisher acquisition continuously until Ctrl+C (import-only; no enrichment post-processing).
  Default: major-publisher sequential mode (Marvel -> DC -> Image -> Dark Horse -> IDW -> Boom).
.PARAMETER AllPublishers
  With -Forever, include minor publishers (AWA, Oni, etc.) before majors are complete and use
  one-chunk rotation across the full publisher list (legacy behavior).
.PARAMETER WhatIf
  Print configuration and planned commands; run safety checks only.
#>
param(
    [switch]$WhatIf,
    [switch]$TestImportHelper,
    [switch]$Forever,
    [switch]$AllPublishers
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
$ComicVineBaseSleepSeconds = 2
$ComicVineOvernightMinSleepSeconds = 1.5
$ComicVineForeverMinSleepSeconds = 10
$ComicVineMaxSleepSeconds = 10

$env:DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"

$ApiRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $ApiRoot ".env"
$LogDir = Join-Path $ApiRoot "data\p97"
$LogFile = Join-Path $LogDir "overnight_catalog_run.log"
$ProgressFile = Join-Path $LogDir "overnight_series_progress.json"
$SummaryFile = Join-Path $LogDir "overnight_catalog_run_summary.json"
$RateStateFile = Join-Path $LogDir "comicvine_rate_state.json"
$ForeverProgressFile = Join-Path $LogDir "forever_catalog_progress.json"
$PublisherPauseStateFile = Join-Path $LogDir "comicvine_publisher_pause_state.json"
$AcquisitionLockFile = Join-Path $LogDir "acquisition_runner.lock"
$ForeverHeartbeatSeconds = 60
$ForeverPublisherPauseMinutes = 60
$GoalIssuesPrimary = 150000
$GoalIssuesStretch = 200000

$PublisherChunkLimits = @{
    "Marvel"     = 100
    "DC Comics"  = 100
}

# Forever major sequential queue (minors deferred until all majors report exhausted)
$ForeverMajorPublishers = @(
    "Marvel",
    "DC Comics",
    "Image",
    "Dark Horse",
    "IDW",
    "Boom"
)

$ForeverMinorPublishers = @(
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

$Script:ForeverMajorOnly = $false
$Script:ForeverStopRequested = $false
$Script:ForeverHeartbeatTimer = $null
$Script:ForeverCancelHandlerRegistered = $false

$Script:ComicVineKeySource = $null
$Script:InSafetyBootstrap = $false
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

$PublisherTargets = @($ForeverMajorPublishers + $ForeverMinorPublishers)

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
        publisher_exhausted = $false
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
                    if ($null -ne $entry.publisher_exhausted) {
                        $doc.publishers[$name].publisher_exhausted = [bool]$entry.publisher_exhausted
                    }
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

function New-ComicVineRateState {
    return [ordered]@{
        current_sleep_seconds = [double]$ComicVineBaseSleepSeconds
        min_sleep_seconds = 1.0
        max_sleep_seconds = [double]$ComicVineMaxSleepSeconds
        last_420_at = $null
        throttle_count_last_hour = 0
        total_420_count = 0
        total_requests_observed = 0
        throttle_420_timestamps = @()
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
    }
}

function Load-ComicVineRateState {
    if (-not (Test-Path -LiteralPath $RateStateFile)) {
        return New-ComicVineRateState
    }
    try {
        $raw = Get-Content -LiteralPath $RateStateFile -Raw -Encoding utf8 | ConvertFrom-Json
        $state = New-ComicVineRateState
        if ($null -ne $raw.current_sleep_seconds) { $state.current_sleep_seconds = [double]$raw.current_sleep_seconds }
        if ($null -ne $raw.min_sleep_seconds) { $state.min_sleep_seconds = [double]$raw.min_sleep_seconds }
        if ($null -ne $raw.max_sleep_seconds) { $state.max_sleep_seconds = [double]$raw.max_sleep_seconds }
        $state.last_420_at = $raw.last_420_at
        if ($null -ne $raw.throttle_count_last_hour) { $state.throttle_count_last_hour = [int]$raw.throttle_count_last_hour }
        if ($null -ne $raw.total_420_count) { $state.total_420_count = [int]$raw.total_420_count }
        if ($null -ne $raw.total_requests_observed) { $state.total_requests_observed = [int]$raw.total_requests_observed }
        if ($null -ne $raw.throttle_420_timestamps) {
            $state.throttle_420_timestamps = @($raw.throttle_420_timestamps)
        }
        return $state
    } catch {
        Write-Log "Rate state corrupt; resetting: $($_.Exception.Message)" -Level "WARN"
        return New-ComicVineRateState
    }
}

function Get-ComicVineEffectiveMinSleepSeconds {
    if ($Forever) {
        return [double]$ComicVineForeverMinSleepSeconds
    }
    return [double]$ComicVineOvernightMinSleepSeconds
}

function Enforce-ComicVineForeverSleepFloor {
    param([Parameter(Mandatory = $true)]$State)
    if (-not $Forever) { return $false }
    $floor = [double]$ComicVineForeverMinSleepSeconds
    $changed = $false
    $beforeSleep = [double]$State.current_sleep_seconds
    if ($beforeSleep -lt $floor) {
        $State.current_sleep_seconds = $floor
        Write-Log "Forever sleep floor enforced: $beforeSleep -> $floor"
        $changed = $true
    }
    if ([double]$State.min_sleep_seconds -lt $floor) {
        $State.min_sleep_seconds = $floor
        $changed = $true
    }
    if ([double]$State.max_sleep_seconds -gt [double]$ComicVineMaxSleepSeconds) {
        $State.max_sleep_seconds = [double]$ComicVineMaxSleepSeconds
        $changed = $true
    }
    return $changed
}

function Get-MinutesSinceLast420 {
    param([Parameter(Mandatory = $true)]$State)
    if ($null -eq $State.last_420_at -or [string]::IsNullOrWhiteSpace([string]$State.last_420_at)) {
        return $null
    }
    try {
        $last420 = [datetimeoffset]::Parse([string]$State.last_420_at).UtcDateTime
        $minutes = ((Get-Date).ToUniversalTime() - $last420).TotalMinutes
        if ($minutes -lt 0) { $minutes = 0 }
        return [math]::Round($minutes, 1)
    } catch {
        return $null
    }
}

function Save-ComicVineRateState {
    param([Parameter(Mandatory = $true)]$State)
    $State.updated_at = (Get-Date).ToUniversalTime().ToString("o")
    $State | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $RateStateFile -Encoding utf8
}

function Format-ComicVineSleepSeconds {
    param([Parameter(Mandatory = $true)][double]$Seconds)
    $rounded = [math]::Round($Seconds, 2)
    if ($rounded -eq [math]::Floor($rounded)) {
        return ([int]$rounded).ToString()
    }
    return $rounded.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Update-ComicVineRateThrottleWindows {
    param([Parameter(Mandatory = $true)]$State)
    $now = Get-Date
    $cutoffHour = $now.AddHours(-1)
    $kept = New-Object System.Collections.Generic.List[string]
    foreach ($ts in @($State.throttle_420_timestamps)) {
        if ([string]::IsNullOrWhiteSpace($ts)) { continue }
        try {
            $dt = [datetimeoffset]::Parse($ts)
            if ($dt.UtcDateTime -ge $cutoffHour.ToUniversalTime()) {
                [void]$kept.Add($ts)
            }
        } catch {
            continue
        }
    }
    $State.throttle_420_timestamps = @($kept)
    $State.throttle_count_last_hour = $State.throttle_420_timestamps.Count
}

function Get-ComicVine420Counts {
    param([Parameter(Mandatory = $true)]$State)
    $now = Get-Date
    $cutoff30 = $now.AddMinutes(-30).ToUniversalTime()
    $cutoff60 = $now.AddHours(-1).ToUniversalTime()
    $count30 = 0
    $count60 = 0
    foreach ($ts in @($State.throttle_420_timestamps)) {
        try {
            $dt = [datetimeoffset]::Parse($ts).UtcDateTime
            if ($dt -ge $cutoff60) { $count60++ }
            if ($dt -ge $cutoff30) { $count30++ }
        } catch {
            continue
        }
    }
    return @{ count30 = $count30; count60 = $count60 }
}

function Apply-ComicVineSleepRecovery {
    param([Parameter(Mandatory = $true)]$State)
    if ($Forever) { return }
    $minSleep = [double](Get-ComicVineEffectiveMinSleepSeconds)
    $before = [double]$State.current_sleep_seconds
    if ($before -le $minSleep) { return }

    if ($null -eq $State.last_420_at -or [string]::IsNullOrWhiteSpace([string]$State.last_420_at)) {
        if (-not $Forever -and $before -le [double]$ComicVineBaseSleepSeconds) { return }
        $State.current_sleep_seconds = [math]::Max($minSleep, $before - 0.25)
        if ($State.current_sleep_seconds -ne $before) {
            Write-Log "ComicVine sleep recovery (no prior 420): $before -> $($State.current_sleep_seconds)"
        }
        return
    }
    try {
        $last420 = [datetimeoffset]::Parse([string]$State.last_420_at).UtcDateTime
        if ((Get-Date).ToUniversalTime() - $last420 -gt [TimeSpan]::FromMinutes(30)) {
            $State.current_sleep_seconds = [math]::Max($minSleep, $before - 0.25)
            if ($State.current_sleep_seconds -ne $before) {
                Write-Log "ComicVine sleep recovery (no 420 in 30m): $before -> $($State.current_sleep_seconds)"
            }
        }
    } catch {
        return
    }
}

function Register-ComicVine420 {
    param([Parameter(Mandatory = $true)]$State)
    $nowIso = (Get-Date).ToUniversalTime().ToString("o")
    $before = [double]$State.current_sleep_seconds
    $State.last_420_at = $nowIso
    $State.total_420_count = [int]$State.total_420_count + 1
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($ts in @($State.throttle_420_timestamps)) { [void]$list.Add($ts) }
    [void]$list.Add($nowIso)
    $State.throttle_420_timestamps = @($list)
    Update-ComicVineRateThrottleWindows -State $State
    $counts = Get-ComicVine420Counts -State $State
    if ($Forever) {
        [void](Enforce-ComicVineForeverSleepFloor -State $State)
        Write-Log "420 detected (forever steady crawl); total_420_count=$($State.total_420_count) throttle_count_last_hour=$($State.throttle_count_last_hour); sleep held at $($State.current_sleep_seconds)s" -Level "WARN"
        return
    }
    $bump = 1
    if ($counts.count60 -ge 3) {
        $bump = 5
    } elseif ($counts.count30 -ge 2) {
        $bump = 2
    }
    $State.current_sleep_seconds = [math]::Min([double]$State.max_sleep_seconds, $before + $bump)
    Write-Log "420 detected; total_420_count=$($State.total_420_count) throttle_count_last_hour=$($State.throttle_count_last_hour)" -Level "WARN"
    Write-Log "ComicVine throttle detected; sleep_seconds increased $before -> $($State.current_sleep_seconds)" -Level "WARN"
}

function Get-ComicVineImportSleepSeconds {
    $state = Load-ComicVineRateState
    Apply-ComicVineSleepRecovery -State $state
    [void](Enforce-ComicVineForeverSleepFloor -State $state)
    Save-ComicVineRateState -State $state
    Write-Log "ComicVine current_sleep_seconds=$($state.current_sleep_seconds)"
    return [double]$state.current_sleep_seconds
}

function Update-ComicVineRateAfterImport {
    param(
        [Parameter(Mandatory = $true)][string]$OutputBlob,
        [switch]$Throttled
    )
    $state = Load-ComicVineRateState
    $state.total_requests_observed = [int]$state.total_requests_observed + 1
    if ($Throttled -or (Test-OutputThrottle420 -OutputBlob $OutputBlob)) {
        Register-ComicVine420 -State $state
    }
    Update-ComicVineRateThrottleWindows -State $state
    [void](Enforce-ComicVineForeverSleepFloor -State $state)
    Save-ComicVineRateState -State $state
    Write-Log "ComicVine current_sleep_seconds=$($state.current_sleep_seconds)"
}

function Test-OutputThrottle420 {
    param([string]$OutputBlob)
    if ($OutputBlob -match "HTTP/1\.1 420") { return $true }
    return ($OutputBlob -match "\b420\b") -or ($OutputBlob -match "(?i)too many requests") -or ($OutputBlob -match "(?i)throttle")
}

function Parse-ImportMetrics {
    param([string[]]$Lines)
    $metrics = @{
        final_offset = $null
        total_candidates_seen = 0
        imported_series = 0
        accepted_volumes = 0
        skipped_publisher = 0
        issues_created = 0
        issues_updated = 0
        cover_images_created = 0
        cover_images_skipped = 0
        skipped_quality_gate = 0
        failures = 0
        issue_import_ran = $false
    }
    foreach ($line in $Lines) {
        if ($line -match "^final_offset=(\d+)") { $metrics.final_offset = [int]$Matches[1] }
        if ($line -match "^total_candidates_seen=(\d+)") { $metrics.total_candidates_seen = [int]$Matches[1] }
        if ($line -match "^imported_series=(\d+)") { $metrics.imported_series = [int]$Matches[1] }
        if ($line -match "^accepted_volumes=(\d+)") { $metrics.accepted_volumes = [int]$Matches[1] }
        if ($line -match "^skipped_publisher=(\d+)") { $metrics.skipped_publisher = [int]$Matches[1] }
        if ($line -match "^issues_created=(\d+)") { $metrics.issues_created = [int]$Matches[1] }
        if ($line -match "^issues_updated=(\d+)") { $metrics.issues_updated = [int]$Matches[1] }
        if ($line -match "^cover_images_created=(\d+)") { $metrics.cover_images_created = [int]$Matches[1] }
        if ($line -match "^cover_images_skipped=(\d+)") { $metrics.cover_images_skipped = [int]$Matches[1] }
        if ($line -match "^skipped_quality_gate=(\d+)") { $metrics.skipped_quality_gate = [int]$Matches[1] }
        if ($line -match "^failures=(\d+)") { $metrics.failures = [int]$Matches[1] }
        if ($line -match "^issue_import_ran=(True|False)") { $metrics.issue_import_ran = ($Matches[1] -eq "True") }
    }
    return $metrics
}

function Count-StrictPublisherMismatchLines {
    param([string[]]$Lines)
    $count = 0
    foreach ($line in $Lines) {
        if ($line -match "STRICT_PUBLISHER_MISMATCH") { $count++ }
    }
    return $count
}

function Test-ForeverImportTrueApiFailure {
    param(
        [Parameter(Mandatory = $true)]$ImportResult
    )
    if ($ImportResult.throttled) { return $true }
    $m = $ImportResult.metrics
    if ([int]$m.failures -gt 0) { return $true }
    $blob = @($ImportResult.output) -join "`n"
    if ($blob -match "(?i)Traceback \(most recent call last\)") { return $true }
    if ($blob -match "(?i)ConnectionError|TimeoutError|Read timed out") { return $true }
    if ($blob -match "HTTP/1\.1 5\d\d") { return $true }
    if ($blob -match "HTTP/1\.1 420") { return $true }
    return $false
}

function Test-ForeverPublisherMismatchOnlyChunk {
    param(
        [Parameter(Mandatory = $true)]$ImportResult
    )
    if ($ImportResult.throttled) { return $false }
    if (Test-ForeverImportTrueApiFailure -ImportResult $ImportResult) { return $false }

    $m = $ImportResult.metrics
    $blob = @($ImportResult.output) -join "`n"
    $mismatchLines = Count-StrictPublisherMismatchLines -Lines @($ImportResult.output)
    $skippedPublisher = [int]$m.skipped_publisher
    if ($skippedPublisher -le 0 -and $mismatchLines -gt 0) {
        $skippedPublisher = $mismatchLines
    }
    $candidatesSeen = [int]$m.total_candidates_seen
    if ($candidatesSeen -le 0 -and $skippedPublisher -gt 0) {
        $candidatesSeen = $skippedPublisher
    }

    if ([int]$m.imported_series -gt 0 -or [int]$m.accepted_volumes -gt 0) { return $false }
    if ([int]$m.issues_created -gt 0 -or [int]$m.issues_updated -gt 0) { return $false }
    if ($skippedPublisher -le 0 -or $candidatesSeen -le 0) { return $false }

    if ([int]$ImportResult.exit_code -eq 3) {
        if ($blob -notmatch "STRICT_PUBLISHER_MISMATCH") { return $false }
        if ($blob -notmatch "(?i)no issue import phase ran") { return $false }
        return $true
    }
    if ([int]$ImportResult.exit_code -ne 0) { return $false }
    return $true
}

function Test-ForeverStrictPublisherMismatchEmptyChunk {
    param([Parameter(Mandatory = $true)]$ImportResult)
    return (Test-ForeverPublisherMismatchOnlyChunk -ImportResult $ImportResult)
}

function Apply-ForeverPublisherMismatchOnlyOffset {
    param(
        [Parameter(Mandatory = $true)]$Entry,
        [Parameter(Mandatory = $true)]$PubRow,
        [Parameter(Mandatory = $true)][int]$OffsetBefore,
        [Parameter(Mandatory = $true)][int]$ChunkLimit,
        [Parameter(Mandatory = $true)]$ImportResult
    )
    $nextOffset = $OffsetBefore + $ChunkLimit
    if ($null -ne $ImportResult.metrics.final_offset) {
        $finalOffset = [int]$ImportResult.metrics.final_offset
        if ($finalOffset -gt $nextOffset) {
            $nextOffset = $finalOffset
        }
    }
    $Entry.last_offset = $nextOffset
    $PubRow.offset = $nextOffset
    $PubRow.status = "ACTIVE"
}

function Write-ForeverImportFailureLog {
    param(
        [Parameter(Mandatory = $true)]$ImportResult,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$ImportArgs
    )
    $exitCode = [int]$ImportResult.exit_code
    if ($exitCode -eq 0) { return }
    $output = @($ImportResult.output)
    $excerpt = ($output | Select-Object -Last 25) -join " | "
    if ($excerpt.Length -gt 2000) { $excerpt = $excerpt.Substring(0, 2000) }
    Write-Log "Command failed: $Label" -Level "WARN"
    Write-Log "  > python $($ImportArgs -join ' ')" -Level "WARN"
    Write-Log "  exit_code=$exitCode" -Level "WARN"
    Write-Log "  output_excerpt: $excerpt" -Level "WARN"
}

function Apply-ForeverPublisherOffsetAfterChunk {
    param(
        [Parameter(Mandatory = $true)]$Entry,
        [Parameter(Mandatory = $true)]$PubRow,
        [Parameter(Mandatory = $true)]$ImportResult,
        [Parameter(Mandatory = $true)][string]$PublisherName,
        [Parameter(Mandatory = $true)][int]$OffsetBefore
    )
    if ($null -ne $ImportResult.metrics.final_offset) {
        $Entry.last_offset = [int]$ImportResult.metrics.final_offset
        $PubRow.offset = $Entry.last_offset
    }
    if ([int]$ImportResult.metrics.total_candidates_seen -eq 0) {
        $Entry.publisher_exhausted = $true
        $PubRow.status = "EXHAUSTED"
        Write-Log "Publisher exhausted (zero candidates): $PublisherName at offset $OffsetBefore"
    } else {
        $PubRow.status = "ACTIVE"
    }
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
        $run = Invoke-ExternalPython -ArgumentList $step.Command[1..($step.Command.Length - 1)] -Label $step.Label
        $code = $run.exit_code
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

function Invoke-ExternalPython {
    param(
        [Parameter(Mandatory = $true)][string[]]$ArgumentList,
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$StrictFailure,
        [switch]$SuppressFailureLog
    )
    $stdoutLines = New-Object System.Collections.Generic.List[string]
    $stderrLines = New-Object System.Collections.Generic.List[string]
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & python @ArgumentList 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $text = $_.ToString()
                if ($_.Exception -and $_.Exception.Message) {
                    $text = $_.Exception.Message
                }
                [void]$stderrLines.Add($text)
            } else {
                [void]$stdoutLines.Add([string]$_)
            }
        }
    } finally {
        $ErrorActionPreference = $prevEap
    }
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) { $exitCode = 0 }

    $allLines = @()
    foreach ($line in $stdoutLines) { $allLines += $line }
    foreach ($line in $stderrLines) { $allLines += $line }

    foreach ($line in $stdoutLines) {
        Write-Host $line
        Add-Content -Path $LogFile -Value $line -Encoding utf8
    }
    foreach ($line in $stderrLines) {
        Write-Host $line
        Add-Content -Path $LogFile -Value $line -Encoding utf8
        if ($exitCode -ne 0 -and -not $SuppressFailureLog) {
            Write-Log "stderr: $line" -Level "WARN"
        } else {
            Write-Log "stderr: $line" -Level "INFO"
        }
    }

    if ($exitCode -ne 0 -and -not $SuppressFailureLog) {
        $excerpt = ($allLines | Select-Object -Last 25) -join " | "
        if ($excerpt.Length -gt 2000) { $excerpt = $excerpt.Substring(0, 2000) }
        Write-Log "Command failed: $Label" -Level "WARN"
        Write-Log "  > python $($ArgumentList -join ' ')" -Level "WARN"
        Write-Log "  exit_code=$exitCode" -Level "WARN"
        Write-Log "  output_excerpt: $excerpt" -Level "WARN"
        if ($StrictFailure) {
            throw "Command failed with exit code ${exitCode}: $Label"
        }
    }

    return @{
        exit_code = [int]$exitCode
        stdout = @($stdoutLines)
        stderr = @($stderrLines)
        output = $allLines
    }
}

function Get-ImportThrottleRetryMax {
    if ($Forever) { return 0 }
    return [int]$ThrottleRetryMax
}

function Invoke-ImportWithThrottle {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$ImportScript,
        [Parameter(Mandatory = $true)][string]$Label
    )
    $throttleAttempts = 0
    $importResult = $null
    $retryMax = Get-ImportThrottleRetryMax
    do {
        $importResult = & $ImportScript
        if ($importResult.throttled -and $throttleAttempts -lt $retryMax) {
            $throttleAttempts++
            $Script:RunStats.throttle_events++
            $retrySleep = Get-ComicVineImportSleepSeconds
            Write-Log "HTTP 420/throttle for $Label; sleep_seconds=$retrySleep; cooldown ${ThrottleSleepSeconds}s (retry $throttleAttempts/$retryMax)" -Level "WARN"
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
        [Parameter(Mandatory = $true)][string]$Label,
        [switch]$ForeverQuietFailureLog
    )
    Write-Log "START $Label"
    if (-not $WhatIf) {
        $sleepSeconds = Get-ComicVineImportSleepSeconds
        Write-Log "ComicVine sleep seconds before import: $sleepSeconds"
        $ImportArgs = Set-ImportSleepArgument -ImportArgs $ImportArgs -SleepSeconds $sleepSeconds
    }
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
    $run = Invoke-ExternalPython -ArgumentList $ImportArgs -Label $Label -SuppressFailureLog:$ForeverQuietFailureLog
    $exitCode = $run.exit_code
    $output = @($run.output)
    $blob = $output -join "`n"
    $throttled = (Test-OutputThrottle420 -OutputBlob $blob)
    if (-not $WhatIf) {
        Update-ComicVineRateAfterImport -OutputBlob $blob -Throttled:$throttled
    }
    $result = @{
        exit_code = $exitCode
        output = $output
        throttled = $throttled
        metrics = (Parse-ImportMetrics -Lines $output)
    }
    if ($ForeverQuietFailureLog) {
        $mismatchOnly = Test-ForeverPublisherMismatchOnlyChunk -ImportResult $result
        $result.skipped_mismatch_only = $mismatchOnly
        if ($exitCode -ne 0 -and -not $mismatchOnly) {
            Write-ForeverImportFailureLog -ImportResult $result -Label $Label -ImportArgs $ImportArgs
        } elseif ($mismatchOnly) {
            Write-Log "Forever mismatch-only chunk (exit=$exitCode): offset will advance; not a hard failure" -Level "INFO"
        }
    }
    return $result
}

function Set-ImportSleepArgument {
    param(
        [Parameter(Mandatory = $true)][string[]]$ImportArgs,
        [Parameter(Mandatory = $true)][double]$SleepSeconds
    )
    $sleepText = Format-ComicVineSleepSeconds -Seconds $SleepSeconds
    $out = New-Object System.Collections.Generic.List[string]
    for ($i = 0; $i -lt $ImportArgs.Count; $i++) {
        if ($ImportArgs[$i] -eq "--sleep-seconds" -and ($i + 1) -lt $ImportArgs.Count) {
            [void]$out.Add("--sleep-seconds")
            [void]$out.Add($sleepText)
            $i++
            continue
        }
        [void]$out.Add($ImportArgs[$i])
    }
    return @($out)
}

function Invoke-SeriesImport {
    param(
        [Parameter(Mandatory = $true)][string]$SeriesName,
        [Parameter(Mandatory = $true)][int]$Offset,
        [int]$Limit = $PerSeriesLimit
    )
    $sleepPlaceholder = Format-ComicVineSleepSeconds -Seconds $ComicVineBaseSleepSeconds
    $importArgs = @(
        "scripts\p97_import_comicvine_catalog.py",
        "--series-name", $SeriesName,
        "--limit", "$Limit",
        "--offset", "$Offset",
        "--import-issues",
        "--sleep-seconds", $sleepPlaceholder,
        "--resume"
    )
    return Invoke-ComicVineImport -ImportArgs $importArgs -Label "import series: $SeriesName (offset=$Offset)"
}

function Invoke-PublisherImport {
    param(
        [Parameter(Mandatory = $true)][string]$PublisherName,
        [Parameter(Mandatory = $true)][int]$Offset,
        [int]$Limit = $PerSeriesLimit,
        [switch]$ForeverChunk
    )
    # Publisher volumes API filter + strict client match; English/US gate remains default (no --allow-international-editions).
    $sleepPlaceholder = Format-ComicVineSleepSeconds -Seconds $ComicVineBaseSleepSeconds
    $importArgs = @(
        "scripts\p97_import_comicvine_catalog.py",
        "--publisher", $PublisherName,
        "--strict-publisher",
        "--limit", "$Limit",
        "--offset", "$Offset",
        "--import-issues",
        "--sleep-seconds", $sleepPlaceholder,
        "--resume"
    )
    return Invoke-ComicVineImport -ImportArgs $importArgs -Label "import publisher: $PublisherName (offset=$Offset)" -ForeverQuietFailureLog:$ForeverChunk
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
    $rateState = Load-ComicVineRateState
    Update-ComicVineRateThrottleWindows -State $rateState
    $publishersExhausted = @()
    $publishersPaused = @()
    if ($null -ne $Progress) {
        foreach ($name in $PublisherTargets) {
            if ($Progress.publishers[$name].publisher_exhausted) { $publishersExhausted += $name }
        }
    }
    if ($Forever) {
        $pauseState = Load-PublisherPauseState
        foreach ($name in $PublisherTargets) {
            if (Test-PublisherPaused -PauseState $pauseState -PublisherName $name) { $publishersPaused += $name }
        }
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
        comicvine_total_420_count = [int]$rateState.total_420_count
        comicvine_final_sleep_seconds = [double]$rateState.current_sleep_seconds
        comicvine_throttle_count_last_hour = [int]$rateState.throttle_count_last_hour
        comicvine_rate_state_file = $RateStateFile
    }
    if ($Forever) {
        $summary.mode = "forever"
        $summary.current_publisher = $Script:RunStats.last_publisher
        $summary.current_offset = $Script:RunStats.last_offset
        $summary.current_chunk_limit = $(if ($Script:ForeverState) { $Script:ForeverState.current_chunk_limit } else { 0 })
        $summary.publishers_exhausted = @($publishersExhausted)
        $summary.publishers_paused = @($publishersPaused)
        $summary.total_chunks_completed = $(if ($Script:ForeverState) { $Script:ForeverState.chunks_completed_this_run } else { 0 })
        $summary.total_420_count = $(if ($Script:ForeverState) { $Script:ForeverState.total_420_count_this_run } else { 0 })
        $summary.current_sleep_seconds = [double]$rateState.current_sleep_seconds
        $summary.last_successful_chunk_at = $(if ($Script:ForeverState) { $Script:ForeverState.last_successful_chunk_at } else { $null })
        if ($Script:ForeverState -and $Script:ForeverState.last_chunk_result) {
            $summary.last_created_count = [int]$Script:ForeverState.last_chunk_result.created
            $summary.last_updated_count = [int]$Script:ForeverState.last_chunk_result.updated
        }
        $summary.forever_progress_file = $ForeverProgressFile
        $summary.acquisition_lock_file = $AcquisitionLockFile
    }
    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $SummaryFile -Encoding utf8
}

function Get-PublisherChunkLimit {
    param([Parameter(Mandatory = $true)][string]$PublisherName)
    if ($PublisherChunkLimits.ContainsKey($PublisherName)) {
        return [int]$PublisherChunkLimits[$PublisherName]
    }
    return 250
}

function Format-Count {
    param([Parameter(Mandatory = $true)][int]$Value)
    return $Value.ToString("N0", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-RuntimeHoursMinutes {
    param([Parameter(Mandatory = $true)][double]$TotalHours)
    $totalMinutes = [math]::Max(0, [int][math]::Floor($TotalHours * 60))
    $hours = [int][math]::Floor($totalMinutes / 60)
    $minutes = [int]($totalMinutes % 60)
    return ("{0:D2}h {1:D2}m" -f $hours, $minutes)
}

function ConvertFrom-PythonStdoutJson {
    param(
        [Parameter(Mandatory = $true)][string[]]$StdoutLines,
        [string]$LogLabel = "python_json"
    )
    if ($null -eq $StdoutLines -or $StdoutLines.Count -eq 0) {
        Write-Log "${LogLabel}_parse_success=False (empty stdout)" -Level "WARN"
        throw "Python JSON output was empty ($LogLabel)"
    }
    $text = ($StdoutLines -join "`n").Trim()
    if ($text.Length -ge 1 -and [int][char]$text[0] -eq 0xFEFF) {
        $text = $text.Substring(1)
    }
    if ($text -isnot [string]) {
        $text = [string]$text
    }
    if ($text -match "^\s*\{") {
        # Already a single JSON object string (possibly multi-line pretty-print).
    } elseif ($StdoutLines.Count -eq 1 -and ($StdoutLines[0] -is [pscustomobject] -or $StdoutLines[0] -is [hashtable])) {
        Write-Log "${LogLabel}_parse_success=True (stdout already parsed object)" -Level "INFO"
        return $StdoutLines[0]
    }
    $start = $text.IndexOf("{")
    $end = $text.LastIndexOf("}")
    if ($start -lt 0 -or $end -le $start) {
        $excerpt = if ($text.Length -gt 240) { $text.Substring(0, 240) } else { $text }
        Write-Log "raw_${LogLabel}_json_excerpt=$excerpt" -Level "WARN"
        Write-Log "${LogLabel}_parse_success=False (no JSON object braces)" -Level "WARN"
        throw "No JSON object found in Python output ($LogLabel)"
    }
    $jsonText = $text.Substring($start, $end - $start + 1)
    $excerptLen = [math]::Min(240, $jsonText.Length)
    Write-Log "raw_${LogLabel}_json_excerpt=$($jsonText.Substring(0, $excerptLen))"
    try {
        $parsed = $jsonText | ConvertFrom-Json
        Write-Log "${LogLabel}_parse_success=True"
        return $parsed
    } catch {
        Write-Log "${LogLabel}_parse_success=False error=$($_.Exception.Message)" -Level "WARN"
        throw
    }
}

function Get-CatalogProgressSnapshot {
    if ($WhatIf) {
        return @{
            total_issues = 0
            total_images = 0
            ready_covers = 0
            pending_covers = 0
            fingerprints = 0
            ocr_rows = 0
        }
    }
    $run = Invoke-ExternalPython -ArgumentList @("scripts\p97_progress_watch.py", "--json") -Label "catalog progress snapshot"
    if ($run.exit_code -ne 0) {
        throw "Failed to read catalog progress snapshot (exit $($run.exit_code))"
    }
    return (ConvertFrom-PythonStdoutJson -StdoutLines @($run.stdout) -LogLabel "catalog_progress")
}

function New-PublisherPauseState {
    return @{ publishers = @{} }
}

function Load-PublisherPauseState {
    if (-not (Test-Path -LiteralPath $PublisherPauseStateFile)) {
        return New-PublisherPauseState
    }
    try {
        $raw = Get-Content -LiteralPath $PublisherPauseStateFile -Raw -Encoding utf8 | ConvertFrom-Json
        $doc = New-PublisherPauseState
        if ($null -ne $raw.publishers) {
            foreach ($prop in $raw.publishers.PSObject.Properties) {
                $doc.publishers[$prop.Name] = @{
                    paused_until = $prop.Value.paused_until
                    last_reason = $prop.Value.last_reason
                }
            }
        } else {
            foreach ($prop in $raw.PSObject.Properties) {
                if ($prop.Name -eq "publishers") { continue }
                $doc.publishers[$prop.Name] = @{
                    paused_until = $prop.Value.paused_until
                    last_reason = $prop.Value.last_reason
                }
            }
        }
        return $doc
    } catch {
        Write-Log "Publisher pause state corrupt; resetting: $($_.Exception.Message)" -Level "WARN"
        return New-PublisherPauseState
    }
}

function Save-PublisherPauseState {
    param([Parameter(Mandatory = $true)]$State)
    $export = [ordered]@{}
    foreach ($name in $State.publishers.Keys) {
        $export[$name] = [ordered]@{
            paused_until = $State.publishers[$name].paused_until
            last_reason = $State.publishers[$name].last_reason
        }
    }
    $export | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $PublisherPauseStateFile -Encoding utf8
}

function Test-PublisherPaused {
    param(
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)][string]$PublisherName
    )
    if ($null -eq $PauseState -or $null -eq $PauseState.publishers) { return $false }
    if (-not $PauseState.publishers.ContainsKey($PublisherName)) { return $false }
    $entry = $PauseState.publishers[$PublisherName]
    $untilText = [string]$entry.paused_until
    if ([string]::IsNullOrWhiteSpace($untilText)) { return $false }
    try {
        $until = [datetimeoffset]::Parse($untilText).UtcDateTime
        return ((Get-Date).ToUniversalTime() -lt $until)
    } catch {
        return $false
    }
}

function Remove-ExpiredPublisherPauses {
    param([Parameter(Mandatory = $true)]$PauseState)
    if ($null -eq $PauseState -or $null -eq $PauseState.publishers) { return }
    $toRemove = New-Object System.Collections.Generic.List[string]
    foreach ($name in @($PauseState.publishers.Keys)) {
        if (-not (Test-PublisherPaused -PauseState $PauseState -PublisherName $name)) {
            [void]$toRemove.Add($name)
        }
    }
    foreach ($name in $toRemove) {
        if ($PauseState.publishers.ContainsKey($name)) {
            $PauseState.publishers.Remove($name)
        }
    }
    if ($toRemove.Count -gt 0) {
        Save-PublisherPauseState -State $PauseState
    }
}

function Get-ForeverProgressPublisherEntry {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)][string]$PublisherName
    )
    if ($null -eq $ProgressDoc -or $null -eq $ProgressDoc.publishers) { return $null }
    $pubs = $ProgressDoc.publishers
    if ($pubs -is [System.Collections.IDictionary]) {
        if ($pubs.Contains($PublisherName)) { return $pubs[$PublisherName] }
        return $null
    }
    if ($pubs.PSObject.Properties.Name -contains $PublisherName) {
        return $pubs.$PublisherName
    }
    return $null
}

function Test-ForeverPublisherExhausted {
    param([Parameter(Mandatory = $true)]$PublisherEntry)
    if ($null -eq $PublisherEntry) { return $true }
    $raw = $PublisherEntry.publisher_exhausted
    if ($null -eq $raw) { return $false }
    if ($raw -is [bool]) { return $raw }
    $text = [string]$raw
    if ([string]::IsNullOrWhiteSpace($text)) { return $false }
    return ($text.Trim().ToLowerInvariant() -eq "true")
}

function Sync-ForeverPublisherRunStatuses {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState
    )
    if ($null -eq $Script:ForeverState) { return }
    foreach ($name in $PublisherTargets) {
        $entry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $name
        $row = $Script:ForeverState.publisher_progress[$name]
        if ($null -eq $row) { continue }
        if (Test-ForeverPublisherExhausted -PublisherEntry $entry) {
            $row.status = "EXHAUSTED"
        } elseif (Test-PublisherPaused -PauseState $PauseState -PublisherName $name) {
            $row.status = "PAUSED"
        } elseif ([int]$row.chunks -gt 0) {
            $row.status = "ACTIVE"
        } else {
            $row.status = "PENDING"
        }
    }
}

function Set-PublisherPaused {
    param(
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)][string]$PublisherName,
        [Parameter(Mandatory = $true)][string]$Reason
    )
    $until = (Get-Date).ToUniversalTime().AddMinutes($ForeverPublisherPauseMinutes)
    $PauseState.publishers[$PublisherName] = @{
        paused_until = $until.ToString("o")
        last_reason = $Reason
    }
    Save-PublisherPauseState -State $PauseState
    Write-Log "Publisher paused: $PublisherName until $($PauseState.publishers[$PublisherName].paused_until) reason=$Reason" -Level "WARN"
}

function Test-ForeverPublisherEligible {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)][string]$PublisherName
    )
    $entry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $PublisherName
    if ($null -eq $entry) { return $false }
    if (Test-ForeverPublisherExhausted -PublisherEntry $entry) { return $false }
    if (Test-PublisherPaused -PauseState $PauseState -PublisherName $PublisherName) { return $false }
    return $true
}

function Get-ForeverPublisherSelectionOrder {
    param([Parameter(Mandatory = $true)]$ProgressDoc)
    if ($Script:ForeverMajorOnly -and -not (Test-AllForeverMajorPublishersComplete -ProgressDoc $ProgressDoc)) {
        return @($ForeverMajorPublishers)
    }
    return @(Get-ForeverPublisherWorkQueue -ProgressDoc $ProgressDoc)
}

function Test-ForeverWorkQueueHasEligiblePublisher {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)][string[]]$PublisherNames
    )
    foreach ($name in $PublisherNames) {
        if (Test-ForeverPublisherEligible -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherName $name) {
            return $true
        }
    }
    return $false
}

function Test-ForeverWorkQueueAllNonExhaustedPaused {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)][string[]]$PublisherNames
    )
    $foundNonExhausted = $false
    foreach ($name in $PublisherNames) {
        $entry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $name
        if (Test-ForeverPublisherExhausted -PublisherEntry $entry) { continue }
        $foundNonExhausted = $true
        if (-not (Test-PublisherPaused -PauseState $PauseState -PublisherName $name)) {
            return $false
        }
    }
    return $foundNonExhausted
}

function Test-AllForeverMajorPublishersComplete {
    param([Parameter(Mandatory = $true)]$ProgressDoc)
    foreach ($name in $ForeverMajorPublishers) {
        $entry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $name
        if (-not (Test-ForeverPublisherExhausted -PublisherEntry $entry)) {
            return $false
        }
    }
    return $true
}

function Get-ForeverPublisherWorkQueue {
    param([Parameter(Mandatory = $true)]$ProgressDoc)
    if ($Script:ForeverMajorOnly) {
        if (-not (Test-AllForeverMajorPublishersComplete -ProgressDoc $ProgressDoc)) {
            return @($ForeverMajorPublishers)
        }
        return @($ForeverMajorPublishers + $ForeverMinorPublishers)
    }
    return @($PublisherTargets)
}

function Select-ForeverPublisherToRun {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState
    )
    $queue = Get-ForeverPublisherSelectionOrder -ProgressDoc $ProgressDoc
    foreach ($name in $queue) {
        if (Test-ForeverPublisherEligible -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherName $name) {
            return $name
        }
    }
    return $null
}

function Get-NextForeverMajorPublisher {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState,
        [string]$AfterPublisher
    )
    $startIdx = 0
    if (-not [string]::IsNullOrWhiteSpace($AfterPublisher)) {
        $idx = [array]::IndexOf($ForeverMajorPublishers, $AfterPublisher)
        if ($idx -ge 0) {
            $startIdx = $idx + 1
        }
    }
    for ($i = $startIdx; $i -lt $ForeverMajorPublishers.Count; $i++) {
        $name = $ForeverMajorPublishers[$i]
        if (Test-ForeverPublisherEligible -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherName $name) {
            return $name
        }
    }
    for ($i = 0; $i -lt $ForeverMajorPublishers.Count; $i++) {
        $name = $ForeverMajorPublishers[$i]
        if ($name -eq $AfterPublisher) { continue }
        if (Test-ForeverPublisherEligible -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherName $name) {
            return $name
        }
    }
    return $null
}

function Reset-ForeverPublisherExhaustedFlags {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)][string[]]$PublisherNames
    )
    foreach ($name in $PublisherNames) {
        if (Test-PublisherPaused -PauseState $PauseState -PublisherName $name) { continue }
        $ProgressDoc.publishers[$name].publisher_exhausted = $false
        if ($Script:ForeverState -and $Script:ForeverState.publisher_progress.ContainsKey($name)) {
            $Script:ForeverState.publisher_progress[$name].status = "PENDING"
        }
    }
}

function Test-AcquisitionLockActive {
    param([Parameter(Mandatory = $true)][string]$LockPath)
    if (-not (Test-Path -LiteralPath $LockPath)) { return $false }
    try {
        $raw = Get-Content -LiteralPath $LockPath -Raw -Encoding utf8 | ConvertFrom-Json
        $pidValue = [int]$raw.pid
        if ($pidValue -le 0) { return $false }
        $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        return ($null -ne $proc)
    } catch {
        return $false
    }
}

function Acquire-AcquisitionRunnerLock {
    if ($WhatIf) { return }
    if (Test-AcquisitionLockActive -LockPath $AcquisitionLockFile) {
        $existing = Get-Content -LiteralPath $AcquisitionLockFile -Raw -Encoding utf8
        throw "Another acquisition runner appears active. Lock file: $AcquisitionLockFile`n$existing"
    }
    if (Test-Path -LiteralPath $AcquisitionLockFile) {
        Write-Log "Stale acquisition lock found; replacing." -Level "WARN"
    }
    $lockDoc = [ordered]@{
        pid = $PID
        started_at = (Get-Date).ToUniversalTime().ToString("o")
        mode = $(if ($Forever) { "forever" } else { "overnight" })
        host = $env:COMPUTERNAME
    }
    $lockDoc | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $AcquisitionLockFile -Encoding utf8
    Write-Log "Acquisition lock acquired: $AcquisitionLockFile (pid=$PID)"
}

function Release-AcquisitionRunnerLock {
    if ($WhatIf) { return }
    if (-not (Test-Path -LiteralPath $AcquisitionLockFile)) { return }
    try {
        $raw = Get-Content -LiteralPath $AcquisitionLockFile -Raw -Encoding utf8 | ConvertFrom-Json
        if ([int]$raw.pid -eq $PID) {
            Remove-Item -LiteralPath $AcquisitionLockFile -Force
            Write-Log "Acquisition lock released."
        }
    } catch {
        Remove-Item -LiteralPath $AcquisitionLockFile -Force -ErrorAction SilentlyContinue
    }
}

function Initialize-ComicVineForeverRateState {
    $state = Load-ComicVineRateState
    $floor = [double]$ComicVineForeverMinSleepSeconds
    $state.current_sleep_seconds = $floor
    $state.min_sleep_seconds = $floor
    [void](Enforce-ComicVineForeverSleepFloor -State $state)
    Save-ComicVineRateState -State $state
    Write-Log "Forever ComicVine rate state initialized at ${floor}s (downtrim disabled)"
}

function Initialize-ForeverRunState {
    param(
        [Parameter(Mandatory = $true)][datetime]$StartTime,
        [Parameter(Mandatory = $true)]$CatalogSnapshot
    )
    $Script:ForeverState = @{
        started_at = $StartTime.ToUniversalTime().ToString("o")
        issues_before_run = [int]$CatalogSnapshot.total_issues
        images_before_run = [int]$CatalogSnapshot.total_images
        issues_added_this_run = 0
        images_added_this_run = 0
        chunks_completed_this_run = 0
        total_420_count_at_start = 0
        total_420_count_this_run = 0
        issue_samples = New-Object System.Collections.Generic.List[object]
        publisher_progress = @{}
        last_chunk_result = @{ created = 0; updated = 0; skipped = 0; failed = 0; outcome = "ok" }
        last_successful_chunk_at = $null
        current_publisher = ""
        current_offset = 0
        current_chunk_limit = 0
        status = "RUNNING"
    }
    $rate = Load-ComicVineRateState
    $Script:ForeverState.total_420_count_at_start = [int]$rate.total_420_count
    foreach ($name in $PublisherTargets) {
        $Script:ForeverState.publisher_progress[$name] = @{
            offset = 0
            chunks = 0
            created = 0
            updated = 0
            "420s" = 0
            mismatch_only_chunks = 0
            skipped_mismatch_volumes = 0
            status = "PENDING"
        }
    }
}

function Update-ForeverPublisherProgressFromProgressDoc {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        $PauseState = $null
    )
    foreach ($name in $PublisherTargets) {
        $entry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $name
        $row = $Script:ForeverState.publisher_progress[$name]
        if ($null -eq $row) { continue }
        if ($null -eq $entry) { continue }
        $row.offset = [int]$entry.last_offset
        if ($null -ne $PauseState) {
            if (Test-ForeverPublisherExhausted -PublisherEntry $entry) {
                $row.status = "EXHAUSTED"
            } elseif (Test-PublisherPaused -PauseState $PauseState -PublisherName $name) {
                $row.status = "PAUSED"
            } elseif ([int]$row.chunks -gt 0) {
                $row.status = "ACTIVE"
            } else {
                $row.status = "PENDING"
            }
        } elseif (Test-ForeverPublisherExhausted -PublisherEntry $entry) {
            $row.status = "EXHAUSTED"
        } elseif ([int]$row.chunks -gt 0) {
            $row.status = "ACTIVE"
        }
    }
}

function Get-IssuesAddedLastHour {
    if ($null -eq $Script:ForeverState) { return 0 }
    $cutoff = (Get-Date).ToUniversalTime().AddHours(-1)
    $baseline = [int]$Script:ForeverState.issues_before_run
    $samplesEnum = $Script:ForeverState.issue_samples
    if ($null -eq $samplesEnum) {
        return [math]::Max(0, [int]$Script:ForeverState.issues_added_this_run)
    }
    foreach ($sample in $samplesEnum) {
        if ($null -eq $sample) { continue }
        try {
            $atText = $null
            $issuesVal = $null
            if ($sample -is [System.Collections.IDictionary]) {
                $atText = [string]$sample["at"]
                $issuesVal = [int]$sample["issues"]
            } else {
                $atText = [string]$sample.at
                $issuesVal = [int]$sample.issues
            }
            if ([string]::IsNullOrWhiteSpace($atText)) { continue }
            $at = [datetimeoffset]::Parse($atText).UtcDateTime
            if ($at -le $cutoff) { $baseline = $issuesVal }
        } catch {
            continue
        }
    }
    $currentIssues = [int]$Script:ForeverState.issues_now
    if ($currentIssues -lt $baseline) {
        $baseline = [int]$Script:ForeverState.issues_before_run
    }
    return [math]::Max(0, $currentIssues - $baseline)
}

function Get-EstimatedTimeTo150k {
    $chunks = [int]$Script:ForeverState.chunks_completed_this_run
    if ($chunks -lt 3) { return "UNKNOWN" }
    $added = [math]::Max(0, [int]$Script:ForeverState.issues_added_this_run)
    if ($added -le 0) { return "UNKNOWN" }
    $avgPerChunk = $added / [double]$chunks
    if ($avgPerChunk -le 0) { return "UNKNOWN" }
    $remaining = [math]::Max(0, $GoalIssuesPrimary - [int]$Script:ForeverState.issues_now)
    $chunksNeeded = $remaining / $avgPerChunk
    $hoursPerChunk = ((Get-Date) - $Script:RunStats.start_time).TotalHours / [math]::Max(1, $chunks)
    $hoursRemaining = $chunksNeeded * $hoursPerChunk
    if ($hoursRemaining -gt 8760) { return "UNKNOWN" }
    return ("{0:0.#}h" -f $hoursRemaining)
}

function Export-ForeverPublisherProgressJson {
    $export = [ordered]@{}
    foreach ($name in $PublisherTargets) {
        $row = $Script:ForeverState.publisher_progress[$name]
        $export[$name] = [ordered]@{
            offset = [int]$row.offset
            chunks = [int]$row.chunks
            created = [int]$row.created
            updated = [int]$row.updated
            throttle_420_count = [int]$row."420s"
            mismatch_only_chunks = [int]$row.mismatch_only_chunks
            skipped_mismatch_volumes = [int]$row.skipped_mismatch_volumes
            status = [string]$row.status
        }
    }
    return $export
}

function Write-ForeverProgressArtifacts {
    param(
        [Parameter(Mandatory = $true)][datetime]$StartTime,
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState,
        [Parameter(Mandatory = $true)]$CatalogSnapshot
    )
    $rate = Load-ComicVineRateState
    Update-ComicVineRateThrottleWindows -State $rate
    if (Enforce-ComicVineForeverSleepFloor -State $rate) {
        Save-ComicVineRateState -State $rate
    }
    $Script:ForeverState.issues_now = [int]$CatalogSnapshot.total_issues
    $Script:ForeverState.images_now = [int]$CatalogSnapshot.total_images
    $Script:ForeverState.ready_covers = [int]$CatalogSnapshot.ready_covers
    $Script:ForeverState.pending_covers = [int]$CatalogSnapshot.pending_covers
    $Script:ForeverState.fingerprints = [int]$CatalogSnapshot.fingerprints
    $Script:ForeverState.ocr_rows = [int]$CatalogSnapshot.ocr_rows
    $Script:ForeverState.issues_added_this_run = [math]::Max(0, $Script:ForeverState.issues_now - $Script:ForeverState.issues_before_run)
    $Script:ForeverState.images_added_this_run = [math]::Max(0, $Script:ForeverState.images_now - $Script:ForeverState.images_before_run)
    $Script:ForeverState.total_420_count_this_run = [math]::Max(0, [int]$rate.total_420_count - $Script:ForeverState.total_420_count_at_start)
    $Script:ForeverState.current_sleep_seconds = [double]$rate.current_sleep_seconds
    $minutesSinceLast420 = Get-MinutesSinceLast420 -State $rate
    $runtimeSeconds = ((Get-Date) - $StartTime).TotalSeconds
    $goal150 = if ($GoalIssuesPrimary -gt 0) { [math]::Round(100.0 * $Script:ForeverState.issues_now / $GoalIssuesPrimary, 1) } else { 0.0 }
    $goal200 = if ($GoalIssuesStretch -gt 0) { [math]::Round(100.0 * $Script:ForeverState.issues_now / $GoalIssuesStretch, 1) } else { 0.0 }
    $avgIssues = if ($Script:ForeverState.chunks_completed_this_run -gt 0) {
        [math]::Round($Script:ForeverState.issues_added_this_run / [double]$Script:ForeverState.chunks_completed_this_run, 1)
    } else { 0.0 }

    Update-ForeverPublisherProgressFromProgressDoc -ProgressDoc $ProgressDoc -PauseState $PauseState
    Sync-ForeverPublisherRunStatuses -ProgressDoc $ProgressDoc -PauseState $PauseState

    $publishersExhausted = @($PublisherTargets | Where-Object { $ProgressDoc.publishers[$_].publisher_exhausted })
    $publishersPaused = @($PublisherTargets | Where-Object { Test-PublisherPaused -PauseState $PauseState -PublisherName $_ })

    $lastChunk = $Script:ForeverState.last_chunk_result
    $lastChunkExport = [ordered]@{
        created = [int]$lastChunk.created
        updated = [int]$lastChunk.updated
        skipped = [int]$lastChunk.skipped
        failed = [int]$lastChunk.failed
        outcome = [string]($lastChunk.outcome)
    }

    $pubProgress = Export-ForeverPublisherProgressJson
    $issuesLastHour = Get-IssuesAddedLastHour

    $currentPub = [string]$Script:ForeverState.current_publisher
    $currentMajor = $null
    if ($ForeverMajorPublishers -contains $currentPub) {
        $currentMajor = $currentPub
    }
    $majorPhaseComplete = Test-AllForeverMajorPublishersComplete -ProgressDoc $ProgressDoc
    $nextMajor = Get-NextForeverMajorPublisher -ProgressDoc $ProgressDoc -PauseState $PauseState -AfterPublisher $currentMajor
    $workQueue = Get-ForeverPublisherWorkQueue -ProgressDoc $ProgressDoc

    $doc = [ordered]@{
        mode = $(if ($Script:ForeverMajorOnly) { "forever_major" } else { "forever_all" })
        forever_major_only = [bool]$Script:ForeverMajorOnly
        major_publishers_phase_complete = [bool]$majorPhaseComplete
        major_publisher_order = @($ForeverMajorPublishers)
        current_major_publisher = $currentMajor
        next_major_publisher = $nextMajor
        publisher_work_queue = @($workQueue)
        status = $Script:ForeverState.status
        started_at = $Script:ForeverState.started_at
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
        runtime_seconds = [math]::Round($runtimeSeconds, 0)
        issues_before_run = $Script:ForeverState.issues_before_run
        issues_now = $Script:ForeverState.issues_now
        issues_added_this_run = $Script:ForeverState.issues_added_this_run
        issues_added_last_hour = $issuesLastHour
        images_now = $Script:ForeverState.images_now
        images_added_this_run = $Script:ForeverState.images_added_this_run
        ready_covers = $Script:ForeverState.ready_covers
        pending_covers = $Script:ForeverState.pending_covers
        fingerprints = $Script:ForeverState.fingerprints
        ocr_rows = $Script:ForeverState.ocr_rows
        current_publisher = $Script:ForeverState.current_publisher
        current_offset = $Script:ForeverState.current_offset
        current_chunk_limit = $Script:ForeverState.current_chunk_limit
        chunks_completed_this_run = $Script:ForeverState.chunks_completed_this_run
        publisher_progress = $pubProgress
        total_420_count_this_run = $Script:ForeverState.total_420_count_this_run
        current_sleep_seconds = $Script:ForeverState.current_sleep_seconds
        sleep_floor = [double]$ComicVineForeverMinSleepSeconds
        downtrim_enabled = $false
        last_420_at = $(if ($null -ne $rate.last_420_at) { [string]$rate.last_420_at } else { $null })
        minutes_since_last_420 = $minutesSinceLast420
        last_successful_chunk_at = $Script:ForeverState.last_successful_chunk_at
        last_chunk_result = $lastChunkExport
        goal_150k_progress_pct = $goal150
        goal_200k_progress_pct = $goal200
        goal_150k_remaining = [math]::Max(0, $GoalIssuesPrimary - $Script:ForeverState.issues_now)
        goal_200k_remaining = [math]::Max(0, $GoalIssuesStretch - $Script:ForeverState.issues_now)
        average_issues_per_chunk = $avgIssues
        estimated_time_to_150k = (Get-EstimatedTimeTo150k)
        publishers_exhausted = @($publishersExhausted)
        publishers_paused = @($publishersPaused)
        total_chunks_completed = $Script:ForeverState.chunks_completed_this_run
    }
    try {
        $jsonText = ($doc | ConvertTo-Json -Depth 8)
        Set-Content -LiteralPath $ForeverProgressFile -Value $jsonText -Encoding utf8
    } catch {
        Write-Log "forever_progress_json_write_failed=$($_.Exception.Message)" -Level "ERROR"
        throw
    }
    return $doc
}

function Write-ForeverHeartbeat {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$CatalogSnapshot
    )
    $rate = Load-ComicVineRateState
    $last = $Script:ForeverState.last_chunk_result
    $elapsed = Get-ElapsedHours -Since $Script:RunStats.start_time
    Write-Host ""
    Write-Host "P97 FOREVER HEARTBEAT"
    Write-Host "publisher=$($Script:ForeverState.current_publisher)"
    Write-Host "offset=$($Script:ForeverState.current_offset)"
    Write-Host "chunk_limit=$($Script:ForeverState.current_chunk_limit)"
    Write-Host "issues_total=$($CatalogSnapshot.total_issues)"
    Write-Host "images_total=$($CatalogSnapshot.total_images)"
    Write-Host "ready_covers=$($CatalogSnapshot.ready_covers)"
    Write-Host "pending_covers=$($CatalogSnapshot.pending_covers)"
    Write-Host "fingerprints=$($CatalogSnapshot.fingerprints)"
    Write-Host "ocr_rows=$($CatalogSnapshot.ocr_rows)"
    Write-Host "current_sleep_seconds=$($rate.current_sleep_seconds)"
    Write-Host "total_420_count=$($rate.total_420_count)"
    Write-Host "elapsed_hours=$([math]::Round($elapsed, 2))"
    Write-Host "created_this_chunk=$($last.created)"
    Write-Host "updated_this_chunk=$($last.updated)"
    Write-Host "skipped_this_chunk=$($last.skipped)"
    Write-Host "failed_this_chunk=$($last.failed)"
    Write-Host ""
}

function Write-ForeverProgressBlock {
    param(
        [Parameter(Mandatory = $true)][datetime]$StartTime,
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$CatalogSnapshot,
        [Parameter(Mandatory = $true)]$ForeverDoc
    )
    $rate = Load-ComicVineRateState
    $last = $Script:ForeverState.last_chunk_result
    $runtimeText = Format-RuntimeHoursMinutes -TotalHours (Get-ElapsedHours -Since $StartTime)
    Write-Host ""
    Write-Host "P97 FOREVER PROGRESS"
    Write-Host ("-" * 52)
    $naLabel = "N/A"
    $modeText = if ($Script:ForeverMajorOnly) { "FOREVER MAJOR SEQUENTIAL" } else { "FOREVER ALL PUBLISHERS" }
    Write-Host ("Mode: {0}" -f $modeText)
    Write-Host ("Runtime: {0}" -f $runtimeText)
    $currentPub = [string]$Script:ForeverState.current_publisher
    $currentMajor = if ($ForeverMajorPublishers -contains $currentPub) { $currentPub } else { $naLabel }
    $afterMajor = if ($currentMajor -ne $naLabel) { $currentMajor } else { $null }
    $nextMajor = Get-NextForeverMajorPublisher -ProgressDoc $ProgressDoc -PauseState (Load-PublisherPauseState) -AfterPublisher $afterMajor
    Write-Host ("Current Major Publisher: {0}" -f $currentMajor)
    $nextMajorText = if ($nextMajor) { $nextMajor } else { $naLabel }
    Write-Host ("Next Major Publisher: {0}" -f $nextMajorText)
    Write-Host ("Major Phase Complete: {0}" -f (Test-AllForeverMajorPublishersComplete -ProgressDoc $ProgressDoc))
    Write-Host ("Current Publisher: {0}" -f $Script:ForeverState.current_publisher)
    Write-Host "Publisher Offset: $(Format-Count -Value ([int]$Script:ForeverState.current_offset))"
    Write-Host "Chunk Limit: $(Format-Count -Value ([int]$Script:ForeverState.current_chunk_limit))"
    Write-Host "Chunk: $($Script:ForeverState.chunks_completed_this_run) completed this run"
    Write-Host "Issues Before Run: $(Format-Count -Value $Script:ForeverState.issues_before_run)"
    Write-Host "Issues Now: $(Format-Count -Value ([int]$CatalogSnapshot.total_issues))"
    Write-Host "Issues Added This Run: +$(Format-Count -Value $Script:ForeverState.issues_added_this_run)"
    Write-Host "Images Added This Run: +$(Format-Count -Value $Script:ForeverState.images_added_this_run)"
    Write-Host "Ready Covers: $(Format-Count -Value ([int]$CatalogSnapshot.ready_covers))"
    Write-Host "Pending Covers: $(Format-Count -Value ([int]$CatalogSnapshot.pending_covers))"
    Write-Host "Fingerprints: $(Format-Count -Value ([int]$CatalogSnapshot.fingerprints))"
    Write-Host "OCR Rows: $(Format-Count -Value ([int]$CatalogSnapshot.ocr_rows))"
    Write-Host "ComicVine Sleep: $($rate.current_sleep_seconds)s (floor=$($ComicVineForeverMinSleepSeconds)s, downtrim=off)"
    $last420Text = if ($null -ne $rate.last_420_at -and -not [string]::IsNullOrWhiteSpace([string]$rate.last_420_at)) { [string]$rate.last_420_at } else { "N/A" }
    $mins420 = Get-MinutesSinceLast420 -State $rate
    $mins420Text = if ($null -ne $mins420) { "$mins420" } else { "N/A" }
    Write-Host "Last 420 At: $last420Text  (minutes_since_last_420=$mins420Text)"
    Write-Host "420 Count This Run: $($Script:ForeverState.total_420_count_this_run)"
    Write-Host "Last Successful Chunk: $($Script:ForeverState.last_successful_chunk_at)"
    Write-Host "Last Chunk Result: created=$($last.created) updated=$($last.updated) skipped=$($last.skipped) failed=$($last.failed) outcome=$($last.outcome)"
    Write-Host "Status: $($Script:ForeverState.status)"
    Write-Host ""
    Write-Host "Publisher Progress"
    Write-Host ("-" * 52)
    $progressPublishers = if ($Script:ForeverMajorOnly -and -not (Test-AllForeverMajorPublishersComplete -ProgressDoc $ProgressDoc)) {
        $ForeverMajorPublishers
    } else {
        $PublisherTargets
    }
    foreach ($name in $progressPublishers) {
        $row = $Script:ForeverState.publisher_progress[$name]
        Write-Host ("{0,-14} offset={1}  chunks={2}  created={3}  updated={4}  th420={5}  mismatch_chunks={6}  skipped_vol={7}  status={8}" -f `
            $name, (Format-Count -Value ([int]$row.offset)), $row.chunks, $row.created, $row.updated, $row."420s", `
            $row.mismatch_only_chunks, (Format-Count -Value ([int]$row.skipped_mismatch_volumes)), $row.status)
    }
    Write-Host ""
    Write-Host "Catalog Goal Progress"
    Write-Host ("-" * 52)
    Write-Host "Current Issues: $(Format-Count -Value ([int]$CatalogSnapshot.total_issues))"
    Write-Host "Goal: $(Format-Count -Value $GoalIssuesPrimary)"
    Write-Host "Remaining: $(Format-Count -Value ([int]$ForeverDoc.goal_150k_remaining))"
    Write-Host "Progress: $($ForeverDoc.goal_150k_progress_pct)%"
    Write-Host ""
    Write-Host "Stretch Goal: $(Format-Count -Value $GoalIssuesStretch)"
    Write-Host "Remaining: $(Format-Count -Value ([int]$ForeverDoc.goal_200k_remaining))"
    Write-Host "Progress: $($ForeverDoc.goal_200k_progress_pct)%"
    Write-Host ""
    Write-Host "Throughput"
    Write-Host ("-" * 52)
    Write-Host "Issues Added Last Hour: $(Format-Count -Value ([int]$ForeverDoc.issues_added_last_hour))"
    Write-Host "Issues Added This Run: $(Format-Count -Value $Script:ForeverState.issues_added_this_run)"
    Write-Host "Chunks Completed This Run: $($Script:ForeverState.chunks_completed_this_run)"
    Write-Host "Average Issues Per Chunk: $($ForeverDoc.average_issues_per_chunk)"
    Write-Host "Estimated Time To 150k: $($ForeverDoc.estimated_time_to_150k)"
    Write-Host ""
}

function Start-ForeverHeartbeatTimer {
    param(
        [Parameter(Mandatory = $true)][datetime]$StartTime
    )
    if ($WhatIf) { return }
    if ($null -ne $Script:ForeverHeartbeatTimer) { return }
    $Script:ForeverHeartbeatTimer = New-Object System.Timers.Timer
    $Script:ForeverHeartbeatTimer.Interval = ($ForeverHeartbeatSeconds * 1000)
    $Script:ForeverHeartbeatTimer.AutoReset = $true
    Register-ObjectEvent -InputObject $Script:ForeverHeartbeatTimer -EventName Elapsed -SourceIdentifier "P97ForeverHeartbeat" -Action {
        if ($Event.MessageData.Stop) { return }
        $path = $Event.MessageData.ProgressFile
        if (-not (Test-Path -LiteralPath $path)) { return }
        try {
            $doc = Get-Content -LiteralPath $path -Raw -Encoding utf8 | ConvertFrom-Json
            $last = $doc.last_chunk_result
            Write-Host ""
            Write-Host "P97 FOREVER HEARTBEAT"
            Write-Host "publisher=$($doc.current_publisher)"
            Write-Host "offset=$($doc.current_offset)"
            Write-Host "chunk_limit=$($doc.current_chunk_limit)"
            Write-Host "issues_total=$($doc.issues_now)"
            Write-Host "images_total=$($doc.images_now)"
            Write-Host "ready_covers=$($doc.ready_covers)"
            Write-Host "pending_covers=$($doc.pending_covers)"
            Write-Host "fingerprints=$($doc.fingerprints)"
            Write-Host "ocr_rows=$($doc.ocr_rows)"
            Write-Host "current_sleep_seconds=$($doc.current_sleep_seconds)"
            Write-Host "total_420_count=$($doc.total_420_count_this_run)"
            $elapsedHours = ([double]$doc.runtime_seconds) / 3600.0
            Write-Host "elapsed_hours=$([math]::Round($elapsedHours, 2))"
            Write-Host "created_this_chunk=$($last.created)"
            Write-Host "updated_this_chunk=$($last.updated)"
            Write-Host "skipped_this_chunk=$($last.skipped)"
            Write-Host "failed_this_chunk=$($last.failed)"
            Write-Host ""
        } catch {
            # ignore timer read errors
        }
    } -MessageData @{
        ProgressFile = $ForeverProgressFile
        Stop = $false
    } | Out-Null
    $Script:ForeverHeartbeatTimer.Start()
}

function Stop-ForeverHeartbeatTimer {
    if ($null -ne $Script:ForeverHeartbeatTimer) {
        $Script:ForeverHeartbeatTimer.Stop()
        $Script:ForeverHeartbeatTimer.Dispose()
        $Script:ForeverHeartbeatTimer = $null
    }
    Unregister-Event -SourceIdentifier "P97ForeverHeartbeat" -ErrorAction SilentlyContinue
}

function Register-ForeverCancelHandler {
    if ($Script:ForeverCancelHandlerRegistered) { return }
    $Script:ForeverCancelHandlerRegistered = $true
    try {
        [Console]::TreatControlCAsInput = $false
        $handler = [ConsoleCancelEventHandler] {
            param([object]$sender, [ConsoleCancelEventArgs]$e)
            $e.Cancel = $true
            $script:ForeverStopRequested = $true
            $script:interrupted = $true
            if ($Script:ForeverState) { $Script:ForeverState.status = "STOPPING" }
            Write-Log "Ctrl+C received; finishing current work and saving progress..." -Level "WARN"
        }
        [Console]::Add_CancelKeyPress($handler)
    } catch {
        Write-Log "Could not register Ctrl+C handler: $($_.Exception.Message)" -Level "WARN"
    }
}

function Invoke-ForeverPublisherChunk {
    param(
        [Parameter(Mandatory = $true)][string]$PublisherName,
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState
    )
    $entry = $ProgressDoc.publishers[$PublisherName]
    $offset = [int]$entry.last_offset
    $chunkLimit = Get-PublisherChunkLimit -PublisherName $PublisherName
    $Script:ForeverState.current_publisher = $PublisherName
    $Script:ForeverState.current_offset = $offset
    $Script:ForeverState.current_chunk_limit = $chunkLimit
    $Script:RunStats.last_publisher = $PublisherName
    $Script:RunStats.last_offset = $offset

    $wrapped = Invoke-ImportWithThrottle -Label "forever publisher=$PublisherName" -ImportScript {
        Invoke-PublisherImport -PublisherName $PublisherName -Offset $offset -Limit $chunkLimit -ForeverChunk
    }
    $importResult = $wrapped.result
    $maxThrottle = [bool]$importResult.throttled
    $mismatchOnly = ($importResult.skipped_mismatch_only -eq $true)
    if (-not $mismatchOnly) {
        $mismatchOnly = Test-ForeverPublisherMismatchOnlyChunk -ImportResult $importResult
    }

    $created = [int]$importResult.metrics.issues_created
    $updated = [int]$importResult.metrics.issues_updated
    $skippedPublisher = [int]$importResult.metrics.skipped_publisher
    if ($mismatchOnly -and $skippedPublisher -le 0) {
        $skippedPublisher = Count-StrictPublisherMismatchLines -Lines @($importResult.output)
    }
    $skipped = [int]$importResult.metrics.cover_images_skipped + [int]$importResult.metrics.skipped_quality_gate + $skippedPublisher
    $failed = [int]$importResult.metrics.failures
    $chunkOutcome = "ok"
    if ($mismatchOnly) {
        $chunkOutcome = "skipped_mismatch_only"
        $failed = 0
    } elseif ($importResult.exit_code -ne 0 -and -not $maxThrottle) {
        $failed = [math]::Max($failed, 1)
        $chunkOutcome = "failed"
    }

    $Script:ForeverState.last_chunk_result = @{
        created = $created
        updated = $updated
        skipped = $skipped
        failed = $failed
        outcome = $chunkOutcome
    }

    $pubRow = $Script:ForeverState.publisher_progress[$PublisherName]
    if ($null -eq $pubRow.mismatch_only_chunks) { $pubRow.mismatch_only_chunks = 0 }
    if ($null -eq $pubRow.skipped_mismatch_volumes) { $pubRow.skipped_mismatch_volumes = 0 }
    $pubRow."420s" += $(if ($importResult.throttled) { 1 } else { [int]$wrapped.throttle_attempts })

    if ($maxThrottle) {
        Set-PublisherPaused -PauseState $PauseState -PublisherName $PublisherName -Reason "HTTP_420_THROTTLED"
        $pubRow.status = "PAUSED"
        $Script:RunStats.publishers_failed++
        Write-Log "Forever chunk throttled for $PublisherName at sleep floor; publisher paused; offset unchanged at $offset; continuing to next publisher (no global cooldown)" -Level "WARN"
        return
    }

    $entry.last_run_at = (Get-Date).ToUniversalTime().ToString("o")
    $entry.last_exit_code = [int]$importResult.exit_code

    if ($mismatchOnly) {
        $entry.success_count++
        Apply-ForeverPublisherMismatchOnlyOffset -Entry $entry -PubRow $pubRow -OffsetBefore $offset -ChunkLimit $chunkLimit -ImportResult $importResult
        $pubRow.mismatch_only_chunks++
        $pubRow.skipped_mismatch_volumes += $skippedPublisher
        $newOffset = [int]$entry.last_offset
        $totalSeen = [int]$importResult.metrics.total_candidates_seen
        Write-Log ("Forever mismatch-only chunk skipped publisher={0} offset={1}->{2} chunk_limit={3} skipped_publisher={4} total_seen={5}" -f `
            $PublisherName, $offset, $newOffset, $chunkLimit, $skippedPublisher, $totalSeen) -Level "WARN"
        $Script:ForeverState.last_successful_chunk_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        $Script:RunStats.publishers_successful++
        $Script:RunStats.last_offset = $newOffset
    } elseif ($importResult.exit_code -eq 0) {
        $entry.success_count++
        Apply-ForeverPublisherOffsetAfterChunk -Entry $entry -PubRow $pubRow -ImportResult $importResult `
            -PublisherName $PublisherName -OffsetBefore $offset
        $Script:ForeverState.last_successful_chunk_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        $Script:RunStats.publishers_successful++
    } else {
        $entry.failure_count++
        $pubRow.status = "ERROR"
        $Script:RunStats.publishers_failed++
        Write-Log "Forever chunk failed for $PublisherName exit=$($importResult.exit_code)" -Level "WARN"
    }

    $pubRow.chunks++
    $pubRow.created += $created
    $pubRow.updated += $updated
    $Script:ForeverState.chunks_completed_this_run++
    $Script:RunStats.publishers_attempted++
    $Script:RunStats.issues_created_total += $created
    $Script:RunStats.cover_images_created_total += [int]$importResult.metrics.cover_images_created

    Save-ProgressDocument -Progress $ProgressDoc

    if ($mismatchOnly -and $null -ne $Script:ForeverLastCatalogSnapshot -and $null -ne $Script:ForeverDaemonStartTime) {
        try {
            [void](Write-ForeverProgressArtifacts -StartTime $Script:ForeverDaemonStartTime -ProgressDoc $ProgressDoc `
                -PauseState $PauseState -CatalogSnapshot $Script:ForeverLastCatalogSnapshot)
        } catch {
            Write-Log "forever_progress_immediate_flush_failed=$($_.Exception.Message)" -Level "WARN"
        }
    }
}

function Start-ForeverAcquisitionDaemon {
    param(
        [Parameter(Mandatory = $true)][datetime]$StartTime,
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState
    )
    Register-ForeverCancelHandler
    $Script:ForeverMajorOnly = -not $AllPublishers
    if ($Script:ForeverMajorOnly) {
        Write-Log "Forever major-only sequential mode (minors deferred until majors exhausted)"
    } else {
        Write-Log "Forever all-publishers rotation mode (-AllPublishers)"
    }
    $Script:ForeverDaemonStartTime = $StartTime
    Initialize-ComicVineForeverRateState
    $ProgressDoc.series_exhausted = $true
    $ProgressDoc.acquisition_phase = "publisher"
    $Script:RunStats.acquisition_phase = "publisher"
    Save-ProgressDocument -Progress $ProgressDoc

    $catalog = Get-CatalogProgressSnapshot
    $Script:ForeverLastCatalogSnapshot = $catalog
    Initialize-ForeverRunState -StartTime $StartTime -CatalogSnapshot $catalog
    Update-ForeverPublisherProgressFromProgressDoc -ProgressDoc $ProgressDoc -PauseState $PauseState
    Sync-ForeverPublisherRunStatuses -ProgressDoc $ProgressDoc -PauseState $PauseState
    Start-ForeverHeartbeatTimer -StartTime $StartTime

    Write-Log "Forever acquisition daemon started (publisher-only, no enrichment)"
    $foreverDoc = Write-ForeverProgressArtifacts -StartTime $StartTime -ProgressDoc $ProgressDoc -PauseState $PauseState -CatalogSnapshot $catalog
    Write-ForeverProgressBlock -StartTime $StartTime -ProgressDoc $ProgressDoc -CatalogSnapshot $catalog -ForeverDoc $foreverDoc
    Write-ForeverHeartbeat -ProgressDoc $ProgressDoc -CatalogSnapshot $catalog

    while (-not $Script:ForeverStopRequested) {
        $PauseState = Load-PublisherPauseState
        Remove-ExpiredPublisherPauses -PauseState $PauseState
        Sync-ForeverPublisherRunStatuses -ProgressDoc $ProgressDoc -PauseState $PauseState

        $workQueue = Get-ForeverPublisherWorkQueue -ProgressDoc $ProgressDoc
        $selectionOrder = Get-ForeverPublisherSelectionOrder -ProgressDoc $ProgressDoc
        $publisher = Select-ForeverPublisherToRun -ProgressDoc $ProgressDoc -PauseState $PauseState
        if (-not $publisher) {
            $hasEligible = Test-ForeverWorkQueueHasEligiblePublisher -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherNames $selectionOrder
            if ($hasEligible) {
                Write-Log "Forever publisher selector recovered: eligible major exists; re-selecting" -Level "WARN"
                $publisher = Select-ForeverPublisherToRun -ProgressDoc $ProgressDoc -PauseState $PauseState
            }
        }
        if (-not $publisher) {
            $anyNonExhausted = $false
            foreach ($name in $workQueue) {
                $entry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $name
                if (-not (Test-ForeverPublisherExhausted -PublisherEntry $entry)) {
                    $anyNonExhausted = $true
                    break
                }
            }
            if (-not $anyNonExhausted) {
                Write-Log "Forever work queue exhausted; resetting exhausted flags for queue ($($workQueue.Count) publishers)"
                Reset-ForeverPublisherExhaustedFlags -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherNames $workQueue
                $Script:RunStats.publisher_passes++
                Save-ProgressDocument -Progress $ProgressDoc
                Start-Sleep -Seconds 5
                continue
            }
            if (Test-ForeverWorkQueueAllNonExhaustedPaused -ProgressDoc $ProgressDoc -PauseState $PauseState -PublisherNames $selectionOrder) {
                Write-Log "Forever: all non-exhausted publishers paused; waiting 30s before retry" -Level "WARN"
                Start-Sleep -Seconds 30
                continue
            }
            Write-Log "Forever: no publisher selected; retrying immediately" -Level "WARN"
            continue
        }

        while (-not $Script:ForeverStopRequested) {
            $pubEntry = Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $publisher
            if (Test-ForeverPublisherExhausted -PublisherEntry $pubEntry) { break }
            if (Test-PublisherPaused -PauseState $PauseState -PublisherName $publisher) {
                $Script:ForeverState.publisher_progress[$publisher].status = "PAUSED"
                break
            }
            Invoke-ForeverPublisherChunk -PublisherName $publisher -ProgressDoc $ProgressDoc -PauseState $PauseState
            $PauseState = Load-PublisherPauseState
            if ($Script:ForeverState.publisher_progress[$publisher].status -eq "PAUSED") {
                break
            }
            while (
                -not $Script:ForeverStopRequested -and
                $Script:ForeverState.last_chunk_result.outcome -eq "skipped_mismatch_only" -and
                -not (Test-ForeverPublisherExhausted -PublisherEntry (Get-ForeverProgressPublisherEntry -ProgressDoc $ProgressDoc -PublisherName $publisher)) -and
                -not (Test-PublisherPaused -PauseState $PauseState -PublisherName $publisher)
            ) {
                Invoke-ForeverPublisherChunk -PublisherName $publisher -ProgressDoc $ProgressDoc -PauseState $PauseState
                $PauseState = Load-PublisherPauseState
                if ($Script:ForeverState.publisher_progress[$publisher].status -eq "PAUSED") {
                    break
                }
            }
        }

        $catalog = Get-CatalogProgressSnapshot
        $Script:ForeverLastCatalogSnapshot = $catalog
        [void]$Script:ForeverState.issue_samples.Add(@{
            at = (Get-Date).ToUniversalTime().ToString("o")
            issues = [int]$catalog.total_issues
        })
        $foreverDoc = Write-ForeverProgressArtifacts -StartTime $StartTime -ProgressDoc $ProgressDoc -PauseState $PauseState -CatalogSnapshot $catalog
        Write-ForeverProgressBlock -StartTime $StartTime -ProgressDoc $ProgressDoc -CatalogSnapshot $catalog -ForeverDoc $foreverDoc
        Write-ForeverHeartbeat -ProgressDoc $ProgressDoc -CatalogSnapshot $catalog
    }

    Stop-ForeverHeartbeatTimer
    $Script:ForeverState.status = "STOPPED"
    $catalog = Get-CatalogProgressSnapshot
    $null = Write-ForeverProgressArtifacts -StartTime $StartTime -ProgressDoc $ProgressDoc -PauseState $PauseState -CatalogSnapshot $catalog
}

function Show-ForeverWhatIfPlan {
    param(
        [Parameter(Mandatory = $true)]$ProgressDoc,
        [Parameter(Mandatory = $true)]$PauseState
    )
    $rate = Load-ComicVineRateState
    Write-Host "Forever mode enabled"
    if ($AllPublishers) {
        Write-Host "Publisher strategy=ALL (legacy one-chunk rotation across full list)"
    } else {
        Write-Host "Publisher strategy=MAJOR SEQUENTIAL (default; minors after majors exhausted)"
        Write-Host "Major order: $($ForeverMajorPublishers -join ' -> ')"
        Write-Host "Deferred minors: $($ForeverMinorPublishers -join ', ')"
    }
    Write-Host "TargetRuntimeHours=IGNORED MinimumRuntimeHours=IGNORED"
    Write-Host "Enrichment=DISABLED (import only)"
    Write-Host "Lock file=$AcquisitionLockFile"
    Write-Host "Forever progress file=$ForeverProgressFile"
    Write-Host "Publisher pause file=$PublisherPauseStateFile"
    Write-Host "Rate limiter state file=$RateStateFile"
    Write-Host "current_sleep_seconds=$($rate.current_sleep_seconds) total_420_count=$($rate.total_420_count)"
    Write-Host "Forever sleep floor=${ComicVineForeverMinSleepSeconds}s (starts at floor; downtrim/recovery disabled)"
    Write-Host "Publisher queue ($($PublisherTargets.Count)):"
    foreach ($name in $PublisherTargets) {
        $entry = $ProgressDoc.publishers[$name]
        $limit = Get-PublisherChunkLimit -PublisherName $name
        $paused = Test-PublisherPaused -PauseState $PauseState -PublisherName $name
        $pauseText = if ($paused) { "PAUSED" } else { "active" }
        Write-Host ("  {0,-14} chunk_limit={1} offset={2} exhausted={3} {4}" -f `
            $name, $limit, $entry.last_offset, $entry.publisher_exhausted, $pauseText)
    }
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
    Write-Host "ComicVineBaseSleepSeconds=$ComicVineBaseSleepSeconds"
    Write-Host "AdaptiveRateLimiter=enabled"
    Write-Host "RateStatePath=data/p97/comicvine_rate_state.json"
    Write-Host "Progress file=$ProgressFile"
    Write-Host "Log file=$LogFile"
    Write-Host "Summary file=$SummaryFile"
    Write-Host "First 20 planned series:"
    $SeriesTargets | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
    $exampleSleep = Format-ComicVineSleepSeconds -Seconds $ComicVineBaseSleepSeconds
    Write-Host "Example series import command:"
    Write-Host "  python scripts\p97_import_comicvine_catalog.py --series-name `"$($SeriesTargets[0])`" --limit $PerSeriesLimit --offset 0 --import-issues --sleep-seconds $exampleSleep --resume"
    Write-Host "Example publisher import command (after series exhausted):"
    Write-Host "  python scripts\p97_import_comicvine_catalog.py --publisher `"$($PublisherTargets[0])`" --strict-publisher --limit $PerSeriesLimit --offset 0 --import-issues --sleep-seconds $exampleSleep --resume"
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
    $validationSleep = Format-ComicVineSleepSeconds -Seconds $ComicVineBaseSleepSeconds
    $validationArgs = @("scripts\p97_import_comicvine_catalog.py", "--series-name", "Spawn", "--limit", "1", "--dry-run", "--sleep-seconds", $validationSleep)
    Write-Log ("  > python " + ($validationArgs -join " "))
    $run = Invoke-ExternalPython -ArgumentList $validationArgs -Label "ComicVine API validation" -StrictFailure
    $exitCode = $run.exit_code
    $blob = ($run.output -join "`n")
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
        if (-not $Forever) {
            throw "TESSERACT_CMD not found on disk: $($env:TESSERACT_CMD)"
        }
        Write-Log "  (Forever mode: TESSERACT_CMD not required for import-only acquisition)" -Level "INFO"
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

    if ($WhatIf -and -not $Forever) { Show-WhatIfPlan }

    $Script:InSafetyBootstrap = $true
    Test-SafetyChecks
    Initialize-ComicVineApiKey
    Test-ComicVineApiKeyConfigured
    Write-ComicVineKeyStatus
    if (-not $WhatIf) {
        Test-ComicVineApiAccess
    } else {
        Write-Log "(WhatIf: skipping ComicVine API validation call)"
    }
    $Script:InSafetyBootstrap = $false

    if ($TestImportHelper) {
        Write-Log "TestImportHelper: Batman limit 10 via Invoke-SeriesImport (adaptive sleep)"
        $testResult = Invoke-SeriesImport -SeriesName "Batman" -Offset 0 -Limit 10
        Write-Host "TestImportHelper exit_code=$($testResult.exit_code)"
        exit [int]$testResult.exit_code
    }

    $Progress = Load-ProgressDocument
    $pauseState = Load-PublisherPauseState

    if ($Forever) {
        Write-Log "Forever catalog acquisition mode (WhatIf=$WhatIf)"
        if ($WhatIf) {
            Show-ForeverWhatIfPlan -ProgressDoc $Progress -PauseState $pauseState
            Write-Log "WhatIf: forever mode plan shown; no imports executed."
        } else {
            Acquire-AcquisitionRunnerLock
            try {
                Start-ForeverAcquisitionDaemon -StartTime $StartTime -ProgressDoc $Progress -PauseState $pauseState
            } finally {
                Stop-ForeverHeartbeatTimer
                Release-AcquisitionRunnerLock
            }
        }
    } else {
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

    if (-not $WhatIf -and -not $Forever) {
        Invoke-PostProcessing -Reason "final checkpoint at target runtime"
        $lastPostProcessingAt = Get-Date
    }
    }

} catch {
    $interrupted = $true
    Write-Log $_.Exception.Message -Level "ERROR"
    if ($Script:InSafetyBootstrap) {
        Write-Error $_.Exception.Message
        exit 1
    }
    Write-Log "Unexpected error during acquisition loop; progress JSON will be saved in finally." -Level "ERROR"
} finally {
    if ($Forever -and -not $WhatIf) {
        Stop-ForeverHeartbeatTimer
        Release-AcquisitionRunnerLock
    }
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
        } elseif ($Forever) {
            Write-Log "(Forever mode: skipping p97_catalog_health.py on shutdown; use p97_forever_progress_watch.py)"
        } else {
            Write-Log "Running catalog health report"
            $healthRun = Invoke-ExternalPython -ArgumentList @($healthScript) -Label "catalog health"
            if ($healthRun.exit_code -ne 0) {
                Write-Log "catalog health exited $($healthRun.exit_code)" -Level "WARN"
            }
        }
    }

    if ($WhatIf) {
        Write-Log "WhatIf complete - no imports or post-processing were executed."
    } elseif ($Forever) {
        Write-Log "Forever acquisition stopped; progress and summary saved."
    }
}

exit 0
