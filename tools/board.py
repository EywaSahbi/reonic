#!/usr/bin/env python3
"""Agent message board: the pinned GitHub issue the team's agents talk through.

Usage (see AGENTS.md):
  python tools/board.py whoami
  python tools/board.py post --to engine --type NEED "text"     (--file msg.md for long text)
  python tools/board.py inbox [--peek]
  python tools/board.py wait [--interval 30] [--timeout 540]
  python tools/board.py log [-n 20]

Needs only the Python stdlib and an authenticated `gh` CLI.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = "EywaSahbi/reonic"
BOARD_ISSUE = 1
TEAM = {"EywaSahbi": "data", "egeunluer": "engine", "RaneemK-commits": "app"}
TYPES = ["NEED", "DONE", "CONTRACT", "BLOCKED", "ACK", "FYI", "DECISION"]
QUIET = {"ACK", "FYI", "DECISION"}  # never wake an agent's `wait`
CURSOR_DIR = Path(__file__).resolve().parent.parent / ".board"
MARKER = re.compile(r"<!--\s*board\s+(.*?)\s*-->", re.S)


def gh(*args: str, stdin: str | None = None) -> str:
    try:
        r = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        sys.exit("board: the GitHub CLI `gh` is not installed (https://cli.github.com).")
    if r.returncode != 0:
        sys.exit(f"board: gh {' '.join(args[:2])} failed: {r.stderr.strip()}")
    return r.stdout


def me() -> str:
    login = gh("api", "user", "--jq", ".login").strip()
    canon = {k.lower(): k for k in TEAM}.get(login.lower())
    if not canon:
        sys.exit(f"board: gh is logged in as {login}, who is not on the team {list(TEAM)}.")
    return canon


def resolve(to: str, sender: str) -> list[str]:
    by_role = {role: login for login, role in TEAM.items()}
    by_login = {login.lower(): login for login in TEAM}
    out: list[str] = []
    for part in (p.strip() for p in to.split(",") if p.strip()):
        key = part.lstrip("@").lower()
        if key == "all":
            out += [lg for lg in TEAM if lg != sender]
        elif key == "humans":
            out += list(TEAM)
        elif key in by_role:
            out.append(by_role[key])
        elif key in by_login:
            out.append(by_login[key])
        else:
            sys.exit(f"board: unknown recipient '{part}'. Use a role {list(by_role)}, a login, 'all' or 'humans'.")
    return list(dict.fromkeys(out))


def fetch(since: str | None = None) -> list[dict]:
    path = f"repos/{REPO}/issues/{BOARD_ISSUE}/comments?per_page=100"
    if since:
        path += f"&since={since}"
    jq = ".[] | {id, created_at, url: .html_url, author: .user.login, body}"
    out = gh("api", path, "--paginate", "--jq", jq)
    return sorted((json.loads(line) for line in out.splitlines() if line.strip()), key=lambda c: c["id"])


def parse(c: dict) -> dict:
    """Turn a raw comment into a message: sender, recipients, type, text."""
    body = c["body"] or ""
    m = MARKER.search(body)
    if m:
        meta = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv)
        to = [t for t in meta.get("to", "").split(",") if t]
        typ = meta.get("type", "FYI").upper()
        text = body[m.end():].strip()
        text = text.split("\n", 1)[1].strip() if text.startswith("**`") and "\n" in text else text
        agent = True
    else:  # a human wrote in the issue directly: route by @mentions
        to = [lg for lg in TEAM if re.search(rf"@{re.escape(lg)}\b", body, re.I)]
        typ, text, agent = "HUMAN", body.strip(), False
    return {**c, "to": to, "type": typ, "text": text, "agent": agent}


def for_me(msg: dict, login: str) -> bool:
    if msg["author"].lower() not in {k.lower() for k in TEAM}:
        return False  # only the team can address agents
    if msg["agent"] and msg["author"].lower() == login.lower():
        return False  # my own agent's posts
    return login.lower() in {t.lower() for t in msg["to"]}


def show(msg: dict) -> str:
    sender = msg["author"]
    who = f"{TEAM.get(sender, '?')} agent ({sender})" if msg["agent"] else f"human {sender}"
    to = ", ".join(msg["to"]) or "-"
    when = msg["created_at"].replace("T", " ")[:16]
    return f"--- {msg['type']} from {who} to {to} · {when} UTC · {msg['url']}\n{msg['text']}\n"


def load_cursor(login: str) -> dict:
    f = CURSOR_DIR / f"{login}.json"
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return {"last_id": 0, "since": None}


def save_cursor(login: str, comments: list[dict], cur: dict) -> None:
    if not comments:
        return
    last = max(comments, key=lambda c: c["id"])
    if last["id"] <= cur["last_id"]:
        return
    CURSOR_DIR.mkdir(exist_ok=True)
    (CURSOR_DIR / f"{login}.json").write_text(json.dumps({"last_id": last["id"], "since": last["created_at"]}))


def unread(login: str) -> tuple[list[dict], list[dict], dict]:
    cur = load_cursor(login)
    new = [c for c in fetch(cur["since"]) if c["id"] > cur["last_id"]]
    msgs = [m for m in map(parse, new) if for_me(m, login)]
    return new, msgs, cur


def cmd_whoami(_: argparse.Namespace) -> None:
    login = me()
    issue = json.loads(gh("api", f"repos/{REPO}/issues/{BOARD_ISSUE}", "--jq", "{title, state, url: .html_url}"))
    role = subprocess.run(["git", "config", "hackathon.role"], capture_output=True, text=True).stdout.strip()
    print(f"login: {login}\nrole:  {TEAM[login]}\nboard: #{BOARD_ISSUE} {issue['title']} ({issue['state']}) {issue['url']}")
    if role != TEAM[login]:
        print(f"warning: `git config hackathon.role` is '{role or 'unset'}', expected '{TEAM[login]}'. "
              f"Run: git config hackathon.role {TEAM[login]}")
    hooks = subprocess.run(["git", "config", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
    if hooks != "tools/hooks":
        print("warning: ownership hook not enabled. Run: git config core.hooksPath tools/hooks")


def cmd_post(a: argparse.Namespace) -> None:
    login = me()
    typ = a.type.upper()
    text = Path(a.file).read_text(encoding="utf-8") if a.file else " ".join(a.text)
    if text.strip() == "-":
        text = sys.stdin.read()
    if not text.strip():
        sys.exit("board: empty message.")
    if typ == "DECISION":
        to = list(TEAM)  # decisions always go to all three humans
    else:
        to = resolve(a.to, login) if a.to else []
    if not to and typ not in {"FYI", "ACK"}:
        sys.exit("board: --to is required for this type.")
    mentions = " ".join(f"@{t}" for t in to)
    targets = "humans" if typ == "DECISION" else (", ".join(TEAM[t] for t in to) or "everyone")
    header = f"**`{typ}`** · {TEAM[login]} → {targets}" + (f" · {mentions}" if mentions else "")
    if typ == "DECISION":
        header += " · _needs a human: reply here and tag_ `" + login + "`"
    marker = f"<!-- board from={login} to={','.join(to)} type={typ} -->"
    body = f"{marker}\n{header}\n\n{text.strip()}\n"
    res = json.loads(gh("api", "--method", "POST", f"repos/{REPO}/issues/{BOARD_ISSUE}/comments",
                        "--input", "-", stdin=json.dumps({"body": body})))
    print(f"posted {typ} to {', '.join(to) or 'board'}: {res['html_url']}")


def cmd_inbox(a: argparse.Namespace) -> None:
    login = me()
    new, msgs, cur = unread(login)
    print("\n".join(map(show, msgs)) if msgs else "inbox: no new messages.")
    if not a.peek:
        save_cursor(login, new, cur)


def cmd_wait(a: argparse.Namespace) -> None:
    login = me()
    start = time.time()
    print(f"waiting for messages to {login} ({TEAM[login]}) on #{BOARD_ISSUE}, every {a.interval}s ...", flush=True)
    while True:
        new, msgs, cur = unread(login)
        loud = [m for m in msgs if m["type"] not in QUIET]
        if loud:
            print("\n".join(map(show, msgs)), flush=True)
            save_cursor(login, new, cur)
            return
        if a.timeout and time.time() - start >= a.timeout:
            print("wait: timed out, no new messages. Run it again.")
            sys.exit(2)
        time.sleep(a.interval)


def cmd_log(a: argparse.Namespace) -> None:
    msgs = [parse(c) for c in fetch()][-a.n:]
    print("\n".join(map(show, msgs)) if msgs else "board is empty.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Agent message board (pinned issue).")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("whoami", help="show login, role and board").set_defaults(fn=cmd_whoami)
    s = sub.add_parser("post", help="post a message")
    s.add_argument("--to", help="role(s), login(s), 'all' or 'humans', comma-separated")
    s.add_argument("--type", required=True, type=str.upper, choices=TYPES)
    s.add_argument("--file", help="read the message text from a file")
    s.add_argument("text", nargs="*", help="message text, or '-' for stdin")
    s.set_defaults(fn=cmd_post)
    s = sub.add_parser("inbox", help="print unread messages for me and mark them read")
    s.add_argument("--peek", action="store_true", help="do not mark as read")
    s.set_defaults(fn=cmd_inbox)
    s = sub.add_parser("wait", help="block until a message for me arrives")
    s.add_argument("--interval", type=int, default=30, help="seconds between polls (default 30)")
    s.add_argument("--timeout", type=int, default=0, help="give up after N seconds, exit code 2 (default: never)")
    s.set_defaults(fn=cmd_wait)
    s = sub.add_parser("log", help="recent board history")
    s.add_argument("-n", type=int, default=20)
    s.set_defaults(fn=cmd_log)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
