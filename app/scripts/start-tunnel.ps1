# Start the public tunnel only after proving the local planner endpoints are protected.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$tokenFile = Join-Path $repoRoot 'app/.runtime/installer-token.txt'
if (-not (Test-Path -LiteralPath $tokenFile)) { throw 'Run start-backend.ps1 -Protected first.' }
$plannerToken = [System.IO.File]::ReadAllText($tokenFile).Trim()
$anon = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -SkipHttpErrorCheck
if ($anon.StatusCode -ne 401) { throw 'Refusing public tunnel: planner routes are not protected.' }
$verified = Invoke-WebRequest 'http://127.0.0.1:8001/plans' -Headers @{Authorization="Bearer $plannerToken"} -SkipHttpErrorCheck
if ($verified.StatusCode -ne 200) { throw 'Refusing public tunnel: local planner token does not match the backend.' }
ngrok config check
if ($LASTEXITCODE -ne 0) { throw 'Configure your ngrok account locally first.' }
ngrok http http://127.0.0.1:8001
