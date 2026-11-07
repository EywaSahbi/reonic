"""Hourly profiles for the one-year simulation (METHOD.md step 4), written to engine/profiles.json.

Run once (needs demandlib, which needs pandas < 3, so it runs outside the engine venv):
    uv run --no-project --python 3.12 --with demandlib --with "pandas<3" --with holidays python tools/derive_profiles.py

- h0:  BDEW standard household load profile H0 for 2019 (demandlib), hourly, scaled to 1,000 kWh/yr
- pv:  PVGIS v5.3 hourly output of 1 kWp at the centre of Germany (Kassel), south 35°, 14% losses, 2019,
       shifted from UTC to CET, scaled to 1,000 kWh/yr (the engine multiplies by kWp × Y / 1,000)
- t2m: outdoor temperature (°C) for the same hours, to spread heat-pump demand over the year
Both are the same calendar year so sunny and cloudy days line up with the weekday pattern of H0.
Only a generic coordinate is sent to PVGIS.
"""
import json
import urllib.request
from pathlib import Path

import demandlib.bdew as bdew
import holidays

OUT = Path(__file__).parent.parent / "profiles.json"
YEAR = 2019
URL = ("https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat=51.31&lon=9.48&pvcalculation=1&peakpower=1&loss=14"
       f"&angle=35&aspect=0&startyear={YEAR}&endyear={YEAR}&outputformat=json")


def main():
    h0 = bdew.ElecSlp(YEAR, holidays=holidays.Germany(years=YEAR)).get_scaled_profiles({"h0": 1000})["h0"]
    h0 = h0.resample("h").sum().tolist()

    with urllib.request.urlopen(URL, timeout=120) as r:
        hourly = json.load(r)["outputs"]["hourly"]
    p = [x["P"] for x in hourly]
    t = [x["T2m"] for x in hourly]
    p, t = p[-1:] + p[:-1], t[-1:] + t[:-1]          # UTC -> CET
    total = sum(p)
    pv = [x / total * 1000 for x in p]

    assert len(h0) == len(pv) == 8760
    OUT.write_text(json.dumps({
        "_note": "hourly, 8,760 values each; see engine/tools/derive_profiles.py",
        "h0_kwh_per_1000": [round(x, 4) for x in h0],
        "pv_kwh_per_1000": [round(x, 4) for x in pv],
        "t2m_c": [round(x, 1) for x in t],
    }))
    print(f"wrote {OUT} (PVGIS 2019 yield at Kassel {total / 1000:.0f} kWh/kWp)")


if __name__ == "__main__":
    main()
