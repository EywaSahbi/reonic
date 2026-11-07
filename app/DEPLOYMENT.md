# Free deployment: Vercel frontend + laptop backend

## Prepared

Vercel project `sonnfeld-reo` is linked and the CLI is authenticated. Deploy from `app/` only. `vercel.json` builds Vite into dist with `npm run build:deploy`. The deployment guard rejects mock/localhost/non-HTTPS API URLs and URLs containing credentials. `.vercelignore` excludes runtime files, learning logs and secrets.

Automatic GitHub connection failed because Vercel lacks access to this private repo. CLI deployment is available; a later Git integration must use app as its root directory.

## Laptop startup

From the repository root:

```powershell
./app/scripts/start-backend.ps1
```

This starts or reuses engine/reo on loopback ports 8000/8001 and writes logs under ignored app/.runtime. It does not expose a tunnel. Keep the laptop awake, plugged in and online. Storage is still reo/plans.json; no SQLite migration happened. Back up that file outside Git and use one reo worker because locks/live runs are process-local.

## Backend access contract required

Before exposing the backend, reo must protect customer/installer/plan/run endpoints and configure the exact frontend CORS origin. CORS is not authentication. Agree with app on browser authentication, SSE, uploads, credentials and OPTIONS handling. Never embed a shared backend secret in VITE_* or the bundle. Keep engine private on localhost. No public tunnel has been started by this setup.

## ngrok setup

Windows blocked the standalone client download. Install the official Microsoft Store version (product 9MVS1J51GMK6); do not disable antivirus or add exclusions. Then configure your free account locally; never paste the token in chat or commit it:

```powershell
ngrok config add-authtoken YOUR_TOKEN
```

Only after backend access protection is verified:

```powershell
ngrok http http://127.0.0.1:8001
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

Current status: prepared, not publicly deployed. ngrok token configuration and reo access contract are pending. Laptop uptime determines backend availability.
