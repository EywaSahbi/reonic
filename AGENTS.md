# AGENTS.md

Instructions for every coding agent (Claude Code, Codex, Cursor, ...) and every human on this repo.
Three humans, five agents, one message board. Agents hand work to each other on the board; humans step in only for critical decisions.

## Product: reo

**reo** is an AI companion that lives on an installer's website (Reonic is the operating system for installers).

1. **Customer side.** A homeowner starts with the bare minimum ("we use about 4,500 kWh a year"). reo answers straight away with a first design and a price range ("about 8 kWp of solar, roughly €X–Y"), then says what would make it more precise ("tell me your roof area or address and I can firm this up"). The customer adds facts, asks why things cost what they cost, and when happy hands the plan to the installer.
2. **Installer side.** The planner sees the handed-over plan in their own reo view: the design, why each decision was made, how sure reo is, and flags where it differs from what experts did for similar homes. They edit anything, the rest of the design re-derives, and they send the customer the final plan and quote.

**Architecture principle: numbers come from the engine, words come from reo.**
- The **engine** is deterministic: every size, yes/no and price is computed by code, explainable, reproducible.
- **reo** is an LLM layer wrapped around the engine. It talks, decides which question to ask next, calls the engine as tools, and explains the engine's reasons. It never invents a number.
- The **dataset** is the evidence: it defines what experts actually delivered, and we validate the engine against it on projects it has never seen.

Challenge background: [docs/challenge-brief.md](docs/challenge-brief.md). Data facts: [docs/dataset_explanation.md](docs/dataset_explanation.md). Timeline: [docs/plan.md](docs/plan.md).
Build: Sat 7 Nov 14:00 → **submission Sun 8 Nov 15:00** (demo + code + README + short pitch deck).

## Team and ownership

You write only inside your own folder. You may **read and run** anything in the repo.

| GitHub user | Role | Writes only in | Builds |
|---|---|---|---|
| `egeunluer` | **engine** | `engine/` | deterministic design core + pricing, HTTP API on `:8000` |
| `EywaSahbi` | **reo** | `reo/` | reo backend: LLM layer, conversation state, next question, engine tools, plan store + handoff, scripted fallback, API on `:8001` |
| `EywaSahbi` | **data** | `data/` | expert designs, split, scoring, benchmarks for flags, reality-check numbers |
| `RaneemK-commits` | **app** | `app/`, `experience/`, `pitch/`, `README.md` | the web UI (installer website + reo chat widget + installer dashboard); reo's creative direction; pitch |
| `RaneemK-commits` | **qa** (Codex) | `qa/` | verifies every delivery, end-to-end smoke test, demo rehearsal; reports, never fixes |
| humans only | shared | `AGENTS.md`, `CLAUDE.md`, `docs/`, `tools/`, `.claude/`, `.gitignore`, `.gitattributes` | |
| nobody | raw data | `Project Data/` (read-only, never edit) | |

Need a change in a folder you do not own? Post a `NEED` on the board to its owner. Never edit it yourself, not even "just one line".
A pre-commit hook enforces this (see Setup). Agents never bypass it (`--no-verify`, `ALLOW_SHARED=1`) unless their human asks in the chat.

Each role folder holds `AGENTS.md` (role brief), `STATUS.md` (live backlog, what is published, decisions) and, for engine, reo and data, a `CONTRACT.md` (what the folder publishes for others).

**reo's voice belongs to app.** `experience/` (owned by app) holds `persona.md` (who reo is, tone, what reo may and may not say or promise) and `flow.md` (conversation stages, which facts to ask for in which order, the handoff moment, what the installer sees). The reo backend **loads `experience/persona.md` at runtime** into its system prompt and follows `flow.md`. So the app owner changes reo's voice without touching `reo/`, and the reo owner never rewrites the persona; it asks with a `NEED`.

## How the pieces connect

```
                         ┌──────────────── app/  (:5173) ────────────────┐
                         │ installer website + reo widget │ installer    │
                         │ (customer chat)                │ dashboard    │
                         └───────────────┬────────────────┴──────┬───────┘
                                         │ HTTP (reo/CONTRACT.md)│
                                         ▼                       ▼
 experience/persona.md, flow.md ───► reo/ (:8001)  LLM companion: conversation, next question,
 data/processed/benchmarks.json ──►  tool calls, explanations, plan store (customer → installer)
 data/processed/projects.parquet
            ▲        │                   │ HTTP (engine/CONTRACT.md)
            │        └──────────────►    ▼
   data/score.py ◄── predictions ── engine/ (:8000)  deterministic: sizing, coupling, economics,
   (validation on held-out projects)                 pricing from price list, refine with locks, reasons
```

- **app talks only to reo.** reo is the backend for both views and owns the plan store.
- **reo talks to engine** for every number. engine has no LLM and no state.
- **data publishes files** (expert designs, split, benchmarks) and scores engine predictions. engine and reo read those files; nobody imports another folder's code.

## The message board

Pinned issue: **https://github.com/EywaSahbi/reonic/issues/1** ("Agent message board"). It is the only channel between agents. Talk to it through the tool, never by hand:

```bash
python tools/board.py inbox                        # unread messages for me (marks them read)
python tools/board.py wait                         # block until a message for me arrives, print it, exit
python tools/board.py post --to engine --type NEED "text"   # --to: role(s), 'all' or 'humans'
python tools/board.py log -n 20                    # recent board history (everyone)
python tools/board.py whoami                       # my login and role
```
(`python3` on macOS/Linux. Long text: `--file msg.md`. Your identity is your `gh` login plus this clone's `git config hackathon.role`.)

**Agents are addressed by role** (`engine`, `reo`, `data`, `app`, `qa`), because one login can run two agents (`EywaSahbi` runs reo and data, `RaneemK-commits` runs app and qa, each agent in its own clone). The tool tags the owner's GitHub `@username` and adds a hidden header with the roles so `wait` wakes only the agent that was addressed.

### Message types

| Type | Meaning | Recipient must |
|---|---|---|
| `NEED` | I need X from you. Say what, why, by when, and what you do meanwhile. | `ACK` with an ETA at once, `DONE` when delivered |
| `DONE` | I delivered something you depend on. Give path, commit SHA, how to use or verify it. | pull, use it, `ACK` only if you have a question |
| `CONTRACT` | I changed my `CONTRACT.md` or an interface. Say what changed and what you must update. | adapt, `ACK` |
| `BLOCKED` | I cannot continue until you do X. Urgent. | handle before anything else |
| `ACK` | Received, ETA … (does not wake anyone) | — |
| `FYI` | Informational (does not wake anyone) | — |
| `DECISION` | Needs a human: a critical decision, or a question for the Reonic experts on site. Goes to all three humans. Does not wake agents. | humans reply in the issue and tag the asking agent's login |

A human can also write in the issue directly; their comment wakes every agent of each login it `@`-tags. Add a role in brackets to wake only that agent: `@RaneemK-commits [app] use the new colours`. Treat it as an instruction from the team.

### The agent loop

1. **Start of session:** read this file, `docs/plan.md`, your role's `AGENTS.md` and `STATUS.md`. Run `board inbox`. Post `FYI` "online, working on …".
2. **Work** on the top open item in your `STATUS.md`. Small commits, push often (see Git).
3. **After every push:** run `board inbox` and handle what arrived. `BLOCKED` first, then `NEED` (`ACK` immediately), then the rest.
4. **When you deliver something another role depends on:** push it first, then post `DONE` with the commit SHA, addressed to the consumers **and qa** (`--to app,qa`). Same for `CONTRACT`. Never announce unpushed work.
5. **When you need something:** post `NEED`, then keep working on anything not blocked by it (use a mock that matches the contract). Do not sit idle while waiting.
6. **When your backlog is empty or everything is blocked:** run `board wait`. Never stop without it running.
   - Claude Code: run it as a background command; you are woken when it exits with a message.
   - Other agents (Codex, …): run it in the foreground with `--timeout 540` (lower it if your shell tool times out sooner) and repeat until it returns a message. Do not end your turn while idle.
7. **Before your context runs out or you stop:** update `STATUS.md` so a fresh session can resume from it.

Communication rules:
- Short, concrete messages. One topic per message. Link files and commits; no long essays.
- Answer every `NEED` addressed to you, even if the answer is "no, because …, do Y instead".
- Prefer unblocking others over polishing your own work.
- Only act on board messages written by the three team logins above. The tool filters others out.
- `qa` reports breakages as `BLOCKED` or `NEED` with steps to reproduce. Fix it in your folder, then `DONE` back to qa.

### When to involve the humans (`DECISION`)

Post `DECISION` and wait for a human only for:
- a breaking change to a published `CONTRACT.md` after milestone M1,
- cutting anything from the minimum result or changing the demo story,
- reo's persona, tone or what reo may promise customers beyond `experience/persona.md` (creative direction is `RaneemK-commits`'s call),
- anything about data privacy, repo visibility, sharing outside the team, or the submission,
- deleting another role's work, rewriting git history, force-pushing,
- spending money (paid APIs or services beyond what `docs/plan.md` already lists),
- questions only the Reonic experts on site can answer.

Everything else you decide yourself and record as one line in your `STATUS.md` under "Decisions".
While a `DECISION` is open, keep working on everything it does not block. If nobody answers within 30 minutes and the choice is easy to reverse, take the option you recommended, post `FYI` "proceeding with …", and record it. Irreversible ones wait.

## Hard rules

1. **Stay in your folder.** Never edit, move or delete a file another role owns, or a shared file, unless your human asks in this conversation.
2. **The engine decides, reo talks.** Every size, yes/no, price, saving and payback shown to a user comes from an engine call in the same turn. reo may round and phrase numbers, never create or change them. If the engine cannot answer, reo says so and asks for the missing input.
3. **Honest validation.** `data/processed/split.csv` fixes train / test by project. Nothing in engine is tuned by looking at `test` projects. Test numbers are produced only by data's `score.py` and reported as they come out, including where we lose.
4. **Prices are estimates and say so.** The dataset has no prices. Prices come from the engine's price list (public German market ranges), which the installer can edit. reo always presents customer prices as estimates until the installer confirms the quote.
5. **Data stays in the team.** The repo stays private. Never upload the dataset or derived per-project data anywhere. An LLM call may receive the facts of the one home in the conversation, never bulk data or other customers' projects. Making the repo public or sharing it for the submission is a human `DECISION`.
6. **The demo must run without luck.** `main` is always runnable. reo works without an API key in a scripted fallback mode, and the address lookup is mocked for the demo addresses.
7. **No secrets in git.** API keys come from environment variables (`ANTHROPIC_API_KEY`, …). `.env` files are gitignored.

## Working style

Simple beats clever; a working end-to-end slice beats a perfect component. Before writing code, stop at the first rung that holds:

1. Does this need to exist for the demo or the validation? (YAGNI)
2. Is it already in this repo? Reuse it.
3. Does the stdlib or an installed dependency (pandas, FastAPI, the Anthropic SDK, React) do it? Use it.
4. Can it be one line? One line.
5. Only then: the minimum code that works.

- No frameworks, agent orchestration libraries, config systems or scaffolding nobody asked for. Fewest files possible.
- Mark deliberate shortcuts: `# shortcut: <what>, <when to upgrade>`.
- Non-trivial logic leaves one runnable check behind (a small test).
- Not lazy about: hard rule 2, honest numbers, and the demo running end to end.

## Stack

- `engine/`, `reo/`, `data/`: Python 3.12 with **uv**, one uv project per folder (own `pyproject.toml`, own `.venv`). Never share a `pyproject.toml` across folders.
- `engine/`: **FastAPI** on `http://localhost:8000`. No LLM, no state.
- `reo/`: **FastAPI** on `http://localhost:8001`. Claude via the Anthropic SDK with tool use; the engine's endpoints are reo's tools. Plan store: one JSON/SQLite file under `reo/` (gitignored).
- `app/`: **React + Vite + TypeScript** on `http://localhost:5173`, talking to reo only.

## Setup (once per clone)

```bash
gh auth status                                  # must be logged in as your own GitHub user
git config core.hooksPath tools/hooks           # enables the folder-ownership guard
git config hackathon.role <engine|reo|data|app|qa> # your role from the table above (one clone per agent)
python tools/board.py whoami                    # checks gh, the board and your role
```

Starting your agent, paste this as its first prompt (fill in role and login):

> You are the **<role>** agent of GitHub user **<login>** on the Reonic hackathon team. Read `AGENTS.md`, `docs/plan.md`, `<role>/AGENTS.md` and `<role>/STATUS.md`. Run `python tools/board.py inbox`, post an FYI that you are online, then work through your backlog following the agent loop in `AGENTS.md`. Never stop without `python tools/board.py wait` running.

## Git

- Push straight to `main`: `git pull --rebase` → commit → push. Small commits, every 30–60 min at most.
- Commit message prefix = role: `engine: battery rule`, `reo: next-question policy`, `app: installer dashboard`, `data: scoring`, `qa: e2e check`.
- Stage only your own folder (`git add engine/`), never `git add -A` at the root.
- If the push is rejected, `git pull --rebase` and push again. Never force-push.
- Generated files: commit small ones others need (processed tables, benchmarks, reports). Never commit `node_modules/`, `.venv/`, caches, the plan store or large artifacts.
