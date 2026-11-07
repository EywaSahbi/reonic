# Start the existing Python services on loopback only. Does not expose a public tunnel.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$runtimeDir = Join-Path $repoRoot 'app/.runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

foreach ($service in @(@{Name='engine';Port=8000}, @{Name='reo';Port=8001})) {
    $healthUrl = "http://127.0.0.1:$($service.Port)/health"
    try {
        $health = Invoke-RestMethod $healthUrl -TimeoutSec 3
        if ($health.ok) { Write-Host "$($service.Name) already healthy on $($service.Port); reusing it."; continue }
    } catch { }
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
