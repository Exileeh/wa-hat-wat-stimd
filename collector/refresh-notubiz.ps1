# refresh-notubiz.ps1 - weekly local refresh of the four Notubiz provinces.
#
# Why this runs on a home PC: api.notubiz.nl silently drops connections from GitHub's cloud runners
# (geo-IP / datacenter filtering; Notubiz makes no exceptions, 2026-09) but accepts this connection.
# Started by Windows Task Scheduler, task "wie-stemde-wat Notubiz refresh". Background and the
# diagnosis: coverage.md "Status van de bronnen", outreach.md section 5.
#
# It commits ONLY the four province files. The weekly GitHub run never writes those while it is
# blocked (its guard keeps the existing files) and owns catalog.json, so the two cannot conflict.
# If this stops working, nothing breaks silently: after 45 days the GitHub run goes red.

$ErrorActionPreference = 'Continue'
# Python prints UTF-8 (PYTHONUTF8 below); without this Windows PowerShell decodes it with the console's
# code page and the log shows mojibake for dashes and accents.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Provinces = @('zuid-holland', 'fryslan', 'gelderland', 'overijssel')
$Repo      = Split-Path -Parent $PSScriptRoot
$Python    = 'C:\Users\Thabi\AppData\Local\Programs\Python\Python313\python.exe'
$Git       = 'C:\Program Files\Git\cmd\git.exe'
$LogDir    = Join-Path $env:LOCALAPPDATA 'wie-stemde-wat'
$Log       = Join-Path $LogDir 'refresh-notubiz.log'
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
    # Keep the log from growing forever: the last ~3000 lines is months of weekly runs.
    $lines = @(Get-Content -Path $Log -Encoding utf8)
    if ($lines.Count -gt 3000) { $lines[-3000..-1] | Set-Content -Path $Log -Encoding utf8 }
    exit $Code
}

Set-Location $Repo
Write-Log "=== start"

# Never touch work in progress: uncommitted changes, or local commits not yet on GitHub (pushing
# would publish them).
if (& $Git status --porcelain) {
    Write-Log "skipped: the repo has uncommitted changes"
    Exit-Run 0
}
if ((Invoke-Logged $Git @('pull', '--ff-only', '-q')) -ne 0) {
    Write-Log "skipped: git pull failed (offline, or local history diverged)"
    Exit-Run 1
}
if ([int](& $Git rev-list --count 'origin/main..HEAD') -gt 0) {
    Write-Log "skipped: there are local commits that are not on GitHub yet"
    Exit-Run 0
}

$env:ONLY = $Provinces -join ','
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$collectorCode = Invoke-Logged $Python @('-u', 'collector/collect.py')
Remove-Item Env:ONLY
Write-Log "collector finished (exit $collectorCode)"

# An ONLY run also rewrites catalog.json; that file belongs to the GitHub run.
& $Git checkout -q -- data/catalog.json

$files = $Provinces | ForEach-Object { "data/$_.json" }
& $Git add -- $files
& $Git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log "no changes to commit"
    Exit-Run $collectorCode
}

$commitArgs = @('commit', '-q', '-m', 'chore: refresh Notubiz provinces (local run)',
                '-m', "Collected from a home connection: api.notubiz.nl blocks GitHub's cloud runners.")
if ((Invoke-Logged $Git $commitArgs) -ne 0) {
    Write-Log "commit failed"
    Exit-Run 1
}

for ($attempt = 1; $attempt -le 3; $attempt++) {
    if ((Invoke-Logged $Git @('push', '-q', 'origin', 'main')) -eq 0) {
        Write-Log "pushed"
        Exit-Run $collectorCode
    }
    # The GitHub run pushed in the meantime. It never touches these four files, so a rebase is clean.
    Write-Log "push rejected (attempt $attempt): rebasing onto GitHub's latest"
    if ((Invoke-Logged $Git @('pull', '--rebase', '-q')) -ne 0) {
        & $Git rebase --abort 2>&1 | Out-Null
        & $Git reset -q --hard 'HEAD~1'   # drop only this run's commit; next week's run retries
        Write-Log "rebase conflict: dropped this run's commit, will retry next run"
        Exit-Run 1
    }
}
# Do not leave the commit behind: the next run would then see an unpushed commit and skip forever.
& $Git reset -q --hard 'HEAD~1'
Write-Log "push failed 3 times: dropped this run's commit, will retry next run"
Exit-Run 1
