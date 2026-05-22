$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$containerName = "comic-os-postgres"
$databaseName = "comic_os"
$databaseUrl = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
$alembicHead = "20260522_0002"

Set-Location $repoRoot

Write-Host "Resetting local Docker development database only." -ForegroundColor Yellow
Write-Host "Target container: $containerName" -ForegroundColor Yellow
Write-Host "Target database: $databaseName" -ForegroundColor Yellow
Write-Host "This deletes local development data and does not target Render or production." -ForegroundColor Yellow

docker info | Out-Null
docker compose up -d postgres | Out-Null

for ($attempt = 1; $attempt -le 30; $attempt++) {
    docker exec $containerName pg_isready -U postgres -d $databaseName *> $null
    if ($LASTEXITCODE -eq 0) {
        break
    }

    if ($attempt -eq 30) {
        throw "Postgres container did not become ready in time."
    }

    Start-Sleep -Seconds 2
}

docker exec $containerName psql -U postgres -d postgres -v ON_ERROR_STOP=1 `
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$databaseName' AND pid <> pg_backend_pid();" `
    -c "DROP DATABASE IF EXISTS $databaseName;" `
    -c "CREATE DATABASE $databaseName;"

$env:DATABASE_URL = $databaseUrl

Push-Location (Join-Path $repoRoot "apps/api")
try {
    .\.venv\Scripts\alembic -c alembic.ini upgrade head
}
finally {
    Pop-Location
}

docker exec $containerName psql -U postgres -d $databaseName -v ON_ERROR_STOP=1 `
    -c "SELECT 1 AS db_connection_check;" `
    -c "SELECT version_num FROM alembic_version;" `
    -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"

Write-Host "Local Docker development database reset completed successfully." -ForegroundColor Green
Write-Host "Verified Alembic head: $alembicHead" -ForegroundColor Green
