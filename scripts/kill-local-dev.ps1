$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptRoot = $PSScriptRoot

Write-Host "Cleaning local API and web listeners..." -ForegroundColor Cyan

& (Join-Path $scriptRoot "kill-local-api.ps1")
& (Join-Path $scriptRoot "kill-local-web.ps1")

Write-Host "Local dev listener cleanup finished." -ForegroundColor Green
