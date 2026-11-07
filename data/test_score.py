from score import COMPONENTS, load, metrics, normalise


def test_perfect_predictions_score_one():
    truth = load("val")
    pred = normalise(truth[["project_id", *[f"has_{c}" for c in COMPONENTS], *COMPONENTS.values()]])
    r = metrics(truth, pred)
    assert r["bundle_match"] == 1.0
    for c, v in r["components"].items():
        assert v["presence_acc"] == 1.0
        assert v["within_tol"] in (1.0, None)
