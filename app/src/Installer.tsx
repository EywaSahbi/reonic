import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { api, USING_MOCK } from "./api";
import { getInstallerToken, setInstallerToken } from "./auth";
import { RunTimeline } from "./OfferPack";
import { SonnfeldMark } from "./Logo";

const DesignStudio = lazy(() => import("./scene/DesignStudio"));
import { COMPONENT_KEYS, isOffline, type ComponentKey, type Design, type HomeFacts, type Locks, type Plan, type PlanSummary, type PriceList } from "./types";

const NAMES: Record<ComponentKey, string> = { pv: "PV", battery: "Battery", heatpump: "Heat pump", wallbox: "Wallbox" };
const eur = (n: number) => "€" + Math.round(n).toLocaleString("en");
const errText = (e: unknown) => String(e instanceof Error ? e.message : e);
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

// Installer view: inbox of handed-over plans -> plan detail with edits, "ask reo why", finalise.
export function Installer() {
  const remote = !USING_MOCK && !["localhost", "127.0.0.1", "[::1]"].includes(new URL(import.meta.env.VITE_API_URL).hostname);
  const [unlocked, setUnlocked] = useState(() => !remote || !!getInstallerToken());
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);
  useEffect(() => {
    const denied = () => { setUnlocked(false); setError("Your planner access token is missing or invalid."); };
    window.addEventListener("reo-installer-unauthorized", denied);
    return () => window.removeEventListener("reo-installer-unauthorized", denied);
  }, []);
  if (unlocked) return <InstallerWorkspace onLock={!USING_MOCK ? () => { setInstallerToken(""); setToken(""); setUnlocked(false); } : undefined} />;
  return <main className="planner-access card"><SonnfeldMark /><h1>Planner access</h1>
    <p>Enter the access token provided by your team. It stays in this browser tab for the current session.</p>
    <form onSubmit={async (e) => { e.preventDefault(); setChecking(true); setError(""); setInstallerToken(token);
      try { await api.listPlans(); setToken(""); setUnlocked(true); }
      catch { setInstallerToken(""); setError("Could not unlock the planner. Check the token and backend connection."); }
      finally { setChecking(false); }
    }}><label>Access token<input type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} required disabled={checking} /></label>
      {error && <p role="alert">{error}</p>}<button className="btn-primary" disabled={checking || !token.trim()}>{checking ? "Checking…" : "Unlock planner"}</button>
    </form><a href="#/">Back to customer site</a></main>;
}

function InstallerWorkspace({ onLock }: { onLock?: () => void }) {
  const [plans, setPlans] = useState<PlanSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function remove(p: PlanSummary) {
    if (!window.confirm(`Delete the plan for ${p.customer.name ?? "this customer"}? This can't be undone.`)) return;
    setDeleting(p.id);
    try {
      await api.deletePlan(p.id);
      setPlans((ps) => ps.filter((x) => x.id !== p.id));
      setSelected((s) => (s === p.id ? null : s));
    } catch (e) {
      window.alert(`Could not delete the plan: ${errText(e)}`);
    } finally {
      setDeleting(null);
    }
  }

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.listPlans().then((ps) => {
        if (!alive) return;
        const visible = ps.filter((p) => p.status !== "drafting");
        setPlans(visible);
        setSelected((s) => s ?? visible[0]?.id ?? null);
      }).catch(() => {});
    load();
    const t = setInterval(load, 5000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="inst">
      <header className="inst-nav">
        <div className="brand"><SonnfeldMark /> Sonnfeld</div>
        <span className="inst-tag">reo · powered by Reonic</span>
        {onLock && <button className="btn-ghost small" onClick={onLock}>Lock planner</button>}
        <a className="inst-link" href="#/">Customer site →</a>
      </header>
      <div className="inst-body">
        <aside className="inbox" aria-label="Handed-over plans">
          <h2>Inbox</h2>
          {plans.length === 0 && <p className="muted">No plans yet. Hand one over from the customer site.</p>}
          <ul>
            {plans.map((p) => (
              <li key={p.id}>
                <button className={`inbox-item ${selected === p.id ? "active" : ""}`} onClick={() => setSelected(p.id)}>
                  <span className="inbox-name">{p.customer.name ?? "Unnamed"}</span>
                  <span className={`pill pill-${p.status}`}>{p.status === "quoted" ? "quoted" : "new"}</span>
                  <span className="inbox-meta">{p.total_eur > 0 ? eur(p.total_eur) : "no price yet"} · {when(p.updated_at)}</span>
                </button>
                <button className="inbox-delete" onClick={() => remove(p)} disabled={deleting === p.id}
                  aria-label={`Delete plan for ${p.customer.name ?? "unnamed customer"}`} title="Delete plan">×</button>
              </li>
            ))}
          </ul>
        </aside>
        <main className="detail">{selected ? <PlanDetail key={selected} id={selected} /> : <p className="muted">Select a plan.</p>}</main>
      </div>
    </div>
  );
}

type Change = { keys: Set<string>; text: string };

// What changed between two designs, as before → after (engine numbers only, no arithmetic).
function diff(a: Design, b: Design): Change {
  const keys = new Set<string>();
  const parts: string[] = [];
  for (const k of COMPONENT_KEYS) {
    const x = a.components[k], y = b.components[k];
    if (x.recommended !== y.recommended || x.size !== y.size) {
      keys.add(k);
      const fmt = (c: typeof x) => (c.recommended && c.size !== null ? `${c.size} ${c.unit}` : "none");
      parts.push(`${NAMES[k]} ${fmt(x)} → ${fmt(y)}`);
    }
  }
  if (a.price.total_eur !== b.price.total_eur) { keys.add("total"); parts.push(`total ${eur(a.price.total_eur)} → ${eur(b.price.total_eur)}`); }
  if (a.economics.payback_years !== b.economics.payback_years) { keys.add("payback"); parts.push(`payback ${a.economics.payback_years ?? "–"} → ${b.economics.payback_years ?? "–"} yrs`); }
  if (a.economics.annual_savings_eur !== b.economics.annual_savings_eur) keys.add("savings");
  return { keys, text: parts.length ? parts.join(" · ") : "No change to the design." };
}

function PlanDetail({ id }: { id: string }) {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [change, setChange] = useState<Change | null>(null);
  const [note, setNote] = useState("");

  useEffect(() => { api.getPlan(id).then(setPlan).catch((e) => setError(errText(e))); }, [id]);

  async function edit(body: { locks?: Locks; facts?: Partial<HomeFacts>; prices?: PriceList }) {
    if (!plan) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.editPlan(plan.id, body);
      setChange(diff(plan.design, next.design));
      setPlan(next);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function finalize() {
    if (!plan) return;
    setBusy(true);
    try {
      setPlan(await api.finalizePlan(plan.id, note.trim() || undefined));
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!plan) return <p className="muted">{error ?? "Loading…"}</p>;
  const d = plan.design;
  const quoted = plan.status === "quoted";
  const hl = (k: string) => (change?.keys.has(k) ? "changed" : "");

  return (
    <div className={`plan-detail ${busy ? "is-busy" : ""}`}>
      <div className="detail-head">
        <div>
          <span className={`pill pill-${plan.status}`}>{quoted ? "Quote sent" : "Handed over"}</span>
          <h1>{plan.customer.name ?? "Unnamed customer"}</h1>
          <span className="muted">{plan.customer.email ?? "no email given"} · updated {when(plan.updated_at)}</span>
        </div>
        <div className={`detail-total ${hl("total")}`}>
          <span className="muted">Total</span>
          {isOffline(d) ? <strong>–</strong> : <>
            <strong>{eur(d.price.total_eur)}</strong>
            <span className="muted">range {eur(d.price.range_eur[0])}–{eur(d.price.range_eur[1]).slice(1)}</span>
          </>}
        </div>
      </div>

      <section className="card summary">
        <h3>Summary</h3>
        <p>{plan.summary ?? summarize(plan)}</p>
      </section>

      {isOffline(d) && <div className="flag flag-warn">⚠ Design engine unreachable: no sizes or prices in this plan yet. Edits and finalise need the engine.</div>}


      {change && (
        <div className="change-banner" role="status">
          <strong>Re-derived:</strong> {change.text}
          <button className="icon-btn" onClick={() => setChange(null)} aria-label="Dismiss">×</button>
        </div>
      )}
      {error && <div className="chat-error">{error}</div>}

      <Suspense fallback={<section className="card studio"><p className="muted">Loading design studio…</p></section>}>
        <DesignStudio design={d} facts={plan.facts} disabled={quoted || busy || isOffline(d)} onApply={(locks, prices) => edit({ locks, ...(prices ? { prices } : {}) })} />
      </Suspense>

      <div className="detail-grid">
        <section className="card">
          <h3>Home facts</h3>
          <FactsEditor facts={plan.facts} assumed={new Set(d.assumptions.map((a) => String(a.field)))} disabled={quoted || busy || isOffline(d)} onSave={(facts) => edit({ facts })} />
          {d.missing_inputs.length > 0 && (
            <div className="assumptions">
              <span>Still open</span>
              <ul>{d.missing_inputs.map((m) => <li key={String(m.field)}><b>{String(m.field)}</b> ({m.impact}): {m.why}</li>)}</ul>
            </div>
          )}
        </section>

        <section className="card">
          <h3>Price breakdown <span className="muted small">(estimate from the engine's price list)</span></h3>
          <table className="price-table">
            <tbody>
              {d.price.items.map((i) => (
                <tr key={i.label}><td>{i.label}</td><td className="num">{i.qty} {i.unit}</td><td className="num">{eur(i.unit_price_eur)}</td><td className="num">{eur(i.total_eur)}</td></tr>
              ))}
              <tr className={`price-total ${hl("total")}`}><td colSpan={3}>Total</td><td className="num">{eur(d.price.total_eur)}</td></tr>
            </tbody>
          </table>
        </section>

        <AskReo id={plan.id} />

        <section className="card">
          <h3>Conversation</h3>
          <div className="transcript">
            {plan.transcript.map((m, i) => <div key={i} className={`bubble bubble-${m.role}`}>{m.text}</div>)}
          </div>
        </section>
      </div>

      {/* the offer pack no longer carries a send-quote step: the planner finalises here (EywaSahbi) */}
      <section className="card finalize">
        {quoted ? (
          <p><strong>Quote sent.</strong> The customer now sees the confirmed plan and price on the website.</p>
        ) : (
          <>
            <label htmlFor="note">Note to the customer <span className="muted">(optional, sent as written)</span></label>
            <textarea id="note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="e.g. We checked your roof photos; 12 kWh fits your evening usage better." />
            <button className="btn-primary" onClick={finalize} disabled={busy || isOffline(d)}>Finalise and send quote · {eur(d.price.total_eur)}</button>
          </>
        )}
      </section>
    </div>
  );
}

// shortcut: fallback summary templated from plan data, used only while reo has not set Plan.summary.
function summarize(p: Plan): string {
  const f = p.facts, d = p.design, c = d.components;
  const home = [
    f.num_inhabitants ? `${f.num_inhabitants}-person home` : "Home",
    `${(f.total_demand_kwh ?? f.annual_demand_kwh ?? d.economics.total_demand_kwh).toLocaleString("en")} kWh/yr${f.total_demand_kwh ?? f.annual_demand_kwh ? "" : " (estimated)"}`,
    f.heating_type ? `${f.heating_type} heating` : "heating unknown",
    f.has_ev ? "has EV" : f.ev_planned ? "EV planned" : null,
  ].filter(Boolean).join(", ");
  const assumed = d.assumptions.map((a) => a.note).join("; ");
  const sys = COMPONENT_KEYS.filter((k) => c[k].recommended).map((k) => `${c[k].size} ${c[k].unit} ${NAMES[k]}`).join(", ");
  const asks = p.transcript.filter((m) => m.role === "customer" && /why|cost|price|expensive/i.test(m.text)).length;
  return `${home}${assumed ? `; assumed: ${assumed}` : ""}. ${asks ? `Customer asked ${asks}× about reasons or cost. ` : ""}Proposal: ${sys}; ${eur(d.price.total_eur)} (range ${eur(d.price.range_eur[0])}–${eur(d.price.range_eur[1]).slice(1)}), payback ~${d.economics.payback_years ?? "–"} yrs.${p.flags.length ? ` Check: ${p.flags.map((x) => x.text).join("; ")}.` : ""}`;
}


const REGIONS = ["BW", "BY", "BE", "BB", "HB", "HH", "HE", "MV", "NI", "NW", "RP", "SL", "SN", "ST", "SH", "TH"];

const FACT_FIELDS: { key: keyof HomeFacts; label: string; type: "number" | "heating" | "bool" | "region" }[] = [
  { key: "total_demand_kwh", label: "Total demand (kWh/yr)", type: "number" },
  { key: "num_inhabitants", label: "People", type: "number" },
  { key: "heating_type", label: "Heating", type: "heating" },
  { key: "ev_planned", label: "EV planned", type: "bool" },
  { key: "has_ev", label: "Has EV", type: "bool" },
  { key: "roof_area_sqm", label: "Roof area (m²)", type: "number" },
  { key: "region", label: "Federal state", type: "region" },
  { key: "house_size_sqm", label: "Living space (m²)", type: "number" },
  { key: "electricity_price_eur_per_kwh", label: "Tariff (€/kWh)", type: "number" },
];

function FactsEditor({ facts, assumed, disabled, onSave }: { facts: HomeFacts; assumed: Set<string>; disabled: boolean; onSave: (f: Partial<HomeFacts>) => void }) {
  const [draft, setDraft] = useState<Partial<HomeFacts>>({});
  const dirty = Object.keys(draft).length > 0;
  const val = <K extends keyof HomeFacts>(k: K) => (k in draft ? draft[k] : facts[k]);
  const set = (k: keyof HomeFacts, v: unknown) => setDraft((d) => ({ ...d, [k]: v }));
  return (
    <form className="facts" onSubmit={(e) => { e.preventDefault(); if (dirty) { onSave(draft); setDraft({}); } }}>
      {FACT_FIELDS.map(({ key, label, type }) => (
        <label key={key} className={key in draft ? "dirty" : ""}>
          <span>{label}{assumed.has(key) && <em className="assumed">assumed</em>}</span>
          {type === "number" && (
            <input type="number" step="any" value={(val(key) as number | undefined) ?? ""} disabled={disabled}
              onChange={(e) => set(key, e.target.value === "" ? undefined : Number(e.target.value))} />
          )}
          {type === "heating" && (
            <select value={(val(key) as string | undefined) ?? ""} disabled={disabled} onChange={(e) => set(key, e.target.value || undefined)}>
              <option value="">unknown</option>
              {["gas", "oil", "heatpump", "electric", "district", "other"].map((h) => <option key={h}>{h}</option>)}
            </select>
          )}
          {type === "region" && (
            <select value={(val(key) as string | undefined) ?? ""} disabled={disabled} onChange={(e) => set(key, e.target.value || undefined)}>
              <option value="">unknown</option>
              {REGIONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          )}
          {type === "bool" && (
            <select value={val(key) === undefined ? "" : String(val(key))} disabled={disabled} onChange={(e) => set(key, e.target.value === "" ? undefined : e.target.value === "true")}>
              <option value="">unknown</option><option value="true">yes</option><option value="false">no</option>
            </select>
          )}
        </label>
      ))}
      {dirty && <button className="btn-small facts-save" disabled={disabled}>Re-derive with new facts</button>}
    </form>
  );
}

function AskReo({ id }: { id: string }) {
  const [q, setQ] = useState("");
  const [qa, setQa] = useState<{ q: string; a: string; runId?: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { if (qa.length) end.current?.scrollIntoView({ block: "nearest" }); }, [qa]);
  async function ask(text: string) {
    if (!text.trim()) return;
    setBusy(true);
    try {
      const { answer, run_id } = await api.askPlan(id, text);
      setQa((x) => [...x, { q: text, a: answer, runId: run_id }]);
      setQ("");
    } catch (e) {
      setQa((x) => [...x, { q: text, a: `Error: ${errText(e)}` }]);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card ask-reo">
      <h3>Ask reo why</h3>
      <div className="chips">
        {["Why this battery size?", "Why a heat pump?", "Why does it cost this much?"].map((s) => <button key={s} className="chip" disabled={busy} onClick={() => ask(s)}>{s}</button>)}
      </div>
      {qa.map((x, i) => (
        <div key={i} className="qa"><p className="qa-q">{x.q}</p><p className="qa-a">{x.a}</p>{x.runId && <RunTimeline runId={x.runId} trace={[]} live={false} />}</div>
      ))}
      <div ref={end} />
      <form className="composer" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Why …?" disabled={busy} aria-label="Ask reo about this plan" />
        <button type="submit" disabled={busy || !q.trim()}>Ask</button>
      </form>
    </section>
  );
}
