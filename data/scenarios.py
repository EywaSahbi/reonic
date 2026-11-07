"""processed/scenarios.json: hard-case homes for reo's harness evals (reo/evals).

    uv run python scenarios.py

Each scenario = one real home (val; train only where val has no such case, never test) with its HomeFacts
inputs and the expert design. Facts the data cannot hold (planned EV, budget) are listed in `added_facts`
and merged into `facts`; the expert design did not see them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
FACTS = ["annual_demand_kwh", "num_inhabitants", "house_size_sqm", "house_built_year", "heating_type",
         "heating_demand_kwh", "has_ev", "ev_km_per_year", "electricity_price_eur_per_kwh",
         "has_existing_pv", "existing_pv_kwp", "has_existing_battery"]


def clean(v):
    if v is None or v != v:
        return None
    return v.item() if hasattr(v, "item") else v


def pick(df: pd.DataFrame, mask: pd.Series, sort: str | None = None, asc: bool = True) -> pd.Series:
    rows = df[mask]
    rows = rows.sort_values([sort, "project_id"] if sort else "project_id", ascending=[asc, True] if sort else True)
    if rows.empty:
        raise ValueError("no home for scenario")
    return rows.iloc[0]


def scenario(sid: str, r: pd.Series, why: str, expect: str, added: dict | None = None) -> dict:
    facts = {f: clean(r[f]) for f in FACTS if clean(r[f]) is not None}
    facts.update(added or {})
    expert = {c: {"recommended": bool(r[f"has_{c}"]), "size": clean(r[s]) if r[f"has_{c}"] else None, "unit": u}
              for c, s, u in (("pv", "pv_kwp", "kWp"), ("battery", "battery_kwh", "kWh"),
                              ("heatpump", "heatpump_kw", "kW"), ("wallbox", "wallbox_kw", "kW"))}
    return {"id": sid, "project_id": r.project_id, "split": r.split, "installer": r.installer, "why": why,
            "facts": facts, "added_facts": added or {}, "existing_heating_electricity_kwh":
                clean(r.existing_heating_electricity_kwh), "expert": expert,
            "target_source": r.target_source, "expect": expect}


def build() -> list[dict]:
    d = pd.read_parquet(ROOT / "processed" / "projects.parquet").merge(pd.read_csv(ROOT / "processed" / "split.csv"))
    v, t = d[d.split == "val"], d[d.split == "train"]
    plausible = v.annual_demand_kwh.between(1000, 25000)
    return [
        scenario("typical", pick(v, (v.annual_demand_kwh == 4500) & v.has_pv & v.has_battery & ~v.has_wallbox
                                 & ~v.has_ev & v.heating_type.isna()),
                 "The most common home: 4,500 kWh household, no EV, heating unknown.",
                 "PV + battery near the segment median; no heat pump; wallbox not pushed."),
        scenario("retrofit_existing_pv", pick(v, v.has_existing_pv & ~v.has_pv & v.has_battery),
                 "Home already has PV (recorded); expert added only a battery.",
                 "No new PV; battery sized to the existing array."),
        scenario("retrofit_unrecorded_pv", pick(v, ~v.has_existing_pv & ~v.has_pv & v.has_battery & ~v.has_wallbox,
                                                "annual_demand_kwh", False),
                 "Expert sold only a battery but existing PV is not recorded (49 of 52 such test homes).",
                 "reo asks 'do you already have solar?' before proposing PV."),
        scenario("ev_driver", pick(v, v.has_ev & v.has_wallbox & v.has_pv, "ev_km_per_year", False),
                 "EV with known mileage; expert sold PV + wallbox.",
                 "Wallbox 11 kW; PV sized for household + EV."),
        scenario("ev_planned", pick(v, ~v.has_ev & v.has_wallbox & v.has_pv & (v.annual_demand_kwh == 4500)),
                 "Expert sold a wallbox to a home without a recorded EV (57 of 62 val wallboxes): an EV is planned.",
                 "With ev_planned the design adds a wallbox and sizes PV for the future EV.",
                 {"ev_planned": True}),
        scenario("gas_to_heatpump", pick(t, (t.heating_type == "gas") & t.has_heatpump),
                 "Gas heating replaced by a heat pump. From train: val has no expert heat pump.",
                 "Heat pump proposed; PV sized for household + heat pump consumption."),
        scenario("tiny_demand", pick(v, plausible & v.has_pv, "annual_demand_kwh", True),
                 "Smallest plausible household demand with PV in val.",
                 "Small PV, small or no battery; flags if sizes exceed similar homes."),
        scenario("big_demand", pick(v, plausible & v.has_pv, "annual_demand_kwh", False),
                 "Largest plausible household demand with PV in val.",
                 "Large PV (roof permitting), larger battery; no oversize flag vs the 6000+ segment."),
        scenario("tight_budget", pick(v, (v.annual_demand_kwh == 5000) & v.has_pv & v.has_battery, "battery_kwh", False),
                 "Typical PV + battery home with an added tight budget; the expert design did not see the budget.",
                 "Total price within budget_eur, battery reduced or dropped first, the budget variant says what was cut.",
                 {"budget_eur": 12000}),
    ]


def main() -> None:
    sc = build()
    out = ROOT / "processed" / "scenarios.json"
    out.write_text(json.dumps({"built_from": "val (gas_to_heatpump from train), never test",
                               "scenarios": sc}, indent=1), encoding="utf-8")
    for s in sc:
        e = s["expert"]
        sizes = ", ".join(f"{c} {x['size']:g}" for c, x in e.items() if x["recommended"] and x["size"])
        print(f"{s['id']:24s} {s['split']:5s} demand={s['facts'].get('annual_demand_kwh')}  expert: {sizes or 'none'}")


if __name__ == "__main__":
    main()
