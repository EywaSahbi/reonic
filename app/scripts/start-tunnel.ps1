# Start the public tunnel only after proving the local planner endpoints are protected.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$tokenFile = Join-Path $repoRoot 'app/.runtime/installer-token.txt'
if (-not (Test-Path -LiteralPath $tokenFile)) { throw 'Run start-backend.ps1 -Protected first.' }
$plannerToken = [System.IO.File]::ReadAllText($tokenFile).Trim()
$anon = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -SkipHttpErrorCheck
if ($anon.StatusCode -ne 401) { throw 'Refusing public tunnel: planner routes are not protected.' }
$authHeaders = @{Authorization="Bearer $plannerToken"}
$demoPinFile = Join-Path $repoRoot 'app/.runtime/demo-pin.txt'
if (Test-Path -LiteralPath $demoPinFile) {
    $demoPin = [System.IO.File]::ReadAllText($demoPinFile).Trim()
    $authHeaders['X-Demo-Pin'] = $demoPin
    $health = Invoke-RestMethod 'http://127.0.0.1:8001/health'
    if (-not $health.demo_auth_required) { throw 'Refusing public tunnel: requested demo PIN is not enforced.' }
    $demoCheck = Invoke-WebRequest 'http://127.0.0.1:8001/demo/access' -Headers @{'X-Demo-Pin'=$demoPin} -SkipHttpErrorCheck
    $pinOnly = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -Headers @{'X-Demo-Pin'=$demoPin} -SkipHttpErrorCheck
    if ($pinOnly.StatusCode -ne 401) { throw 'Refusing public tunnel: separate planner token is not required.' }
    if ($demoCheck.StatusCode -ne 200) { throw 'Refusing public tunnel: demo PIN verification failed.' }
}
$verified = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -Headers $authHeaders -SkipHttpErrorCheck
if ($verified.StatusCode -ne 200) { throw 'Refusing public tunnel: local planner token does not match the backend.' }
ngrok config check
if ($LASTEXITCODE -ne 0) { throw 'Configure your ngrok account locally first.' }
ngrok http http://127.0.0.1:8001
