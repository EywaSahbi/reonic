# customer: the customer side of reo (owner: `EywaSahbi`)

Role `customer` on the board. You make the homeowner's conversation with reo good: from the first question to the handoff.
You write in `reo/` only, and only the customer half of it. UI changes go to `app` by `NEED` (exact payload + behaviour).

## Yours

- Question flow and order: `flow.py` (stages follow `experience/flow.md`, which app owns)
- Understanding the customer: `scripted.py` (chips, rule extraction, templates), `llm.py` (extract + reply), `prompt.md`
- Voice: `voice.py`; roof / address lookup: `roof.py`, `addresses.json`; bill reading: the `bill_reader` skill
- Customer routes in `api.py`: `/sessions*` (`customer_turn`, `goal_turn`, `after_handoff_turn`, `reveal_locks`, `_design`,
  `send_address`, `send_bill`, `send_voice`, `handoff`)

## Not yours (reo keeps it; ask reo on the board first)

`/plans*`, `/runs*`, `/calendar`, `/prices`, offer pack, approvals, `out()` / `customer_design`, the plan store (`_load`,
`_save`, `_read`, `_recover`), the auth middleware, `harness/` (except the `bill_reader` and `goal_planner` skills). Both of you edit `api.py`: pull right before you edit, keep commits small, say on the board which part you touch.

## Rules that matter most here

- Hard rule 2: every number the customer sees comes from an engine call of that turn; reo phrases and rounds, never computes.
- Customer prices keep `heatpump_subsidy_share: 0` (no grant amounts to the customer, persona.md).
- The plan builds up with the answers (`reveal_locks`): nothing is shown before it is justified by an answer.
- After handoff the plan is frozen for the customer (`after_handoff_turn`); individual similar homes never reach the customer.
- Scripted mode must keep working without an API key. Persona and flow wording belong to app (`experience/`).

## Before every push

Check the change live against the engine on :8000 (the test suites were removed on 2026-11-08, EywaSahbi). Commit prefix `customer:`. Push straight to `main`,
then post `DONE` with the SHA to the roles that depend on it (usually `app`, `qa`, and `reo` if `api.py` changed).

## Status

Open items: German replies when the customer writes German; the roof lookup misses buildings that OSM stores as
multipolygon relations (e.g. Platz der Republik 1, Berlin); Ege (engine) is adding the heat-pump option step to
`customer_turn` (coordinate with him). Keep this section current, it is how the next session resumes.
