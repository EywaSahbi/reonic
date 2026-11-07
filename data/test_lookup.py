from lookup import demand_band, percentile_of, segment, similar_projects, size_at, train

HOME = {"annual_demand_kwh": 4500, "has_ev": False, "heating_type": "gas"}


def test_segment_and_percentiles():
    s = segment(HOME)
    assert s["n"] >= 15 and s["key"].get("demand_band", "4000-5000") == "4000-5000"
    assert demand_band(6000) == "6000+" and demand_band(None) == "unknown"
    p25, p50, p75 = (size_at(HOME, "battery", q) for q in (25, 50, 75))
    assert p25 <= p50 <= p75
    assert percentile_of(HOME, "pv", 0) == 0 and percentile_of(HOME, "pv", 1e6) == 1
    assert segment({})["level"] == 0 or segment({})["n"] >= 15  # unknown home still gets a segment


def test_similar_projects_are_train_and_close():
    ids = set(train().project_id)
    sim = similar_projects(HOME, k=3)
    assert len(sim) == 3 and all(r["project_id"] in ids for r in sim)
    assert all(not r["has_ev"] for r in sim) and all(r["heating_type"] == "gas" for r in sim)
    dist = [abs(r["annual_demand_kwh"] - 4500) for r in sim]
    assert dist == sorted(dist)
