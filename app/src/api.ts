// One client for reo/CONTRACT.md. VITE_API_URL empty or "mock" -> in-browser mock; otherwise HTTP to reo.
import type { Run, RunStep, VariantName, Health, HomeFacts, Locks, Plan, PlanSummary, PriceList, Turn, VoiceTurn } from "./types";
import { mockApi } from "./mock";

const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.trim() ?? "";
export const USING_MOCK = BASE === "" || BASE === "mock";

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE.replace(/\/$/, "") + path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
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
  askPlan(id: string, text: string): Promise<{ answer: string }>;
  finalizePlan(id: string, note?: string): Promise<Plan>;
  validation(split?: "test" | "val", view?: "profiles"): Promise<unknown>;
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
    const res = await fetch(BASE.replace(/\/$/, "") + `/sessions/${id}/voice`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`POST /sessions/${id}/voice → ${res.status} ${await res.text()}`);
    return res.json() as Promise<VoiceTurn>;
  },
  startSession: () => call("POST", "/sessions", {}),
  sendMessage: (id, text) => call("POST", `/sessions/${id}/messages`, { text }),
  sendFacts: (id, facts) => call("POST", `/sessions/${id}/facts`, { facts }),
  async sendBill(id, image) {
    const form = new FormData();
    form.append("image", image);
    const res = await fetch(BASE.replace(/\/$/, "") + `/sessions/${id}/bill`, { method: "POST", body: form });
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
  validation: (split = "test", view) => call("GET", `/validation?${view ? `view=${view}` : `split=${split}`}`),
  preparePlan: (id) => call("POST", `/plans/${id}/prepare`, {}),
  chooseVariant: (id, name) => call("POST", `/plans/${id}/variant`, { name }),
  approveAction: (id, actionId, payload) => call("POST", `/plans/${id}/actions/${actionId}/approve`, payload ? { payload } : {}),
  rejectAction: (id, actionId, reason) => call("POST", `/plans/${id}/actions/${actionId}/reject`, reason ? { reason } : {}),
  getRun: (runId) => call("GET", `/runs/${runId}`),
  watchRun(runId, onStep, onDone) {
    const es = new EventSource(BASE.replace(/\/$/, "") + `/runs/${runId}/events`);
    es.addEventListener("step", (e) => onStep(JSON.parse((e as MessageEvent).data)));
    es.addEventListener("done", (e) => { onDone(JSON.parse((e as MessageEvent).data)); es.close(); });
    es.onerror = () => es.close(); // the timeline keeps what it has; the pack itself still polls
    return () => es.close();
  },
  calendarSlots: () => call("GET", "/calendar/slots"),
};

export const api: Api = USING_MOCK ? mockApi : httpApi;
