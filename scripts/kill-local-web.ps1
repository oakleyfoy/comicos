$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$port = 5173
$killedAny = $false

while ($true) {
    $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    $liveProcesses = @(
        $connections |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue } |
        Where-Object { $null -ne $_ }
    )

    if ($liveProcesses.Count -eq 0) {
        break
    }

    foreach ($process in $liveProcesses) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Killed web listener PID $($process.Id) ($($process.ProcessName)) on port $port." -ForegroundColor Green
        $killedAny = $true
    }

    Start-Sleep -Milliseconds 250
}

if (-not $killedAny) {
    Write-Host "No local web listener found on port $port." -ForegroundColor Yellow
}
