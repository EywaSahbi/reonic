# Challenge brief (summary of `Reonic_Hackathon_Challenge_final.pdf`)

Read the PDF for the full text. This is what matters for building.

## Mission

Turn a few facts about a home into a complete energy system design (PV, battery storage, heat pump, as appropriate, plus sizes) that decides the way an experienced installer's planner would, explains itself, and lets the planner refine it.

## Users

- **Planner** (primary; the minimum result serves them): wants a solid first design right away, full control to override any part, and reasons they can justify to the homeowner. Fears a black box.
- **Homeowner** (stretch goal, same engine): wants to understand the offer and try variants (bigger battery, no heat pump) in plain language, only within the options the installer allows. The home's data stays fixed. Fears being oversold.

"As appropriate" matters: recommending **no** battery or **no** heat pump can be the right expert decision.

## Why it is hard

- Decisions are coupled: PV size changes battery value; a heat pump raises consumption and so the PV size; an EV shifts load into the evening. Three independent guesses look plausible but are wrong.
- Experts apply implicit rules (typical sizes, budget limits, product availability, preferences). Data is noisy; rarely one correct answer.
- An LLM alone will not do it. AI must be a real part (statistical/ML models trained on the data qualify; an LLM is optional). A single ungrounded prompt does not count.

## Core goals

1. **Propose a complete system** from a small set of inputs: whether PV, battery, heat pump, and how large; coherent as a whole.
2. **Let the user refine it**: when the planner changes an input or a component, the rest adapts the way an expert expects, and the planner sees why.
3. **Prove it decides like an expert**: measure closeness to expert designs on projects the system has not seen.

## Minimum result

- For a given project: a complete design (PV, battery, heat pump as appropriate) with a short explanation.
- Measured closeness to expert designs on unseen projects.
- The planner changes at least one input or component and gets an updated design.

## Stretch goals

- Analysis of where and why designs deviate from the experts.
- Alternatives and confidence for every recommendation.
- A validation view for planners ("this battery is unusually large for a home like this") or a homeowner exploration view, on the same engine.

## The demo moment (five minutes, Sunday)

1. A planner enters a few basic facts about a home.
2. A complete system appears with a short explanation.
3. The design is refined, e.g. "the family is buying an electric car next year", and adapts sensibly.
4. It is checked against reality: compared with the expert design for the same project, plus how well it does across many projects.

## Judging (equal weight)

- **Technical depth**: how well designs reproduce expert decisions, and how convincingly that is measured.
- **User fit**: works for planner and/or homeowner, including refining and understanding a design.
- **Business impact**: clear value (time per offer, design quality, win rate).
- **Execution and demo**: works end to end, convincing story.

## Submission (Sun 8 Nov 2026, 15:00)

- Working demo, end to end (a short recording as fallback is recommended).
- Code (e.g. GitHub link) with a short README: setup, approach, known limitations.
- Short pitch deck: problem, solution, evaluation, value for installers and homeowners.

## Good to know

- Free choice of approach. Do not spend time on infrastructure; a simple, well-explained solution beats a complex one that does not run.
- **Use the data only for this hackathon; do not share it outside the team.**
- Reonic experts are on site to answer questions on data, domain and installer workflow (ask via a human: board `DECISION`).

## The data (`Project Data/`)

Two folders, apparently one installer each: `2a8ba8e2/` (~1,277 projects) and `23c108b7/` (~342 projects). Each has:
- `projects_status_quo.csv`: one row per project, the inputs: energy demand (Wh/yr), price per Wh, price increase, EV (+ km/yr), existing PV / storage / wallbox, existing heating type and demand, house size and year, inhabitants. Many columns are mostly empty.
- `project_options_parts.csv`: the offered design as line items per option (`option_id`, `option_number`, `technology`, `component_type`, `component_name`, `quantity`, size columns). Some projects have several options.

First observations (unverified, data agent owns the truth): `inverter_power_kw` is filled on `BatteryStorage` rows and `battery_capacity_kwh` on `Inverter` rows (columns look swapped); module rows with `module_watt_peak` are rare, PV size may need to come from package names ("Complete Package 2 Sigenergy 10.8kWp + 9kWh") or module counts; heat pumps appear only in `2a8ba8e2`.
