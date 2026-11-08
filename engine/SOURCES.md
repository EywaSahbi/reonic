# engine/ sources

Every number the engine did not compute itself, where it came from and where it is used. Checked 2026-11-07.
Most price sources are installer, comparison or advice sites (not official tables), so prices are shown as ranges and estimates until the installer confirms the quote.

## Weather, sun and PV yield

| Source | What we took | Used in |
|---|---|---|
| [PVGIS v5.3 PVcalc API](https://re.jrc.ec.europa.eu/api/v5_3/PVcalc) (EU Joint Research Centre, SARAH-3 satellite irradiance 2005–2023) | Yearly yield of 1 kWp at the 16 state capitals, south 35°, 14% losses; 20 orientation / tilt variants at Kassel → Y = 1,082 kWh/kWp/yr (national), 988–1,139 per state, east / west ≈ 0.80 | `tools/derive_y.py` → `params.json` `pv_yield` |
| [PVGIS v5.3 seriescalc API](https://re.jrc.ec.europa.eu/api/v5_3/seriescalc) | Hourly PV output of 1 kWp and outdoor temperature, Kassel, 2019 | `tools/derive_profiles.py` → `profiles.json` |
| [Marktstammdatenregister](https://www.marktstammdatenregister.de) (Bundesnetzagentur), public unit search | Number of solar units in operation, 2–30 kWp, per federal state (4.5 M systems), to weight Y by where rooftop PV is | `tools/derive_y.py` |

## Load profiles

| Source | What we took | Used in |
|---|---|---|
| [demandlib](https://github.com/oemof/demandlib) (oemof), BDEW standard load profile H0 | Hourly household profile for 2019 incl. German holidays | `tools/derive_profiles.py` → `profiles.json` |
| [HTW Berlin: representative electrical load profiles of residential buildings](https://solar.htw-berlin.de/elektrische-lastprofile-fuer-wohngebaeude/) (Tjaden, Bergner, Weniger, Quaschning; CC BY-NC 4.0; data: public share linked there, password `profile`) | 74 measured single-family homes, 1-minute active power, one year → factor measured ÷ H0 self-use, 0.71–0.95 (e.g. PV 2× demand + 2 kWh/MWh battery: H0 86%, measured 77% autarky). Raw data not in the repo, only the factor table | `tools/derive_calibration.py` → `params.json` `sim_calibration`, `sim.py` |

## Prices (`prices.json`)

| Source | What we took | Used in |
|---|---|---|
| [photovoltaik.info: cost breakdown (2026-05-07)](https://www.photovoltaik.info/kostenaufschluesselung-preise-module-speicher-wechselrichter/) | Example quote 10 kWp: modules 25 × ~150 € = 3,750 €, hybrid inverter 1,800 €, mounting system & DC material 1,500 €, installation + AC + registration 3,000 €, scaffolding 500 € (PV part 10,550 €); modules 100–200 €/pc, inverter 500–2,000 € | Quote lines: the PV total is split in these proportions (`PV_SPLIT` in design.py); the total itself stays the sourced model |
| [reduco.ai: PV installation costs 10 kWp (2026-08-31)](https://reduco.ai/blog/solar/photovoltaik-montage-kosten-ablauf) | Scaffolding 500–1,500 €, substructure 80–250 €/kWp, AC connection meter cabinet 500–900 €, commissioning + grid connection 150–400 €, all installation 300–600 €/kWp | Cross-check of the split lines |
| [ema-energiewelt: wallbox installation 2026](https://ema-energiewelt.de/wissen/wallbox-installation-kosten-elektriker-2026), [clean-invoice: wallbox installation](https://www.clean-invoice.com/wissen/allgemein/wallbox-installieren-kosten) | 11 kW device 400–1,000 €, installation 500–2,500 €, all-in 800–2,200 € | Wallbox lines: device 40 % / installation 60 % of the wallbox price (`WALLBOX_SPLIT`) |
| [solarserver.de, 2025-09-30](https://www.solarserver.de/2025/09/30/photovoltaik-anlagen-seit-januar-um-15-prozent-guenstiger/) | ~10 kW PV system: mean 14,973 € (Jan 2025) → 12,768 € (Sep 2025), −15% | PV price |
| [elektronik-zeit.de: PV costs 2026](https://elektronik-zeit.de/photovoltaik-leitfaden-2026/photovoltaik-kosten/) | 2026 mean ~1,015 €/kWp turnkey; 10 kWp without storage 9,700–14,300 €; with 10 kWh storage 12,500–17,450 € | PV price (2,500 € + 1,000 €/kWp, low 2,000 + 770, high 3,000 + 1,200), battery cross-check |
| [Yello](https://www.yello.de/wissen/solar/solaranlage-kosten/), [42watt](https://42watt.de/magazin/photovoltaik-im-einfamilienhaus), [enter](https://www.enter.de/blog/kosten-solaranlage) | 10 kWp turnkey 9,500–17,000 €; 1,200–2,000 €/kWp (2025) | PV high end |
| [reduco.ai: battery prices 2026](https://reduco.ai/blog/stromspeicher-kosten-vergleich-2026) | Verbraucherzentrale range 300–700 €/kWh incl. installation; installed mean ~315 €/kWh (270–420) | Battery price (800 € + 350 €/kWh, low 500 + 280, high 1,200 + 500) |
| [ema-energiewelt: home storage 2025](https://ema-energiewelt.de/wissen/batteriespeicher-2025-lohnt-sich-die-investition) | 2025 gross installed 700–1,100 €/kWh; system price index 477 €/kWh (2025) | Battery high end |
| [ADAC (via reduco.ai: wallbox costs 2026)](https://reduco.ai/blog/solar/wallbox-kosten-installation-2026), [autozeitung](https://www.autozeitung.de/wallbox-kosten-202955.html) | 11 kW wallbox incl. installation 1,200–3,500 €; device 675–1,570 € in the ADAC test; up to 11 kW only needs notification | Wallbox price (2,000 €, 1,200–3,500), 11 kW default |
| [ADAC: air-water heat pump](https://www.adac.de/rund-ums-haus/energie/versorgung/luft-wasser-waermepumpe/) | 20,000–35,000 € incl. installation | Heat-pump price |
| [Vattenfall: heat pump costs](https://www.vattenfall.de/infowelt-energie/waermepumpe/waermepumpe-kosten-einfamilienhaus) | Device + installation incl. removal of the old boiler 24,300–43,900 €; 3–5 days installation | Heat-pump price (18,000 € + 1,300 €/kW, low 14,000 + 700, high 24,000 + 1,800) |
| [web.de / utopia (Verbraucherzentrale figure)](https://web.de/magazine/ratgeber/utopia/luft-wasser-waermepumpe-funktionsweise-kosten-installation-wissen-42136572) | Mean ~36,000 € in 2025 | Heat-pump price cross-check |
| [reduco.ai: KfW 458 from 2026-07-21](https://reduco.ai/blog/kfw-458-heizungstausch), [cleanthinking: heating subsidy 2026](https://www.cleanthinking.de/heizungsfoerderung/) | Base grant 30%; eligible costs capped at 28,000 € per home since 2026-07-21; bonuses (speed, income, efficiency) case by case | KfW base grant line item (30% of min(cost, 28,000 €)) |
| [reduco.ai: feed-in tariff 2026 / 2027](https://reduco.ai/blog/einspeiseverguetung-aenderungen-2026-2027), [forum-verlag](https://forum-verlag.com/fachwissen/bau-und-gebaeudemanagement/pv-einspeiseverguetung/) | EEG partial feed-in: 7.78 ct/kWh (Feb–Jul 2026) → 7.70–7.71 ct from Aug 2026 up to 10 kWp; 6.73 ct (10–40 kWp part) − 1% | Feed-in 7.71 ct ≤ 10 kWp, 6.66 ct above |
| [BDEW Gaspreisanalyse 08/2026](https://www.bdew.de/media/documents/BDEW_Gaspreisanalyse_082026.pdf) | Single-family house (20,000 kWh) 11.93 ct/kWh in 2026 | Gas 12 ct/kWh (heat-pump savings) |
| [cleanthinking: heating costs winter 2026/27](https://www.cleanthinking.de/?p=1073584) | Destatis: heating oil July 2026 118.11 €/hl excl. VAT ≈ 14.1 ct/kWh | Oil 14 ct/kWh |
| [energiefluss24: district heating](https://www.energiefluss24.de/waermepumpe/was-kostet-fernwaerme), [co2online press release 2026](https://www.co2online.de/co2online/Presse/Pressemitteilungen_nach_Jahren/2026/261007-PM-Fernw%C3%A4rme.pdf) | BDEW/VKU mean 15.6 ct/kWh; co2online 15 ct (renewable) – 17 ct (fossil) for a single-family house | District heating 16 ct/kWh |
| [BDEW Strompreisanalyse 10/2026](https://www.bdew.de/media/documents/BDEW_Strompreisanalyse_102026_1.pdf) | Household mean 37.3 ct/kWh (new contracts, 3,500 kWh) | Reference only: default stays 0.32 €/kWh (owner's choice = dataset default) |

## Technical parameters (`params.json` `_sources`)

| Source | What we took | Used in |
|---|---|---|
| [Fraunhofer ISE: heat pump field test interim results 2024](https://www.ise.fraunhofer.de/de/presse-und-medien/news/2024/waermepumpenfeldstest-zwischenergebnisse-bestaetigen-effizienten-betrieb-auch-im-altbau.html), [WPsmart im Bestand](https://www.ise.fraunhofer.de/de/forschungsprojekte/wp-im-bestand.html) | Air-water heat pumps in existing homes: seasonal performance factor 3.3 (2024, 2.4–4.0); 3.1 (2020); final 2025 reported 3.4 (secondary source) | COP 3.3 |
| [electrive: ADAC on charging losses](https://www.electrive.net/2020/07/23/ladeverluste-laut-adac-oft-hoeher-als-angegeben/), [ADAC test NIO ET7](https://assets.adac.de/image/upload/Autodatenbank/Autotest/AT6279_nio-et7-100-kwh-inkl-batterie/nio-et7-100-kwh-inkl-batterie.pdf), [notebookcheck: Ioniq 6 in the ADAC Ecotest](https://www.notebookcheck.com/Hyundai-Ioniq-6-Sparsamstes-E-Auto-im-ADAC-Ecotest-vor-Tesla-Model-3.740075.0.html) | ADAC Ecotest includes charging losses; examples 15.5 (Ioniq 6) – 20.4 (NIO ET7) kWh/100 km; losses 10–15% | EV 0.18 kWh/km |
| [co2online: Stromspiegel](https://www.co2online.de/energie-sparen/strom-sparen/strom-sparen-stromspartipps/stromverbrauch-5-personen-haushalt/) | Stromspiegel 2025, single-family house without electric hot water: 1,800 / 2,700 / 3,500 / 3,800 / 4,500 kWh for 1–5 people | Demand from `num_inhabitants` |
| [Jinko JKM430N-54HL4R datasheet](https://www.siblik.com/fileadmin/mam/medias/docus/175/Artikel_JKM430N54HL4RBD_Datenblatt.pdf) | 430 W, 1,762 × 1,134 mm = 2.0 m² | Module 430 W, 2.0 m² (roof check) |
| [BürgerNetzwerkSolar: heat pump sizing](https://www.worms.de/neu-de-wAssets/docs/zukunft-gestalten/klima-umwelt/Energie/BuergerSolarBeratung/_BNS_Waermepumpe-Praxistipps-zur-Auslegung.pdf), [reduco.ai: heat pump sizing](https://reduco.ai/blog/heizung/waermepumpe-dimensionieren-kw-tabelle) | Heat load = yearly heat demand ÷ full-load hours; 1,800–2,100 h for existing single-family houses (unrenovated 1,800–2,200, well insulated far less) | 2,000 full-load hours |
| [wohnen-und-finanzieren: energy use by building age](https://wohnen-und-finanzieren.de/blog/energieverbrauch-einfamilienhaus), [Schwäbisch Hall 2014](https://www.schwaebisch-hall.de/content/dam/dambsh/unternehmen/dokumente/presseinformationen/archiv/2014/2014_05_Private%20Energiewende.pdf) | Heating demand by age: before 1978 unrenovated 200–300, 1978–2000 120–200, 2000–2015 70–120, new 30–70 kWh/m²a; new builds 60–70 kWh/m² | Heat demand from `house_size_sqm` × age (200 / 150 / 100 / 60) |

| [UBA: CO2 per kWh of electricity 2025](https://www.umweltbundesamt.de/themen/co2-emissionen-pro-kilowattstunde-strom-2025-nur), [UBA Strom- und Wärmeversorgung in Zahlen](https://www.umweltbundesamt.de/themen/klima-energie/energieversorgung/strom-waermeversorgung-in-zahlen) | German electricity mix 344 g/kWh (2025, estimate; 353 in 2024, 379 in 2023). Gas 201 g and heating oil 266 g per kWh fuel (UBA emission factors, found via secondary tables, original not opened). District heating: no single official factor, so no CO2 shown | `co2_kg_per_kwh`, `heating_comparison` |

## Expert designs

| Source | What we took | Used in |
|---|---|---|
| `data/processed/projects.parquet` + `split.csv` (data role, from `Project Data/`), **train split only** | PV line 6.15 + 0.603 kWp/MWh, battery size per PV band, battery share 95%, catalogue sizes, heat-pump sizes, median heat demand 15,800 kWh, installer profiles | `tools/derive_params.py` → `params.json` |

## Still placeholders (no citable source)

- Usable roof share 0.75 (edges, chimneys, windows): question for the Reonic experts.
- Existing PV of unknown size: 5 kWp.
- Battery efficiency 95% each way, max 0.5 × capacity per hour; EV charging 18–22 h; heat-pump load by degree hours (base 15 °C, 15% hot water).
