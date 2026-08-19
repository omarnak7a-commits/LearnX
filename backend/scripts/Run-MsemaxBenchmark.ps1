<#
.SYNOPSIS
    Drive the real STEP 9 MSEMAX A/B benchmark against a deployed LearnX
    instance from Windows PowerShell.

.DESCRIPTION
    Everything runs server-side. This script only holds the deployment URL and
    BENCHMARK_TOKEN; it never sees, sends, or needs GEMINI_API_KEY or
    GROQ_API_KEY, which stay in the Vercel environment and are read by the
    server at call time.

    The benchmark is deliberately split into many short requests. vercel.json
    uses the legacy "builds" property, so functions.maxDuration cannot be set
    and the platform default (10-15s) applies, while a single provider call can
    take up to AI_TIMEOUT_SECONDS. Each request therefore phrases only a few
    blueprints and persists them; this script simply calls the resumable
    endpoint until the run is complete (~202 requests for the full matrix).

    Safe to stop with Ctrl+C and re-run with -RunId: progress lives in the
    server's database, completed work is never repeated and never duplicated.

    Requires PowerShell 5.1 (Windows built-in) or PowerShell 7+. No Python, no
    git, and no repository checkout are needed - this single file is enough.

.PARAMETER BaseUrl
    Deployment origin, e.g. https://learn-x-ofvm.vercel.app

.PARAMETER Token
    The BENCHMARK_TOKEN configured in Vercel. Defaults to $env:BENCHMARK_TOKEN.
    This is NOT a provider API key.

.PARAMETER RunId
    Resume an existing run instead of starting a new one.

.EXAMPLE
    $env:BENCHMARK_TOKEN = "<benchmark token from Vercel>"
    .\Run-MsemaxBenchmark.ps1 -BaseUrl "https://learn-x-ofvm.vercel.app"

.EXAMPLE
    # resume after an interruption
    .\Run-MsemaxBenchmark.ps1 -BaseUrl "https://learn-x-ofvm.vercel.app" -RunId "abc-123"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $BaseUrl,

    [string] $Token = $env:BENCHMARK_TOKEN,

    [string] $RunId = "",

    [string] $ApiPrefix = "/api/v1",

    [string] $OutFile = "QUIZ_MSEMAX_AB.json",

    # Generous per-request timeout: the server bounds its own work, this only
    # guards against a hung connection.
    [int] $TimeoutSec = 120,

    # Safety stop so a bug can never loop forever. ~202 requests are expected
    # for the full 8-document x 5-seed matrix.
    [int] $MaxRequests = 4000,

    # Retries for transient network/5xx failures on a single request. The run
    # itself is resumable regardless, this just avoids needless restarts.
    [int] $RetryAttempts = 5,

    # Run only the single-call provider pre-flight and exit. Use this first.
    [switch] $CheckOnly,

    # Skip the pre-flight (not recommended: a misconfigured provider would
    # otherwise only be discovered after hundreds of failed calls).
    [switch] $SkipCheck
)

# NOTE: Set-StrictMode is deliberately NOT enabled. The API returns optional
# fields (batch.error, report.note) that are absent on the happy path, and
# strict mode would turn those normal absences into terminating errors.
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($Token)) {
    throw @"
BENCHMARK_TOKEN is not set.

Set the benchmark token you configured in Vercel:
    `$env:BENCHMARK_TOKEN = "<your benchmark token>"

This is the benchmark authorisation secret - NOT a Gemini or Groq API key.
Provider keys stay in Vercel and are never needed here.
"@
}

# Windows PowerShell 5.1 may still default to TLS 1.0/1.1, which modern hosts
# reject outright. Opt in to TLS 1.2 before the first request.
try {
    if ([Net.ServicePointManager]::SecurityProtocol -notmatch 'Tls12') {
        [Net.ServicePointManager]::SecurityProtocol = `
            [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    }
}
catch {
    Write-Verbose "Could not adjust TLS settings: $($_.Exception.Message)"
}

$script:api = $BaseUrl.TrimEnd('/') + $ApiPrefix
# The token is sent as a header only. It is never written to the console, to
# the results file, or to any log by this script.
$script:headers = @{ 'X-Benchmark-Token' = $Token }

function Get-StatusCode {
    param([object] $ErrorRecord)
    $response = $ErrorRecord.Exception.Response
    if ($null -eq $response) { return 0 }
    try { return [int] $response.StatusCode }
    catch { return 0 }
}

function Invoke-Api {
    param(
        [string] $Method,
        [string] $Path,
        [object] $Body = $null
    )
    $uri = "$($script:api)$Path"
    $attempt = 0
    while ($true) {
        $attempt++
        try {
            if ($null -ne $Body) {
                return Invoke-RestMethod -Method $Method -Uri $uri -Headers $script:headers `
                    -ContentType 'application/json' `
                    -Body ($Body | ConvertTo-Json -Compress) -TimeoutSec $TimeoutSec
            }
            return Invoke-RestMethod -Method $Method -Uri $uri -Headers $script:headers `
                -TimeoutSec $TimeoutSec
        }
        catch {
            # Capture the record immediately: $_ is rebound by nested constructs.
            $err = $_
            $status = Get-StatusCode -ErrorRecord $err

            # Permanent, actionable failures - never retry these.
            if ($status -eq 401) {
                throw "401 Unauthorized from $uri. The BENCHMARK_TOKEN sent does not match the one configured in Vercel."
            }
            if ($status -eq 404) {
                throw "404 from $uri. Either BENCHMARK_TOKEN is not configured on the server (the benchmark routes are only mounted when it is set), or the deployment has not picked up the new build yet, or this run id does not exist."
            }
            if ($status -eq 400 -or $status -eq 422) {
                throw ("{0} from {1}: {2}" -f $status, $uri, $err.ErrorDetails.Message)
            }

            # Transient: connection failures (status 0), throttling, 5xx,
            # and Vercel cold-start/timeout responses.
            $transient = ($status -eq 0) -or ($status -eq 408) -or ($status -eq 429) -or ($status -ge 500)
            if ($transient -and $attempt -lt $RetryAttempts) {
                $delay = [int] [Math]::Min(30, [Math]::Pow(2, $attempt))
                Write-Host ("  transient failure (status {0}, attempt {1}/{2}) - retrying in {3}s" -f `
                        $status, $attempt, $RetryAttempts, $delay) -ForegroundColor DarkYellow
                Start-Sleep -Seconds $delay
                continue
            }

            if ($status -eq 503) {
                throw "503 from $uri after $attempt attempts. Most likely MSEMAX is enabled but no provider credentials are readable in this deployment. Check that GEMINI_API_KEY / GROQ_API_KEY exist in the Vercel environment - do not copy them here."
            }
            throw ("Request to {0} failed after {1} attempt(s) (status {2}): {3}" -f `
                    $uri, $attempt, $status, $err.Exception.Message)
        }
    }
}

Write-Host "MSEMAX STEP 9 benchmark" -ForegroundColor Cyan
Write-Host "  target : $($script:api)"
Write-Host "  auth   : X-Benchmark-Token (provider keys stay in Vercel)"
Write-Host ""

if (-not $SkipCheck) {
    Write-Host "pre-flight: one real provider call..." -ForegroundColor Cyan
    $check = Invoke-Api -Method 'Post' -Path '/benchmark/provider-check'
    Write-Host ("  primary   : {0} ({1})  key present: {2}" -f `
            $check.primary, $check.gemini_model, $check.credentials_present.gemini)
    Write-Host ("  fallback  : {0} ({1})  key present: {2}" -f `
            $check.fallback, $check.groq_model, $check.credentials_present.groq)
    if (-not $check.ok) {
        Write-Host ("  FAILED    : {0}" -f $check.category) -ForegroundColor Red
        Write-Host ("  diagnosis : {0}" -f $check.diagnosis) -ForegroundColor Red
        Write-Host ""
        switch ($check.category) {
            'authentication' {
                Write-Host "Fix: the provider key in Vercel is missing, expired or revoked. Rotate it in the Vercel dashboard and redeploy. Do not paste it anywhere else." -ForegroundColor Yellow
            }
            'model_not_found' {
                Write-Host "Fix: the configured model no longer exists. Set GEMINI_MODEL / GROQ_MODEL in Vercel to a current model and redeploy." -ForegroundColor Yellow
            }
            'quota_rate_limit' {
                Write-Host "Fix: quota or rate limit reached. Wait, or raise the provider quota, then retry." -ForegroundColor Yellow
            }
            'configuration' {
                Write-Host "Fix: no provider credentials are set in this deployment's environment." -ForegroundColor Yellow
            }
            default {
                Write-Host "Resolve the issue above before running the benchmark." -ForegroundColor Yellow
            }
        }
        throw "Provider pre-flight failed ($($check.category)). Not starting the benchmark."
    }
    Write-Host ("  OK        : {0} via {1} (fallback_used={2})" -f `
            $check.model_used, $check.provider_used, $check.fallback_used) -ForegroundColor Green
    Write-Host ""
}

if ($CheckOnly) {
    Write-Host "pre-flight only; not starting a run." -ForegroundColor Cyan
    return
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $start = Invoke-Api -Method 'Post' -Path '/benchmark/runs' `
        -Body @{ seeds = @(1, 3, 5, 7, 11); count = 8 }
    $RunId = $start.run_id
    Write-Host ("started run {0}: {1} units" -f $RunId, $start.total_batches) -ForegroundColor Green
}
else {
    Write-Host "resuming run $RunId" -ForegroundColor Green
}
Write-Host "  (safe to Ctrl+C; resume with -RunId $RunId)"
Write-Host ""

$requests = 0
$finished = $false
$startedAt = Get-Date

while ($requests -lt $MaxRequests) {
    $requests++
    $step = Invoke-Api -Method 'Post' -Path "/benchmark/runs/$RunId/next"
    $progress = $step.progress

    if ($null -eq $step.batch) {
        $finished = $true
        Write-Host "all units complete" -ForegroundColor Green
        break
    }

    $batch = $step.batch
    if ($batch.status -eq 'completed' -or $batch.status -eq 'failed') {
        $colour = 'Gray'
        if ($batch.status -eq 'failed') { $colour = 'Yellow' }
        Write-Host ("  [{0,-9}] {1,-30} seed {2,-3} baseline={3}Q msemax={4}Q accepted={5}/{6}  ({7}/{8} units)" -f `
                $batch.status, $batch.document, $batch.seed, `
                $batch.baseline_questions, $batch.msemax_questions, `
                $batch.generations_accepted, $batch.generations_requested, `
                $progress.completed, $progress.total_batches) -ForegroundColor $colour
        if ($batch.error) {
            Write-Host ("             error: {0} (this unit stays retryable)" -f $batch.error) -ForegroundColor Yellow
        }
    }
    elseif (($requests % 10) -eq 0) {
        # Heartbeat during the ~162 phrasing requests so a long run never looks
        # frozen. Each of these persists a few phrasings server-side.
        $elapsed = [int] ((Get-Date) - $startedAt).TotalSeconds
        Write-Host ("  phrasing... {0} requests, {1}/{2} units done, {3}s elapsed" -f `
                $requests, $progress.completed, $progress.total_batches, $elapsed) -ForegroundColor DarkGray
    }

    if ($progress.remaining -le 0) {
        $finished = $true
        Write-Host "all units complete" -ForegroundColor Green
        break
    }
}

if (-not $finished) {
    Write-Warning "Stopped after $requests requests without finishing. Re-run with -RunId $RunId to continue; completed units will not be repeated."
}

Write-Host ""
$report = Invoke-Api -Method 'Get' -Path "/benchmark/runs/$RunId/report"

$json = $report | ConvertTo-Json -Depth 20
if ([System.IO.Path]::IsPathRooted($OutFile)) {
    $outPath = $OutFile
}
else {
    $outPath = Join-Path (Get-Location).Path $OutFile
}
# UTF8 without BOM: a BOM breaks strict JSON parsers, and this file gets read
# back as data. Set-Content -Encoding UTF8 emits a BOM on PowerShell 5.1.
[System.IO.File]::WriteAllText($outPath, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "report written to $outPath" -ForegroundColor Cyan

if ($report.status -ne 'completed') {
    Write-Host ("STATUS: {0} - {1}" -f $report.status, $report.note) -ForegroundColor Yellow
    Write-Host "No A/B comparison is produced until every unit has finished."
    Write-Host "Re-run with -RunId $RunId to finish the remaining units."
    return
}

$b = $report.baseline
$m = $report.msemax
Write-Host ""
Write-Host ("{0,-26} {1,12} {2,12}" -f 'metric', 'baseline', 'MSEMAX') -ForegroundColor Cyan
Write-Host ("-" * 52)
foreach ($row in @(
        @{ label = 'questions'; key = 'questions' },
        @{ label = 'concepts'; key = 'concepts' },
        @{ label = 'tier 1'; key = 'tier1' },
        @{ label = 'scanner defects'; key = 'scanner_defects' },
        @{ label = 'scanner warnings'; key = 'scanner_warnings' },
        @{ label = 'candidate survival'; key = 'candidate_survival' },
        @{ label = 'silent candidate loss'; key = 'silent_candidate_loss' },
        @{ label = 'latency (s)'; key = 'latency_seconds' }
    )) {
    Write-Host ("{0,-26} {1,12} {2,12}" -f $row.label, $b.($row.key), $m.($row.key))
}
Write-Host ("-" * 52)
Write-Host ("MSEMAX accepted : {0}/{1} (rate {2})" -f `
        $m.generations_accepted, $m.generations_requested, $m.valid_rate)
Write-Host ("provider errors : {0}" -f $m.provider_errors)
Write-Host ""
Write-Host "Send $OutFile back for the STEP 10 promotion analysis." -ForegroundColor Cyan
