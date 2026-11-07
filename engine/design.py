"""The full design for one home (CONTRACT.md `Design`): sizes, price, economics, ranges, reasons.

core()     one deterministic pass: Step 0 sizing → battery, wallbox, heat pump → price → yearly simulation.
design()   core() plus re-runs at the low / high plausible value of every missing input:
           those give each size's `range`, the price range and the ranking of `missing_inputs` (PLAN.md #11, #12).
explain()  reasons and what-ifs for one component.
"""
import json
from functools import lru_cache
from pathlib import Path

from inputs import ELECTRIC_HEATING, PARAMS, heat_demand, profile, read_inputs, size_pv
from sim import simulate

PRICES = {k: v for k, v in json.loads((Path(__file__).parent / "prices.json").read_text()).items()
          if not k.startswith("_")}
VERSION = f"{PARAMS['version']}+line{PARAMS['pv_line']['a_kwp']}/{PARAMS['pv_line']['b_kwp_per_mwh']}"
COMPONENTS = ("pv", "battery", "heatpump", "wallbox")
UNITS = {"pv": "kWp", "battery": "kWh", "heatpump": "kW", "wallbox": "kW"}
BUNDLES = ((6, "S"), (10, "M"), (14, "L"))       # new PV kWp below the bound → bundle name, else "XL"
FUEL = {"gas": "gas_eur_per_kwh", "oil": "oil_eur_per_kwh", "district": "district_eur_per_kwh", "other": "gas_eur_per_kwh"}
WHY = {
    "total_demand_kwh": "your yearly electricity use sets the PV and battery size",
    "region": "sunshine differs ~15% between north and south Germany",
    "roof_area_sqm": "checks the panels fit and whether there is room for more",
    "roof_orientation_deg": "an east or west roof yields ~20% less than a south roof",
    "heating_type": "decides whether a heat pump makes sense",
    "heating_demand_kwh": "sizes the heat pump and the extra PV it needs",
    "electricity_price_eur_per_kwh": "sets your savings and payback",
    "has_ev": "an EV adds a wallbox and shifts power use to the evening",
    "has_existing_pv": "with solar already on the roof, experts add storage instead of more panels",
}

sim = lru_cache(maxsize=4096)(simulate)


def nearest(sizes, x):
    return min(sizes, key=lambda s: abs(s - x))


def price_of(key, overrides):
    """(mid, low, high) for one price key; an installer override fixes all three."""
    if key in overrides:
        return (overrides[key],) * 3
    return PRICES[key], PRICES.get(f"{key}_low", PRICES[key]), PRICES.get(f"{key}_high", PRICES[key])


def battery_for(pv_kwp, bands):
    """The experts' most common battery size for this PV size (bands from tools/derive_params.py)."""
    return next(size for upper, size in bands if upper is None or pv_kwp <= upper)


def core(facts: dict, locks: dict, overrides: dict, installer: str | None = None) -> dict:
    p = PARAMS
    home = read_inputs(facts)
    prof = profile(installer)
    lock = {k: locks.get(k) or {} for k in COMPONENTS}

    # retrofit: with existing PV, experts add storage / wallbox, not more panels (51 of 52 no-PV test homes)
    retrofit = home.has_existing_pv and not lock["pv"]
    pv_locked = None
    if lock["pv"]:
        pv_locked = lock["pv"].get("size", None) if lock["pv"]["recommended"] else 0.0
    sizing = size_pv(home, facts, 0.0 if retrofit else pv_locked, prof["pv_line"], prof["pv_packages"], prof["module_w"])

    # heat pump: suggested by the roof check, or forced on / off by a lock
    hp_rec, hp_kw, heat, hp_note = sizing.heatpump_suggested, sizing.heatpump_kw, sizing.heat_demand_kwh, None
    if lock["heatpump"]:
        hp_rec = lock["heatpump"]["recommended"]
        if hp_rec:
            heat, hp_note = heat_demand(facts, home)
            hp_kw = lock["heatpump"].get("size") or nearest(p["heatpump_catalogue_kw"], heat / p["heatpump_full_load_hours"])
    elif hp_rec:
        _, hp_note = heat_demand(facts, home)
    hp_el = heat / p["cop"] if hp_rec and heat else 0.0

    adds_hp_pv = hp_rec and pv_locked is None                  # heat-pump PV on the spare roof, also in retrofits
    if sizing.capped_from is not None and pv_locked:
        pv_locked = sizing.kwp                                 # a lock above the roof is cut to the cap
    pv_kwp = pv_locked if pv_locked else sizing.kwp + (sizing.heatpump_extra_kwp if adds_hp_pv else 0.0)
    pv_modules = sizing.modules + (sizing.heatpump_extra_modules if adds_hp_pv else 0)
    pv_rec = pv_kwp > 0 if not lock["pv"] else lock["pv"]["recommended"]
    pv_total = home.existing_pv_kwp + (pv_kwp if pv_rec else 0.0)

    cat = p["battery"]["catalogue_kwh"]
    bat_rec = pv_total > 0 and not home.has_existing_battery
    bat_kwh = battery_for(pv_total, prof["battery_by_pv_band"])
    if lock["battery"]:
        bat_rec = lock["battery"]["recommended"]
        bat_kwh = lock["battery"].get("size") or bat_kwh
    existing_bat = nearest(cat, p["battery"]["r_b_kwh_per_kwp"] * home.existing_pv_kwp) \
        if home.has_existing_battery and home.existing_pv_kwp else 0.0

    wb_rec = home.has_ev or home.ev_planned
    wb_kw = p["wallbox_kw"]
    if lock["wallbox"]:
        wb_rec = lock["wallbox"]["recommended"]
        wb_kw = lock["wallbox"].get("size") or wb_kw

    sizes = {"pv": pv_kwp if pv_rec else None, "battery": bat_kwh if bat_rec else None,
             "heatpump": hp_kw if hp_rec else None, "wallbox": wb_kw if wb_rec else None}

    # price: line items at mid prices, plus low / high per component (the range only sums recommended ones)
    items, cost = [], {k: [0.0, 0.0] for k in COMPONENTS}
    hp_pv = sizing.heatpump_extra_kwp if adds_hp_pv else 0.0   # PV that exists for the heat pump

    def item(label, qty, unit, key, comp, split=None):
        mid, lo, hi = price_of(key, overrides)
        items.append({"label": label, "qty": round(qty, 2), "unit": unit, "unit_price_eur": mid,
                      "total_eur": round(qty * mid, 2)})
        for c, q in (split or {comp: qty}).items():
            cost[c][0] += q * lo
            cost[c][1] += q * hi

    if pv_rec and pv_kwp:
        item(f"PV system, {pv_modules} modules × {sizing.module_w:g} W, inverter", pv_kwp, "kWp", "pv_eur_per_kwp", "pv",
             {"pv": pv_kwp - hp_pv, "heatpump": hp_pv})
        item("PV installation, scaffolding, grid registration", 1, "flat", "pv_base_eur", "pv")
    if bat_rec:
        item(f"Battery storage {bat_kwh:g} kWh", bat_kwh, "kWh", "battery_eur_per_kwh", "battery")
        item("Battery installation", 1, "flat", "battery_base_eur", "battery")
    if wb_rec:
        item(f"Wallbox {wb_kw:g} kW incl. installation", 1, "piece", "wallbox_eur", "wallbox")
    if hp_rec and hp_kw:
        device = [price_of(k, overrides) for k in ("heatpump_eur_per_kw", "heatpump_base_eur")]
        item(f"Air-water heat pump {hp_kw:g} kW", hp_kw, "kW", "heatpump_eur_per_kw", "heatpump")
        item("Heat pump installation, hydraulics", 1, "flat", "heatpump_base_eur", "heatpump")
        # KfW 458 base grant: share of the eligible heat-pump cost (bonuses are case by case, not applied)
        share = price_of("heatpump_subsidy_share", overrides)[0]
        cap = price_of("heatpump_subsidy_max_eligible_eur", overrides)[0]
        mid, lo, hi = (hp_kw * per_kw + base for per_kw, base in zip(*device))
        if share:                                # share 0 = no grant line (reo's customer view, persona rule)
            grant = round(share * min(mid, cap), 2)
            items.append({"label": f"KfW 458 base grant {share:.0%} (estimate, eligible up to €{cap:,.0f})", "qty": 1,
                          "unit": "flat", "unit_price_eur": -grant, "total_eur": -grant})
            cost["heatpump"][0] -= share * min(lo, cap)
            cost["heatpump"][1] -= share * min(hi, cap)
    total = round(sum(i["total_eur"] for i in items), 2)

    # economics: one year before and after
    price = home.electricity_price_eur_per_kwh
    # EEG: full rate for the first 10 kWp, lower rate above; one blended rate for the whole system
    r10, r_above = price_of("feed_in_eur_per_kwh", overrides)[0], price_of("feed_in_above_10kwp_eur_per_kwh", overrides)[0]
    feed_in = (min(pv_total, 10) * r10 + max(0.0, pv_total - 10) * r_above) / pv_total if pv_total else r10
    house = max(0.0, home.total_demand_kwh - home.ev_kwh - home.heatpump_kwh)
    after = sim(round(house), round(home.ev_kwh), round(home.heatpump_kwh + hp_el), round(pv_total, 2),
                round(home.y_kwh_per_kwp, 1), (bat_kwh if bat_rec else 0.0) + existing_bat)
    if home.existing_pv_kwp:
        before = sim(round(house), round(home.ev_kwh), round(home.heatpump_kwh), round(home.existing_pv_kwp, 2),
                     round(home.y_kwh_per_kwp, 1), existing_bat)
    else:
        before = {"import": home.total_demand_kwh, "export": 0.0}
    elec_before = before["import"] * price - before["export"] * feed_in
    fuel_before = 0.0
    if hp_rec and heat and home.heating_type not in ELECTRIC_HEATING:
        fuel_before = heat / price_of("boiler_efficiency", overrides)[0] \
            * price_of(FUEL.get(home.heating_type, "gas_eur_per_kwh"), overrides)[0]
    elec_after = after["import"] * price - after["export"] * feed_in
    savings = elec_before + fuel_before - elec_after
    gen = after["generation"]
    economics = {
        "total_demand_kwh": round(after["load"]),
        "self_consumption_pct": round(100 * after["self_used"] / gen, 1) if gen else 0.0,
        "autarky_pct": round(100 * after["self_used"] / after["load"], 1) if after["load"] else 0.0,
        "annual_savings_eur": round(savings),
        "payback_years": round(total / savings, 1) if savings > 0 and total else None,
        "bill_today_eur_per_month": round((elec_before + fuel_before) / 12),
        "bill_after_eur_per_month": round(elec_after / 12),
    }
    assumptions = list(home.assumptions) + ([hp_note] if hp_rec and hp_note else [])
    return {"home": home, "sizing": sizing, "sizes": sizes, "modules": pv_modules, "locks": lock, "profile": prof,
            "retrofit": retrofit,
            "price": {"items": items, "total_eur": total, "cost": cost}, "pv_core": (pv_kwp - hp_pv) if pv_rec else None,
            "economics": economics, "after": after, "assumptions": assumptions,
            "pv_total": pv_total, "hp_el": hp_el, "heat": heat}


def missing_fields(facts: dict, base: dict) -> list[str]:
    """Inputs not given whose plausible values are tried for ranges and impact."""
    out = []
    if all(facts.get(k) is None for k in ("total_demand_kwh", "annual_demand_kwh", "num_inhabitants")):
        out.append("total_demand_kwh")
    if facts.get("has_existing_pv") is None:
        out.append("has_existing_pv")
    roof_measured = facts.get("roof_width_m") is not None and facts.get("roof_length_m") is not None
    for k in ("region", "roof_area_sqm", "roof_orientation_deg", "heating_type", "electricity_price_eur_per_kwh"):
        if facts.get(k) is None and not (k == "roof_orientation_deg" and facts.get("roof_type") == "flat") \
                and not (k == "roof_area_sqm" and roof_measured):
            out.append(k)
    if base["sizes"]["heatpump"] and facts.get("heating_demand_kwh") is None and not facts.get("house_size_sqm"):
        out.append("heating_demand_kwh")
    if facts.get("has_ev") is None and not facts.get("ev_planned"):
        out.append("has_ev")
    return out


def rel(a, b):
    a, b = a or 0, b or 0
    return abs(a - b) / max(abs(b), 1e-9) if (a or b) else 0.0


def reasons_for(key, r, no_battery_autarky):
    p, h, s = PARAMS, r["home"], r["sizing"]
    size = r["sizes"][key]
    line = r["profile"]["pv_line"]
    who = f"installer {r['profile']['installer']}'s" if r["profile"]["installer"] else "comparable expert"
    if key == "pv":
        if r["locks"]["pv"]:
            if s.capped_from is not None and r["locks"]["pv"]["recommended"]:
                return [f"set by the installer, but the roof holds only {s.modules_fitting} modules: cut to "
                        f"{size:g} kWp"]
            return ["set by the installer"]
        if r["retrofit"] and not size:
            return [f"you already have {h.existing_pv_kwp:g} kWp; in retrofits experts add storage or a wallbox, "
                    "not more panels"]
        if not size:
            return [f"your existing {h.existing_pv_kwp:g} kWp already covers what experts install for this demand"]
        if r["retrofit"]:
            return [f"you already have {h.existing_pv_kwp:g} kWp; {r['modules']} extra modules only for the heat pump"]
        out = [f"{h.total_demand_kwh:,.0f} kWh/yr: {who} designs install {line['a_kwp']:.1f} kWp "
               f"+ {line['b_kwp_per_mwh']:.2f} kWp per MWh"
               if not r["profile"]["pv_packages"] else
               f"{h.total_demand_kwh:,.0f} kWh/yr: installer {r['profile']['installer']} most often sells the "
               f"{size:g} kWp package to homes with this demand"]
        gen = size * h.y_kwh_per_kwp
        out.append(f"{r['modules']} new modules produce ~{gen:,.0f} kWh/yr ({h.y_kwh_per_kwp:,.0f} kWh per kWp"
                   + (f" in {h.region}" if h.region else ", German average") + ")"
                   + (f", plus ~{h.existing_pv_kwp * h.y_kwh_per_kwp:,.0f} from your existing {h.existing_pv_kwp:g} kWp"
                      if h.existing_pv_kwp else ""))
        if s.roof == "too_small":
            out.append(f"the roof is the limit: it holds only {s.modules_fitting} modules "
                       f"({s.capped_from} would match your demand)")
        elif s.heatpump_suggested and r["sizes"]["heatpump"]:
            out.append(f"includes {s.heatpump_extra_modules} modules for the heat pump on the spare roof")
        return out[:3]
    if key == "battery":
        if r["locks"]["battery"]:
            return ["set by the installer"]
        if h.has_existing_battery:
            return ["you already have a battery"]
        if not size:
            return ["no PV to charge a battery from"]
        return [f"{size:g} kWh is what {who} designs most often pair with ~{r['pv_total']:.0f} kWp of PV "
                f"(a battery is in {p['battery']['share_with_pv']:.0%} of expert PV offers)",
                f"stores the midday surplus for the evening: autarky {no_battery_autarky:.0f}% → "
                f"{r['economics']['autarky_pct']:.0f}%"]
    if key == "wallbox":
        if r["locks"]["wallbox"]:
            return ["set by the installer"]
        if size:
            return [("you have an EV" if h.has_ev else "you plan an EV") + f"; {size:g} kW is the standard home charger"]
        return ["no EV now or planned"]
    if r["locks"]["heatpump"]:
        return ["set by the installer"]
    if size:
        return [f"your {h.heating_type} heating could run on the spare roof's solar power",
                f"{r['heat']:,.0f} kWh heat/yr ÷ {p['heatpump_full_load_hours']} full-load hours → {size:g} kW, "
                f"using ~{r['hp_el']:,.0f} kWh electricity"]
    if h.heating_type in ELECTRIC_HEATING:
        return [f"your heating is already electric ({h.heating_type}), no heat pump needed"]
    if h.heating_type is None:
        return ["heating type unknown, so no heat-pump decision yet"]
    if s.roof == "unknown":
        return [f"{h.heating_type} heating could switch to a heat pump; roof area needed to check it fits"]
    return ["the roof is fully used by the PV for your electricity demand"]


def fit_budget(facts: dict, locks: dict, overrides: dict, base: dict, installer: str | None):
    """(locks, note): smaller battery first, then less PV, until the price is within budget_eur (unlocked parts only)."""
    budget = facts.get("budget_eur")
    if not budget or base["price"]["total_eur"] <= budget:
        return locks, None
    tries = []
    if not locks.get("battery") and base["sizes"]["battery"]:
        smaller = [s for s in PARAMS["battery"]["catalogue_kwh"] if s < base["sizes"]["battery"]]
        tries += [{"battery": {"recommended": True, "size": s}} for s in reversed(smaller)]
        tries.append({"battery": {"recommended": False}})
    if not locks.get("pv") and base["sizes"]["pv"]:
        bat = tries[-1] if tries else {}
        step = PARAMS["module_w"] / 1000
        kwp = base["sizes"]["pv"]
        while kwp - step >= 2:
            kwp = round(kwp - step, 2)
            tries.append({**bat, "pv": {"recommended": True, "size": kwp}})
    for t in tries:
        trial = {**locks, **t}
        if core(facts, trial, overrides, installer)["price"]["total_eur"] <= budget:
            return trial, f"reduced to fit your budget of €{budget:,.0f}"
    return locks, f"even the smallest sensible design is above your budget of €{budget:,.0f}"


def design(facts: dict, locks: dict | None = None, overrides: dict | None = None, installer: str | None = None) -> dict:
    locks, overrides = locks or {}, overrides or {}
    base = core(facts, locks, overrides, installer)
    user_locks = dict(locks)
    locks, budget_note = fit_budget(facts, locks, overrides, base, installer)
    budget_keys = [k for k in locks if k not in user_locks]
    if budget_keys:
        base = core(facts, locks, overrides, installer)
        for k in budget_keys:                    # budget cuts are the engine's choice, not installer locks
            base["locks"][k] = {}
    if budget_note:
        base["assumptions"].append({"field": "budget_eur", "value": facts["budget_eur"], "note": budget_note})
    plausible = PARAMS["plausible"]
    # an unknown roof is not probed: a guessed roof would cap the PV range; the roof check ranks it as a floor instead
    runs = {f: [core({**facts, f: v}, locks, overrides, installer) for v in plausible[f]]
            for f in missing_fields(facts, base) if f != "roof_area_sqm"}
    every = [base] + [r for rs in runs.values() for r in rs]

    # missing inputs: impact = largest relative move of PV size, price or savings
    score = {}
    for f, rs in runs.items():
        score[f] = max(max(rel(r["sizes"]["pv"], base["sizes"]["pv"]), rel(r["price"]["total_eur"], base["price"]["total_eur"]),
                           rel(r["economics"]["annual_savings_eur"], base["economics"]["annual_savings_eur"])) for r in rs)
    level = {f: "high" if s >= 0.15 else "medium" if s >= 0.05 else "low" for f, s in score.items()}
    whys = {m["field"]: m["why"] for m in base["sizing"].missing_inputs}
    floor = {"high": 0.15, "medium": 0.05, "low": 0.0}
    for m in base["sizing"].missing_inputs:     # the roof check's own impact is a floor
        if score.get(m["field"], -1) < floor[m["impact"]]:
            level[m["field"]], score[m["field"]] = m["impact"], floor[m["impact"]]
    missing = sorted(({"field": f, "why": whys.get(f, WHY.get(f, "")), "impact": level[f]} for f in level),
                     key=lambda m: -score[m["field"]])

    no_bat = None
    if base["sizes"]["battery"]:
        r0 = core(facts, {**locks, "battery": {"recommended": False}}, overrides, installer)
        no_bat = r0["economics"]["autarky_pct"]

    # ranges: runs that switch to a retrofit (existing PV) are a different design, so they only rank the question
    every = [r for r in every if r["retrofit"] == base["retrofit"]]
    comps = {}
    for k in COMPONENTS:
        size = base["sizes"][k]
        locked = bool(base["locks"][k])
        if k == "pv" and not base["sizes"]["heatpump"]:
            seen = [r["pv_core"] for r in every if r["pv_core"]]   # heat-pump PV only counts once a heat pump is in
        else:
            seen = [r["sizes"][k] for r in every if r["sizes"][k]]
        rng = [round(size, 2)] * 2 if locked and size else ([round(min(seen), 2), round(max(seen), 2)] if size else None)
        spread = (rng[1] - rng[0]) / size if size and rng else 1
        conf = "high" if locked or spread < 0.1 else "medium" if spread < 0.3 else "low"   # from missing inputs only
        es = PARAMS.get("expert_spread", {}).get(k)
        if es and size and not locked and not (k == "pv" and base["retrofit"]):
            # widen to what comparable expert designs choose (10-90% of expert ÷ engine on train)
            lo_r, hi_r = es.get(base["profile"]["installer"] or "all", es["all"])
            rng = [round(min(rng[0], size * lo_r), 2), round(max(rng[1], size * hi_r), 2)]
        if k == "heatpump" and size and not locked and any(a["field"] == "heating_demand_kwh" for a in base["assumptions"]):
            conf = "low"
        reasons = reasons_for(k, base, no_bat)
        if k in budget_keys:
            reasons = [budget_note] + reasons[:2]
        c = {"recommended": size is not None, "size": round(size, 2) if size else None, "unit": UNITS[k],
             "range": rng, "confidence": conf, "locked": locked, "reasons": reasons}
        if k == "pv" and size:
            c["quantity"] = base["modules"]
        if k == "pv" and base["sizing"].modules_fitting is not None:
            c["max_modules"] = base["sizing"].modules_fitting          # hard roof cap, net of existing panels
            if rng:
                cap_kwp = round(c["max_modules"] * base["sizing"].module_w / 1000, 2)
                c["range"] = [min(rng[0], cap_kwp), min(rng[1], cap_kwp)]
        comps[k] = c

    pv_new = base["sizes"]["pv"] or 0
    bundle = next((name for bound, name in BUNDLES if pv_new < bound), "XL") if pv_new else None
    pr = base["price"]
    rec = [k for k in COMPONENTS if base["sizes"][k]]          # range covers only what is recommended
    lo = min(sum(r["price"]["cost"][k][0] for k in rec) for r in every)
    hi = max(sum(r["price"]["cost"][k][1] for k in rec) for r in every)
    return {"components": comps,
            "price": {"items": pr["items"], "total_eur": pr["total_eur"], "range_eur": [round(lo, -1), round(hi, -1)]},
            "economics": base["economics"], "bundle": bundle, "assumptions": base["assumptions"],
            "missing_inputs": missing, "installer_profile": base["profile"]["installer"], "params_version": VERSION}


def steps(component: str, size):
    """(smaller, larger) size one catalogue step away (PV: ±2 modules ≈ ±0.9 kWp), None at the ends."""
    if component == "pv":
        step = 2 * PARAMS["module_w"] / 1000
        return (round(size - step, 2) if size and size - step >= 2 else None), round((size or 0) + step, 2)
    cat = {"battery": PARAMS["battery"]["catalogue_kwh"], "heatpump": PARAMS["heatpump_catalogue_kw"],
           "wallbox": [11, 22]}[component]
    if not size:
        return None, None
    smaller = [s for s in cat if s < size]
    larger = [s for s in cat if s > size]
    return (smaller[-1] if smaller else None), (larger[0] if larger else None)


def explain(facts: dict, locks: dict | None, overrides: dict | None, component: str,
            installer: str | None = None) -> dict:
    """Reasons plus what-ifs for one component: on / off and one size step down / up, each with deltas."""
    locks, overrides = locks or {}, overrides or {}
    base = design(facts, locks, overrides, installer)
    b = core(facts, locks, overrides, installer)
    c = base["components"][component]
    name = {"pv": "PV", "battery": "battery", "heatpump": "heat pump", "wallbox": "wallbox"}[component]
    size = b["sizes"][component]
    changes = []
    if c["recommended"]:
        changes.append((f"no {name}", {**locks, component: {"recommended": False}}))
        down, up = steps(component, size)
        for s in (down, up):
            if s:
                changes.append((f"{name} {s:g} {UNITS[component]} instead of {size:g}",
                                {**locks, component: {"recommended": True, "size": s}}))
    else:
        changes.append((f"add {name}", {**locks, component: {"recommended": True}}))
    what_if = []
    for label, lk in changes:
        r = core(facts, lk, overrides, installer)
        e0, e1 = b["economics"], r["economics"]
        delta = {"price_eur": round(r["price"]["total_eur"] - b["price"]["total_eur"]),
                 "annual_savings_eur": e1["annual_savings_eur"] - e0["annual_savings_eur"],
                 "payback_years": round(e1["payback_years"] - e0["payback_years"], 1)
                 if e0["payback_years"] and e1["payback_years"] else None,
                 "autarky_pct": round(e1["autarky_pct"] - e0["autarky_pct"], 1),
                 "bill_after_eur_per_month": e1["bill_after_eur_per_month"] - e0["bill_after_eur_per_month"]}
        parts = [f"price {delta['price_eur']:+,} €", f"savings {delta['annual_savings_eur']:+,} €/yr",
                 f"autarky {delta['autarky_pct']:+.0f} pts"]
        if delta["payback_years"] is not None:
            parts.append(f"payback {delta['payback_years']:+.1f} yrs")
        what_if.append({"change": label, "effect": ", ".join(parts), "delta": delta, "locks": lk})
    return {"reasons": c["reasons"], "what_if": what_if}
