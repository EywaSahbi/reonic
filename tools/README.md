# tools/ — team tooling

> Back to the [project README](../README.md). Changes here are human decisions.

| Path | What it does |
|---|---|
| [board.py](board.py) | the team's message board: five agents and three humans talk through one pinned GitHub issue (`post`, `inbox`, `wait`, `log`) |
| [hooks/pre-commit](hooks/pre-commit) | folder-ownership guard: each role may only commit inside its own folder |

Enable once per clone:

```bash
git config core.hooksPath tools/hooks
git config hackathon.role <engine|reo|customer|data|app|qa>
```

The rules are in [AGENTS.md](../AGENTS.md).
