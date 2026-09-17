# refresh-local.ps1 - refresh the Fryslân voting data from a machine that CAN reach Notubiz.
#
# Why this exists: api.notubiz.nl silently drops connections from GitHub's cloud runners
# (geo-IP / datacenter filtering; no exceptions, 2026-09). A Dutch connection works. Run this
# manually, or daily via Windows Task Scheduler:
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<repo>\collector\refresh-local.ps1"
# It commits and pushes ONLY data/fryslan.json and data/roles.json.
#
# Requirements: python (3.10+) and git on PATH, and push rights to the repo (credential manager).

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Repo   = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $env:LOCALAPPDATA 'wa-hat-wat-stimd'
$Log    = Join-Path $LogDir 'refresh-local.log'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log([string]$Message) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message" | Out-File -FilePath $Log -Append -Encoding utf8
}

# Run a program, append its output to the log, return its exit code.
function Invoke-Logged([string]$Exe, [string[]]$Arguments) {
    $output = & $Exe @Arguments 2>&1 | ForEach-Object { "    $_" }
    $code = $LASTEXITCODE
    if ($output) { $output | Out-File -FilePath $Log -Append -Encoding utf8 }
    return $code
}

function Exit-Run([int]$Code) {
    Write-Log "=== end (exit $Code)"
    $lines = @(Get-Content -Path $Log -Encoding utf8)
    if ($lines.Count -gt 3000) { $lines[-3000..-1] | Set-Content -Path $Log -Encoding utf8 }
    exit $Code
}

Set-Location $Repo
Write-Log "=== start"

# Never touch work in progress: uncommitted changes, or local commits not yet on GitHub.
if (& git status --porcelain) {
    Write-Log "skipped: the repo has uncommitted changes"
    Exit-Run 0
}
if ((Invoke-Logged 'git' @('pull', '--ff-only', '-q')) -ne 0) {
    Write-Log "skipped: git pull failed (offline, or local history diverged)"
    Exit-Run 1
}
if ([int](& git rev-list --count 'origin/main..HEAD') -gt 0) {
    Write-Log "skipped: there are local commits that are not on GitHub yet"
    Exit-Run 0
}

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$collectorCode = Invoke-Logged 'python' @('-u', 'collector/collect.py')
Write-Log "collector finished (exit $collectorCode)"

$files = @('data/fryslan.json', 'data/roles.json')
& git add -- $files
& git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log "no changes to commit"
    Exit-Run $collectorCode
}

if ((Invoke-Logged 'git' @('commit', '-q', '-m', 'chore: ververs stemdata Fryslân (lokale run)')) -ne 0) {
    Write-Log "commit failed"
    Exit-Run 1
}

for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ((Invoke-Logged 'git' @('push', '-q', 'origin', 'main')) -eq 0) {
        Write-Log "pushed"
        Exit-Run $collectorCode
    }
    Write-Log "push rejected (attempt $attempt): rebasing onto GitHub's latest"
    if ((Invoke-Logged 'git' @('pull', '--rebase', '-q')) -ne 0) {
        & git rebase --abort 2>&1 | Out-Null
        & git reset -q --hard 'HEAD~1'
        Write-Log "rebase conflict: dropped this run's commit, will retry next run"
        Exit-Run 1
    }
}
& git reset -q --hard 'HEAD~1'
Write-Log "push failed 3 times: dropped this run's commit, will retry next run"
Exit-Run 1
