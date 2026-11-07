from benchmarks import band, build


def test_benchmarks_from_train_with_fallback():
    b = build()
    assert b["built_from"] == "train"
    top = [s for s in b["segments"] if s["level"] == 0]
    assert len(top) == 1 and top[0]["n"] == b["n_train"]  # level 0 covers every train home
    assert band(4500) == "4000-5000" and band(9000) == "6000+" and band(float("nan")) == "unknown"
    for s in b["segments"]:
        pv = s["pv_kwp"]
        assert pv is None or pv["p10"] <= pv["p50"] <= pv["p90"]
