import pandas as pd

from build import build, split


def test_worked_example_and_split():
    df = build()
    row = df.set_index("project_id").loc["f1aedc4ad3f6c4d1"]  # docs/dataset_explanation.md section 8
    assert row.battery_kwh == 10.0 and row.wallbox_kw == 11.0
    assert row.pv_modules == 32 and 14 < row.pv_kwp < 16
    assert not row.has_heatpump and row.heating_type == "heatpump"

    sp = split(df)
    assert sp.project_id.is_unique and set(sp.split) == {"train", "val", "test"}
    per_customer = df.merge(sp).groupby("customer_contact_id").split.nunique()
    assert (per_customer == 1).all()  # no customer leaks across splits
    assert split(df).equals(sp)  # fixed seed
