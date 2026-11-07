# Installer style: engine with vs without installer_profile (val)

Same `val` homes, engine parameters from `train` only. "With profile" fits the PV line and battery bands
on each installer's own `train` projects. Baseline: train medians, wallbox iff EV.

| Installer | Metric | Baseline | Engine, all installers | Engine, installer profile |
|---|---|---|---|---|
| 23c108b7 (n=51) | PV size within ±20 % | 46% | 37% | 46% |
| 23c108b7 (n=51) | Battery size within ±20 % | 73% | 79% | 72% |
| 23c108b7 | PV size MAE (kWp) | 3.4 | 3.17 | 3.13 |
| 23c108b7 | PV median bias (kWp, engine − expert) | | -0.70 | -0.05 |
| 2a8ba8e2 (n=187) | PV size within ±20 % | 51% | 49% | 51% |
| 2a8ba8e2 (n=187) | Battery size within ±20 % | 32% | 33% | 34% |
| 2a8ba8e2 | PV size MAE (kWp) | 2.49 | 2.27 | 2.24 |
| 2a8ba8e2 | PV median bias (kWp, engine − expert) | | +0.48 | +0.07 |

Overall: PV within ±20 % 46% → 50%, battery 43% → 42%, bundle match 56% → 56% (baseline 56%).
