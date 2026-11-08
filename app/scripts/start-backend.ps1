param(
    [switch]$Protected,
    [string]$FrontendOrigin = 'https://sonnfeld-reo.vercel.app',
    [ValidateRange(1, 20)][int]$MaxActiveSessions = 5,
    [ValidateRange(1, 4)][int]$MaxAgentRuns = 2
)
# Start the existing Python services on loopback only. Does not expose a public tunnel.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtimeDir = Join-Path $repoRoot 'app/.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
if ($Protected) {
    $tokenFile = Join-Path $runtimeDir 'installer-token.txt'
    if (-not (Test-Path -LiteralPath $tokenFile)) {
        # 16 random base32 characters (80 bits), grouped for easy entry; omit ambiguous I/O/0/1.
        $alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        $groups = 1..4 | ForEach-Object { -join (1..4 | ForEach-Object { $alphabet[[System.Security.Cryptography.RandomNumberGenerator]::GetInt32($alphabet.Length)] }) }
        $tokenValue = $groups -join '-' 
        [System.IO.File]::WriteAllText($tokenFile, $tokenValue)
    }
    $env:REO_INSTALLER_TOKEN = [System.IO.File]::ReadAllText($tokenFile).Trim()
    if ($env:REO_INSTALLER_TOKEN.Length -lt 19) { throw 'Installer token file is empty or too short.' }
    $env:REO_ALLOWED_ORIGINS = $FrontendOrigin
    $demoPinFile = Join-Path $runtimeDir 'demo-pin.txt'
    if (Test-Path -LiteralPath $demoPinFile) {
        $env:REO_DEMO_PIN = [System.IO.File]::ReadAllText($demoPinFile).Trim()
        if (-not $env:REO_DEMO_PIN) { throw 'Demo PIN file is empty.' }
        $env:REO_MAX_ACTIVE_SESSIONS = [string]$MaxActiveSessions
        $env:REO_MAX_CONCURRENT_RUNS = [string]$MaxAgentRuns
    }
}


foreach ($service in @(@{Name='engine';Port=8000}, @{Name='reo';Port=8001})) {
    $healthUrl = "http://127.0.0.1:$($service.Port)/health"
    try {
        $health = Invoke-RestMethod $healthUrl -TimeoutSec 3
        if ($health.ok) {
            if ($Protected -and $service.Name -eq 'reo') {
                $protectedStatus = (Invoke-WebRequest 'http://127.0.0.1:8001/plans' -SkipHttpErrorCheck).StatusCode
                if ($protectedStatus -ne 401) { throw 'Existing reo has no installer access guard. Restart it before protected startup.' }
                if ($env:REO_DEMO_PIN -and -not $health.demo_auth_required) { throw 'Existing reo does not enforce the requested demo PIN. Restart it with this configuration.' }
                $authHeaders = @{Authorization="Bearer $env:REO_INSTALLER_TOKEN"}
                if ($env:REO_DEMO_PIN) { $authHeaders['X-Demo-Pin'] = $env:REO_DEMO_PIN }
                if ($env:REO_DEMO_PIN) {
                    $pinOnly = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -Headers @{'X-Demo-Pin'=$env:REO_DEMO_PIN} -SkipHttpErrorCheck
                    if ($pinOnly.StatusCode -ne 401) { throw 'Existing reo does not require the separate planner token.' }
                }
                $checkToken = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -Headers $authHeaders -SkipHttpErrorCheck
                if ($checkToken.StatusCode -ne 200) { throw 'Existing reo uses a different installer token. Restart with this configuration.' }
            }
            Write-Host "$($service.Name) already healthy on $($service.Port); reusing it."; continue }
    } catch { if ($_.Exception.Message -match 'Existing reo') { throw } }
    $serviceDir = Join-Path $repoRoot $service.Name
    $pythonExe = Join-Path $serviceDir '.venv/Scripts/python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Missing $pythonExe. Run uv sync in $serviceDir first." }
    $listener = Get-NetTCPConnection -LocalPort $service.Port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $($service.Port) is occupied by an unhealthy or different service. Inspect it before restarting." }
    $started = Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','api:app','--host','127.0.0.1','--port', $service.Port) -WorkingDirectory $serviceDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir "$($service.Name).out.log") -RedirectStandardError (Join-Path $runtimeDir "$($service.Name).err.log")
    $healthy = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ($started.HasExited) { break }
        try { if ((Invoke-RestMethod $healthUrl -TimeoutSec 2).ok) { $healthy = $true; break } } catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $healthy) { throw "$($service.Name) did not become healthy. Inspect app/.runtime/$($service.Name).err.log. Started PID: $($started.Id)." }
    Write-Host "$($service.Name) started on loopback port $($service.Port), PID $($started.Id)."
}
Write-Host 'Services ready locally. No public tunnel was started. Keep the laptop awake and plugged in.'
