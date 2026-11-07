@AGENTS.md

## Claude Code specifics

- Run `python tools/board.py wait` with `run_in_background: true`. You are re-invoked when it exits with a message; handle it, then start a new background `wait` before ending your turn.
- Before ending any turn, check that a background `board wait` is running (or that your human told you to stop).
- Your role brief is `<role>/AGENTS.md`; read it at session start, it is not loaded automatically.
