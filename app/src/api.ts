// One client for reo/CONTRACT.md. VITE_API_URL empty or "mock" -> in-browser mock; otherwise HTTP to reo.
import type { LayoutModule, RoofLayout, Run, RunStep, VariantName, Health, HomeFacts, Locks, Plan, PlanSummary, PriceList, Turn, VoiceTurn, AddressSuggestion } from "./types";
import { mockApi } from "./mock";
import { getInstallerToken, installerUnauthorized, isInstallerPath, getDemoPin, demoUnauthorized } from "./auth";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim() ?? "";
export const USING_MOCK = BASE === "" || BASE === "mock";

function requestHeaders(path: string, json = false): Record<string, string> {
  const headers: Record<string, string> = json ? { "Content-Type": "application/json" } : {};
  const pin = getDemoPin();
  if (pin) headers["X-Demo-Pin"] = pin;
  const token = getInstallerToken();
  if (isInstallerPath(path) && token) headers.Authorization = `Bearer ${token}`;
  if (/\.ngrok(-free)?\.(app|dev)$/.test(new URL(BASE || "http://localhost").hostname)) headers["ngrok-skip-browser-warning"] = "1";
  return headers;
}

async function responseError(res: Response): Promise<Error> {
  const detail = await res.text();
  if (res.status === 401) {
    if (/demo[ _-]*(pin|access)|demo.*pin/i.test(detail)) demoUnauthorized();
    else installerUnauthorized();
  }
  if (res.status === 429) {
    const seconds = Number(res.headers.get("Retry-After"));
    return new Error(seconds > 0 ? `The demo is busy. Please try again in ${Math.ceil(seconds)} seconds.` : "The demo is busy. Please try again shortly.");
  }
  if (res.status === 413) return new Error("This file is too large. Please use a smaller bill photo.");
  return new Error(res.status === 401 ? "The access code was not accepted." : `Request failed (${res.status}). Please try again.`);
}

export async function verifyDemoAccess(): Promise<void> {
  if (!USING_MOCK) await call("GET", "/demo/access");
}

async function call<T>(method: "GET" | "POST" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE.replace(/\/$/, "") + path, {
    method,
    headers: requestHeaders(path, body !== undefined),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

export type Api = {
  health(): Promise<Health>;
  sendVoice(id: string, audio: Blob): Promise<VoiceTurn>;
  startSession(): Promise<Turn>;
  sendMessage(id: string, text: string): Promise<Turn>;
  /** skip: ask fields the customer skipped (reo/CONTRACT.md /facts). */
  sendFacts(id: string, facts: Partial<HomeFacts>, skip?: string[]): Promise<Turn>;
  sendBill(id: string, image: File): Promise<Turn>;
  /** point: the picked type-ahead suggestion, so reo skips geocoding. */
  sendAddress(id: string, address: string, point?: AddressSuggestion): Promise<Turn>;
  suggestAddress(id: string, q: string): Promise<{ suggestions: AddressSuggestion[] }>;
  handoff(id: string, name: string, email?: string): Promise<Plan>;
  getSession(id: string): Promise<Plan>;
  listPlans(status?: Plan["status"]): Promise<PlanSummary[]>;
  getPlan(id: string): Promise<Plan>;
  deletePlan(id: string): Promise<{ deleted: string }>;
  editPlan(id: string, edit: { locks?: Locks; facts?: Partial<HomeFacts>; prices?: PriceList }): Promise<Plan>;
  /** Planner's module placement: the count becomes the pv lock, positions are stored (reo PUT /plans/{id}/layout). */
  putLayout(id: string, modules: LayoutModule[], frame?: RoofLayout["frame"]): Promise<Plan>;
  resetLayout(id: string): Promise<Plan>;
  askPlan(id: string, text: string): Promise<{ answer: string; run_id?: string }>;
  /** Planner asks by voice: ElevenLabs speech-to-text, reo's answer, spoken back (audio: base64 mp3 or null). */
  askPlanVoice(id: string, audio: Blob): Promise<{ heard: string; answer: string; run_id?: string; audio: string | null }>;
  /** reo reads a text aloud (ElevenLabs); null when voice is off. */
  speak(text: string): Promise<Blob | null>;
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
    if (!res.ok) throw await responseError(res);
    return res.json() as Promise<VoiceTurn>;
  },
  startSession: () => call("POST", "/sessions", {}),
  sendMessage: (id, text) => call("POST", `/sessions/${id}/messages`, { text }),
  sendFacts: (id, facts, skip) => call("POST", `/sessions/${id}/facts`, { facts, ...(skip?.length ? { skip } : {}) }),
  async sendBill(id, image) {
    const form = new FormData();
    form.append("image", image);
    const res = await fetch(BASE.replace(/\/$/, "") + `/sessions/${id}/bill`, { method: "POST", headers: requestHeaders(`/sessions/${id}`), body: form });
    if (!res.ok) throw await responseError(res);
    return res.json() as Promise<Turn>;
  },
  sendAddress: (id, address, point) => call("POST", `/sessions/${id}/address`, { ...point, address }),
  suggestAddress: (id, q) => call("GET", `/sessions/${id}/address/suggest?q=${encodeURIComponent(q)}`),
  handoff: (id, name, email) => call("POST", `/sessions/${id}/handoff`, { name, email }),
  getSession: (id) => call("GET", `/sessions/${id}`),
  listPlans: (status) => call("GET", `/plans${status ? `?status=${status}` : ""}`),
  getPlan: (id) => call("GET", `/plans/${id}`),
  editPlan: (id, edit) => call("POST", `/plans/${id}/edit`, edit),
  putLayout: (id, modules, frame) => call("PUT", `/plans/${id}/layout`, { modules, frame }),
  resetLayout: (id) => call("DELETE", `/plans/${id}/layout`),
  askPlan: (id, text) => call("POST", `/plans/${id}/ask`, { text }),
  async askPlanVoice(id, audio) {
    const form = new FormData();
    form.append("audio", audio, audio.type.includes("mp4") ? "speech.mp4" : "speech.webm");
    const path = `/plans/${id}/ask/voice`;
    const res = await fetch(BASE.replace(/\/$/, "") + path, { method: "POST", headers: requestHeaders(path), body: form });
    if (!res.ok) throw await responseError(res);
    return res.json();
  },
  async speak(text) {
    const res = await fetch(BASE.replace(/\/$/, "") + "/tts", { method: "POST", headers: requestHeaders("/tts", true), body: JSON.stringify({ text }) });
    return res.ok ? res.blob() : null;
  },
  finalizePlan: (id, note) => call("POST", `/plans/${id}/finalize`, { note }),
  preparePlan: (id) => call("POST", `/plans/${id}/prepare`, {}),
  chooseVariant: (id, name) => call("POST", `/plans/${id}/variant`, { name }),
  approveAction: (id, actionId, payload) => call("POST", `/plans/${id}/actions/${actionId}/approve`, payload ? { payload } : {}),
  deletePlan: (id) => call("DELETE", `/plans/${id}`),
  rejectAction: (id, actionId, reason) => call("POST", `/plans/${id}/actions/${actionId}/reject`, reason ? { reason } : {}),
  getRun: (runId) => call("GET", `/runs/${runId}`),
  watchRun(runId, onStep, onDone) {
    const controller = new AbortController();
    const path = `/runs/${runId}/events`;
    // fetch supports Bearer authentication without placing the planner secret in a URL or access log.
    void (async () => {
      const res = await fetch(BASE.replace(/\/$/, "") + path, { headers: requestHeaders(path), signal: controller.signal });
      if (!res.ok) { await responseError(res); return; }
      if (!res.body) return;
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
