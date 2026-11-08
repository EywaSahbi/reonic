# Free deployment: Vercel frontend + laptop backend

## Live deployment

- Frontend: https://sonnfeld-reo.vercel.app
- HTTPS backend: https://robin-ignore-oxidation.ngrok-free.dev
- Backend access middleware: reo commit 7df79d3. Planner routes require Bearer auth; customer sessions use their session IDs.
- Verified: production customer flow, planner token gate, anonymous planner 401, authenticated planner 200, production CORS, unrelated-origin denial, and authenticated SSE replay through the public tunnel.
- Planner token lives only in local ignored app/.runtime/installer-token.txt. Open that file locally and paste into the planner access form; do not put it in Git, the board or frontend environment variables.

## Demo access and capacity

The whole interactive demo requires a backend-verified code. The code is kept locally in ignored app/.runtime/demo-pin.txt and is sent in X-Demo-Pin, never bundled. Planner routes also require the separate Bearer token. Wrong attempts are throttled. After changing the code or limits, restart reo with the protected startup helper; saved plans remain intact.

Current admission limits: 5 active customer planning sessions (15-minute idle expiry), 2 concurrent agent runs, 2 concurrent write requests, 12 inflight requests including SSE, 240 requests/minute, 8 MiB multipart and 64 KiB JSON bodies. Excess work is rejected with 429/Retry-After rather than queued; oversized requests return 413. These limits activate with REO_DEMO_PIN. They limit active planning sessions, not the number of people who can download the static frontend. They are conservative settings, not a measured hardware maximum or protection against other applications exhausting laptop RAM.

To change the main caps on a stopped backend:

```powershell
./app/scripts/start-backend.ps1 -Protected -MaxActiveSessions 5 -MaxAgentRuns 2
```

Use one worker. Changing script parameters does not reconfigure an already-running process; restart reo first. Public health reports the active configuration for verification.

## Prepared

Vercel project `sonnfeld-reo` is linked and the CLI is authenticated. Deploy from `app/` only. `vercel.json` builds Vite into dist with `npm run build:deploy`. The deployment guard rejects mock/localhost/non-HTTPS API URLs and URLs containing credentials. `.vercelignore` excludes runtime files, learning logs and secrets.

Automatic GitHub connection failed because Vercel lacks access to this private repo. CLI deployment is available; a later Git integration must use app as its root directory.

## Laptop startup

From the repository root:

```powershell
./app/scripts/start-backend.ps1 -Protected
```

This starts or reuses engine/reo on loopback ports 8000/8001 and writes logs under ignored app/.runtime. It does not expose a tunnel. Keep the laptop awake, plugged in and online. Storage is still reo/plans.json; no SQLite migration happened. Back up that file outside Git and use one reo worker because locks/live runs are process-local.

## Backend access contract required

Before exposing the backend, reo must protect customer/installer/plan/run endpoints and configure the exact frontend CORS origin. CORS is not authentication. Agree with app on browser authentication, SSE, uploads, credentials and OPTIONS handling. Never embed a shared backend secret in VITE_* or the bundle. Keep engine private on localhost. The guarded start-tunnel.ps1 helper refuses to expose unprotected planner routes.

## ngrok setup

Windows blocked the standalone client download. Install the official Microsoft Store version (product 9MVS1J51GMK6); do not disable antivirus or add exclusions. Then configure your free account locally; never paste the token in chat or commit it:

```powershell
ngrok config add-authtoken YOUR_TOKEN
```

Only after backend access protection is verified:

```powershell
./app/scripts/start-tunnel.ps1
```

Use the returned HTTPS URL as VITE_API_URL. Verify the free-plan browser warning does not interfere with fetch, uploads or EventSource. Cloudflare Quick Tunnels do not support SSE and are unsuitable here.

## Vercel publication

From app/:

```powershell
npx --yes vercel env add VITE_API_URL production
npx --yes vercel env add VITE_API_URL preview
npm run build
npx --yes vercel --prod
```

Enter the real HTTPS tunnel URL at each environment prompt. Do not add Anthropic/ElevenLabs keys to frontend variables. Stay on the free/Hobby plan and do not accept a paid upgrade.

## Release checks

- Live API URL in deployment; no mock or localhost.
- Direct backend requests cannot list/open plans or perform installer actions without authorization.
- Allowed origin works; unrelated origins fail CORS.
- Address success/fallback, household choices and heating comparison work.
- Across devices: handoff -> offer preparation -> SSE replay -> variant/edit -> approve/reject -> final quote.
- Disconnecting the tunnel shows an honest offline state.

Current status: deployed and verified. The engine and reo run as hidden local processes; ngrok must remain running. Restart using the two scripts above after a laptop restart. Laptop sleep, shutdown or internet loss makes the backend unavailable. If the tunnel hostname changes, update VITE_API_URL and redeploy Vercel. The engine remains loopback-only.
