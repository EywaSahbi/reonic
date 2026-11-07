// One client for reo/CONTRACT.md. VITE_API_URL empty or "mock" -> in-browser mock; otherwise HTTP to reo.
import type { HomeFacts, Locks, Plan, PlanSummary, PriceList, Turn } from "./types";
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
  startSession(): Promise<Turn>;
  sendMessage(id: string, text: string): Promise<Turn>;
  sendFacts(id: string, facts: Partial<HomeFacts>): Promise<Turn>;
  sendAddress(id: string, address: string): Promise<Turn>;
  handoff(id: string, name: string, email?: string): Promise<Plan>;
  getSession(id: string): Promise<Plan>;
  listPlans(status?: Plan["status"]): Promise<PlanSummary[]>;
  getPlan(id: string): Promise<Plan>;
  editPlan(id: string, edit: { locks?: Locks; facts?: Partial<HomeFacts>; prices?: PriceList }): Promise<Plan>;
  askPlan(id: string, text: string): Promise<{ answer: string }>;
  finalizePlan(id: string, note?: string): Promise<Plan>;
  validation(): Promise<unknown>;
};

const httpApi: Api = {
  startSession: () => call("POST", "/sessions", {}),
  sendMessage: (id, text) => call("POST", `/sessions/${id}/messages`, { text }),
  sendFacts: (id, facts) => call("POST", `/sessions/${id}/facts`, { facts }),
  sendAddress: (id, address) => call("POST", `/sessions/${id}/address`, { address }),
  handoff: (id, name, email) => call("POST", `/sessions/${id}/handoff`, { name, email }),
  getSession: (id) => call("GET", `/sessions/${id}`),
  listPlans: (status) => call("GET", `/plans${status ? `?status=${status}` : ""}`),
  getPlan: (id) => call("GET", `/plans/${id}`),
  editPlan: (id, edit) => call("POST", `/plans/${id}/edit`, edit),
  askPlan: (id, text) => call("POST", `/plans/${id}/ask`, { text }),
  finalizePlan: (id, note) => call("POST", `/plans/${id}/finalize`, { note }),
  validation: () => call("GET", "/validation"),
};

export const api: Api = USING_MOCK ? mockApi : httpApi;
