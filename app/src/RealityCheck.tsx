import { useEffect, useState } from "react";
import { api } from "./api";

type Scores = { available?: boolean; split?: string; n?: number; bundle_match?: number; components?: Record<string, { presence_acc?: number; size_mae?: number | null; within_tol?: number | null }>; by_installer?: Record<string, { n?: number; bundle_match?: number; components?: Scores["components"] }>; note?: string; file?: string };
const pct = (n?: number | null) => n == null ? "—" : `${Math.round(n * 100)}%`;

export function RealityCheck() {
  const [split, setSplit] = useState<"test" | "val">("test");
  const [profiles, setProfiles] = useState(false);
  const [data, setData] = useState<Scores | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { let alive = true; setData(null); setError(""); api.validation(split, profiles ? "profiles" : undefined).then((x) => { if (alive) setData(x as Scores); }).catch((e) => { if (alive) setError(String(e)); }); return () => { alive = false; }; }, [split, profiles]);
  const comps = data?.components;
  return <section className="card reality-check">
    <div className="reality-head"><div><span className="muted small">Held-out homes · engine vs expert designs</span><h3>Reality check</h3></div><div className="reality-controls"><select value={split} onChange={(e) => setSplit(e.target.value as "test" | "val")} aria-label="Validation split"><option value="test">Test set</option><option value="val">Validation set</option></select><label><input type="checkbox" checked={profiles} onChange={(e) => setProfiles(e.target.checked)} /> Installer profiles</label></div></div>
    {error ? <p className="muted">Could not load validation: {error}</p> : !data ? <p className="muted">Loading published scores…</p> : data.available === false ? <p className="muted">{data.note ?? "Validation scores are not available yet."}</p> : <>
      <p className="muted">{data.n ?? "—"} homes · {data.file ?? `${data.split ?? split} split`}. These scores describe where the model agrees with historical expert choices.</p>
      <div className="reality-metrics"><div><b>{pct(data.bundle_match)}</b><span>full bundle match</span></div>{(["pv", "battery", "wallbox", "heatpump"] as const).map((key) => { const c = comps?.[key]; return c ? <div key={key}><b>{pct(c.within_tol)}</b><span>{key} size within ±20%</span><small>presence {pct(c.presence_acc)} · MAE {c.size_mae ?? "—"} {key === "pv" ? "kWp" : key === "battery" ? "kWh" : "kW"}</small></div> : null; })}</div>
      {profiles && data.by_installer && <div className="profile-scores">{Object.entries(data.by_installer).map(([id, row]) => <div key={id}><strong>Installer {id}</strong><span>{row.n} homes · bundle {pct(row.bundle_match)}</span><small>PV ±20% {pct(row.components?.pv?.within_tol)} · battery ±20% {pct(row.components?.battery?.within_tol)}</small></div>)}</div>}
      <p className="reality-caveat">Bundle agreement is close to the simple baseline; battery sizing remains difficult. The system helps planners move faster, with expert review still in control.</p>
    </>}
  </section>;
}
