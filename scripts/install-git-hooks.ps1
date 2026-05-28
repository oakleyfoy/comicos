Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$hooksDir = (git -C $repoRoot rev-parse --git-path hooks).Trim()
if (-not $hooksDir) {
    throw "Unable to resolve the git hooks directory."
}
if (-not [System.IO.Path]::IsPathRooted($hooksDir)) {
    $hooksDir = Join-Path $repoRoot $hooksDir
}
$hooksDir = [System.IO.Path]::GetFullPath($hooksDir)
New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null

$sourceHook = Join-Path $repoRoot ".githooks\pre-push"
$targetHook = Join-Path $hooksDir "pre-push"

Copy-Item -LiteralPath $sourceHook -Destination $targetHook -Force

Write-Host "Installed pre-push hook to $targetHook"
