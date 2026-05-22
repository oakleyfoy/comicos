$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$port = 8000
$killedAny = $false

while ($true) {
    $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    $owningProcessIds = @(
        $connections |
        Select-Object -ExpandProperty OwningProcess -Unique |
        Where-Object { $_ -gt 0 }
    )
    $liveProcesses = @(
        $owningProcessIds |
        ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue } |
        Where-Object { $null -ne $_ }
    )
    $orphanedChildren = @()

    if ($owningProcessIds.Count -gt 0) {
        $orphanedChildren = @(
            Get-CimInstance Win32_Process |
            Where-Object { $owningProcessIds -contains $_.ParentProcessId }
        )
    }

    if ($liveProcesses.Count -eq 0 -and $orphanedChildren.Count -eq 0) {
        break
    }

    foreach ($process in $liveProcesses) {
        taskkill /PID $process.Id /T /F | Out-Null
        Write-Host "Killed API listener tree PID $($process.Id) ($($process.ProcessName)) on port $port." -ForegroundColor Green
        $killedAny = $true
    }

    foreach ($child in $orphanedChildren) {
        taskkill /PID $child.ProcessId /T /F | Out-Null
        Write-Host "Killed orphaned API child PID $($child.ProcessId) from listener parent PID $($child.ParentProcessId)." -ForegroundColor Green
        $killedAny = $true
    }

    Start-Sleep -Milliseconds 250
}

if (-not $killedAny) {
    Write-Host "No local API listener found on port $port." -ForegroundColor Yellow
}
