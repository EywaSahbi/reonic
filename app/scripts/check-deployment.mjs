import { loadEnv } from 'vite';

const env = loadEnv('production', process.cwd(), 'VITE_');
const base = (process.env.VITE_API_URL ?? env.VITE_API_URL ?? '').trim();
let url;
try { url = new URL(base); } catch { /* Report one actionable error below. */ }
if (!url || url.protocol !== 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
    || url.username || url.password || url.search || url.hash) {
  console.error('Deployment requires VITE_API_URL=https://<your-live-backend-host> in Vercel. Mock/localhost URLs and embedded credentials are not allowed.');
  process.exit(1);
}
console.log(`Deployment API host: ${url.host}`);
console.log('Reminder: backend authentication, allowed frontend origin and SSE must be verified before sharing the deployment.');
