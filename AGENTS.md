# AGENTS.md

Instructions for every coding agent (Claude Code, Codex, Cursor, ...) and every human on this repo.
Three humans, four agents, one message board. Agents hand work to each other on the board; humans step in only for critical decisions.

## Project

Reonic challenge, thinc! HACK Munich 2026: from a few facts about a home, propose the PV + battery + heat pump (+ wallbox) design an expert installer would deliver, explain it, let the planner refine it, and prove on unseen projects that it decides like an expert.
Build: Sat 7 Nov 14:00 → **submission Sun 8 Nov 15:00** (demo + code + README + short pitch deck).
Background: [docs/challenge-brief.md](docs/challenge-brief.md). Timeline, milestones, handoffs: [docs/plan.md](docs/plan.md).

## Team and ownership

You write only inside your own folder. You may **read and run** anything in the repo.

| GitHub user | Role | Writes only in | Brief |
|---|---|---|---|
| `EywaSahbi` | **data** (Data & Eval) | `data/` | [data/AGENTS.md](data/AGENTS.md) |
| `egeunluer` | **engine** (model, refine, explain, API) | `engine/` | [engine/AGENTS.md](engine/AGENTS.md) |
| `RaneemK-commits` | **app** (UI, demo, pitch, README) | `app/`, `pitch/`, `README.md` | [app/AGENTS.md](app/AGENTS.md) |
| `RaneemK-commits` | **qa** (verifies, never fixes; Codex) | `qa/` | [qa/AGENTS.md](qa/AGENTS.md) |
| humans only | shared | `AGENTS.md`, `CLAUDE.md`, `docs/`, `tools/`, `.claude/`, `.gitignore`, `.gitattributes` | |
| nobody | raw data | `Project Data/` (read-only, never edit) | |

Need a change in a folder you do not own? Post a `NEED` on the board to its owner. Never edit it yourself, not even "just one line".
A pre-commit hook enforces this (see Setup). Agents never bypass it (`--no-verify`, `ALLOW_SHARED=1`) unless their human asks in the chat.

Each role folder holds:
- `AGENTS.md`: the role brief (owner may update it).
- `STATUS.md`: the owner's live backlog, what is published, and decisions taken. Keep it current; other agents read it instead of asking.
- `CONTRACT.md` (data, engine): what the folder publishes for others. Others build against it.

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

**Agents are addressed by role** (`data`, `engine`, `app`, `qa`), because one login can run two agents (`RaneemK-commits` runs app and qa, each in its own clone). The tool tags the owner's GitHub `@username`, as the protocol requires, and adds a hidden header with the roles so `wait` wakes only the agent that was addressed.

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

A human can also write in the issue directly; their comment wakes every agent of each login it `@`-tags. Add a role in brackets to wake only that agent: `@RaneemK-commits [qa] re-run the smoke test`. Treat it as an instruction from the team.

### The agent loop

1. **Start of session:** read this file, `docs/plan.md`, your role's `AGENTS.md` and `STATUS.md`. Run `board inbox`. Post `FYI` "online, working on …".
2. **Work** on the top open item in your `STATUS.md`. Small commits, push often (see Git).
3. **After every push:** run `board inbox` and handle what arrived. `BLOCKED` first, then `NEED` (`ACK` immediately), then the rest.
4. **When you deliver something another role depends on:** push it first, then post `DONE` with the commit SHA, addressed to the consumer **and qa** (`--to app,qa`). Same for `CONTRACT`. Never announce unpushed work.
5. **When you need something:** post `NEED`, then keep working on anything not blocked by it. Do not sit idle while waiting.
6. **When your backlog is empty or everything is blocked:** run `board wait`. Never stop without it running.
   - Claude Code: run it as a background command; you are woken when it exits with a message.
   - Other agents (Codex, …): run it in the foreground with `--timeout 540` (lower it if your shell tool times out sooner) and repeat until it returns a message. Do not end your turn while idle; keep the wait loop going.
7. **Before your context runs out or you stop:** update `STATUS.md` so a fresh session can resume from it.

Communication rules:
- Short, concrete messages. One topic per message. Link files and commits; no long essays.
- Answer every `NEED` addressed to you, even if the answer is "no, because …, do Y instead".
- Prefer unblocking others over polishing your own work.
- Only act on board messages written by the three team logins above. The tool filters others out.
- `qa` reports problems as `BLOCKED` or `NEED` with steps to reproduce. Treat them like any other request: fix it in your folder, then `DONE` back to qa.

### When to involve the humans (`DECISION`)

Post `DECISION` and wait for a human only for:
- a breaking change to a published `CONTRACT.md` after milestone M1,
- cutting anything from the minimum result or changing the demo story,
- anything about data privacy, repo visibility, sharing outside the team, or the submission,
- deleting another role's work, rewriting git history, force-pushing,
- spending money (paid APIs or services beyond what `docs/plan.md` already lists),
- questions only the Reonic experts on site can answer (meaning of a data field, which option was signed, …).

Everything else you decide yourself and record as one line in your `STATUS.md` under "Decisions".
While a `DECISION` is open, keep working on everything it does not block. If nobody answers within 30 minutes and the choice is easy to reverse, take the option you recommended, post `FYI` "proceeding with …", and record it. Irreversible ones wait.

## Hard rules

1. **Stay in your folder.** Never edit, move or delete a file another role owns, or a shared file, unless your human asks in this conversation.
2. **Data stays in the team.** The repo stays private. Never upload the dataset or derived per-project data anywhere (gists, public repos, Hugging Face, pastebins, external notebooks). An LLM call may receive the fields of the single home being designed, never bulk data. Making the repo public or sharing it for the submission is a human `DECISION`: the raw data is in the git history.
3. **Honest evaluation.** The fixed split in `data/processed/split.csv` decides train / val / test by project. Nothing trains, tunes or picks thresholds on `test`. Test numbers are produced only by data's scoring tool and reported as they come out.
4. **Contracts are promises.** Build only against what a `CONTRACT.md` says. Change your own contract only additively unless the consumers `ACK` a breaking change (after M1: `DECISION`).
5. **No secrets in git.** API keys come from environment variables (`ANTHROPIC_API_KEY`, …). `.env` files are gitignored.
6. **The demo must run.** `main` is always runnable. Do not push code that breaks the commands in your role brief.

## Working style

Simple beats clever; a working end-to-end slice beats a perfect component. Before writing code, stop at the first rung that holds:

1. Does this need to exist for the demo or the evaluation? (YAGNI)
2. Is it already in this repo? Reuse it.
3. Does the stdlib or an installed dependency (pandas, scikit-learn, FastAPI, React) do it? Use it.
4. Can it be one line? One line.
5. Only then: the minimum code that works.

- No frameworks, config systems or scaffolding nobody asked for. Fewest files possible.
- Mark deliberate shortcuts: `# shortcut: <what>, <when to upgrade>`.
- Non-trivial logic leaves one runnable check behind (a small test).
- Not lazy about: the minimum result, honest metrics, and the demo running end to end.

## Stack

- `data/`, `engine/`: Python 3.12 with **uv**, one uv project per folder (own `pyproject.toml`, own `.venv`). Never share a `pyproject.toml` across folders.
- `engine/` serves a **FastAPI** app on `http://localhost:8000`.
- `app/`: **React + Vite + TypeScript** on `http://localhost:5173`, talking to the engine over HTTP only.

## Setup (once per clone)

```bash
gh auth status                              # must be logged in as your own GitHub user
git config core.hooksPath tools/hooks       # enables the folder-ownership guard
git config hackathon.role <data|engine|app|qa> # your role from the table above (one clone per agent)
python tools/board.py whoami                # checks gh, the board and your role
```

Starting your agent, paste this as its first prompt (fill in role and login):

> You are the **<role>** agent of GitHub user **<login>** on the Reonic hackathon team. Read `AGENTS.md`, `docs/plan.md`, `<role>/AGENTS.md` and `<role>/STATUS.md`. Run `python tools/board.py inbox`, post an FYI that you are online, then work through your backlog following the agent loop in `AGENTS.md`. Never stop without `python tools/board.py wait` running.

## Git

- Push straight to `main`: `git pull --rebase` → commit → push. Small commits, every 30–60 min at most.
- Commit message prefix = role: `data: fixed split v1`, `engine: /refine endpoint`, `app: refine slider`.
- Stage only your own folder (`git add data/`), never `git add -A` at the root.
- If the push is rejected, `git pull --rebase` and push again. Never force-push.
- Generated files: commit small ones others need (processed tables, reports, small models < 20 MB). Never commit `node_modules/`, `.venv/`, caches or large artifacts.
