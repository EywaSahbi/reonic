// One client for reo/CONTRACT.md. VITE_API_URL empty or "mock" -> in-browser mock; otherwise HTTP to reo.
import type { Run, RunStep, VariantName, Health, HomeFacts, Locks, Plan, PlanSummary, PriceList, Turn, VoiceTurn } from "./types";
import { mockApi } from "./mock";
import { getInstallerToken, installerUnauthorized, isInstallerPath } from "./auth";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim() ?? "";
export const USING_MOCK = BASE === "" || BASE === "mock";

function requestHeaders(path: string, json = false): Record<string, string> {
  const headers: Record<string, string> = json ? { "Content-Type": "application/json" } : {};
  const token = getInstallerToken();
  if (isInstallerPath(path) && token) headers.Authorization = `Bearer ${token}`;
  if (/\.ngrok(-free)?\.(app|dev)$/.test(new URL(BASE || "http://localhost").hostname)) headers["ngrok-skip-browser-warning"] = "1";
  return headers;
}

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE.replace(/\/$/, "") + path, {
    method,
    headers: requestHeaders(path, body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && isInstallerPath(path)) installerUnauthorized();
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export type Api = {
  health(): Promise<Health>;
  sendVoice(id: string, audio: Blob): Promise<VoiceTurn>;
  startSession(): Promise<Turn>;
  sendMessage(id: string, text: string): Promise<Turn>;
  sendFacts(id: string, facts: Partial<HomeFacts>): Promise<Turn>;
  sendBill(id: string, image: File): Promise<Turn>;
  sendAddress(id: string, address: string): Promise<Turn>;
  handoff(id: string, name: string, email?: string): Promise<Plan>;
  getSession(id: string): Promise<Plan>;
  listPlans(status?: Plan["status"]): Promise<PlanSummary[]>;
  getPlan(id: string): Promise<Plan>;
  editPlan(id: string, edit: { locks?: Locks; facts?: Partial<HomeFacts>; prices?: PriceList }): Promise<Plan>;
  askPlan(id: string, text: string): Promise<{ answer: string; run_id?: string }>;
  finalizePlan(id: string, note?: string): Promise<Plan>;
  preparePlan(id: string): Promise<Plan>;
  chooseVariant(id: string, name: VariantName): Promise<Plan>;
  approveAction(id: string, actionId: string, payload?: Record<string, unknown>): Promise<Plan>;
  rejectAction(id: string, actionId: string, reason?: string): Promise<Plan>;
  getRun(runId: string): Promise<Run>;
  /** Live steps of a run (SSE, replays past steps first). Returns a close function. */
  watchRun(runId: string, onStep: (s: RunStep) => void, onDone: (d: { status: Run["status"]; duration_s: number | null }) => void): () => void;
  calendarSlots(): Promise<{ slots: string[] }>;
};

const httpApi: Api = {
  health: () => call("GET", "/health"),
  async sendVoice(id, audio) {
    const form = new FormData();
    form.append("audio", audio, audio.type.includes("mp4") ? "speech.mp4" : "speech.webm");
    const res = await fetch(BASE.replace(/\/$/, "") + `/sessions/${id}/voice`, { method: "POST", headers: requestHeaders(`/sessions/${id}`), body: form });
    if (!res.ok) throw new Error(`POST /sessions/${id}/voice → ${res.status} ${await res.text()}`);
    return res.json() as Promise<VoiceTurn>;
  },
  startSession: () => call("POST", "/sessions", {}),
  sendMessage: (id, text) => call("POST", `/sessions/${id}/messages`, { text }),
  sendFacts: (id, facts) => call("POST", `/sessions/${id}/facts`, { facts }),
  async sendBill(id, image) {
    const form = new FormData();
    form.append("image", image);
    const res = await fetch(BASE.replace(/\/$/, "") + `/sessions/${id}/bill`, { method: "POST", headers: requestHeaders(`/sessions/${id}`), body: form });
    if (!res.ok) throw new Error(`POST /sessions/${id}/bill → ${res.status} ${await res.text()}`);
    return res.json() as Promise<Turn>;
  },
  sendAddress: (id, address) => call("POST", `/sessions/${id}/address`, { address }),
  handoff: (id, name, email) => call("POST", `/sessions/${id}/handoff`, { name, email }),
  getSession: (id) => call("GET", `/sessions/${id}`),
  listPlans: (status) => call("GET", `/plans${status ? `?status=${status}` : ""}`),
  getPlan: (id) => call("GET", `/plans/${id}`),
  editPlan: (id, edit) => call("POST", `/plans/${id}/edit`, edit),
  askPlan: (id, text) => call("POST", `/plans/${id}/ask`, { text }),
  finalizePlan: (id, note) => call("POST", `/plans/${id}/finalize`, { note }),
  preparePlan: (id) => call("POST", `/plans/${id}/prepare`, {}),
  chooseVariant: (id, name) => call("POST", `/plans/${id}/variant`, { name }),
  approveAction: (id, actionId, payload) => call("POST", `/plans/${id}/actions/${actionId}/approve`, payload ? { payload } : {}),
  rejectAction: (id, actionId, reason) => call("POST", `/plans/${id}/actions/${actionId}/reject`, reason ? { reason } : {}),
  getRun: (runId) => call("GET", `/runs/${runId}`),
  watchRun(runId, onStep, onDone) {
    const controller = new AbortController();
    const path = `/runs/${runId}/events`;
    // fetch supports Bearer authentication without placing the planner secret in a URL or access log.
    void (async () => {
      const res = await fetch(BASE.replace(/\/$/, "") + path, { headers: requestHeaders(path), signal: controller.signal });
      if (res.status === 401) { installerUnauthorized(); return; }
      if (!res.ok || !res.body) return;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let pending = "";
      try {
        while (!controller.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          pending += decoder.decode(value, { stream: true });
          pending = pending.replace(/\r\n/g, "\n");
          let end: number;
          while ((end = pending.indexOf("\n\n")) >= 0) {
            const frame = pending.slice(0, end); pending = pending.slice(end + 2);
            const lines = frame.split("\n");
            const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
            const data = lines.filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
            if (!data) continue;
            if (event === "step") onStep(JSON.parse(data));
            if (event === "done") { onDone(JSON.parse(data)); return; }
          }
        }
      } finally { await reader.cancel().catch(() => {}); }
    })().catch(() => { /* Pack polling remains available if the stream disconnects. */ });
    return () => controller.abort();
  },
  calendarSlots: () => call("GET", "/calendar/slots"),
};

export const api: Api = USING_MOCK ? mockApi : httpApi;
