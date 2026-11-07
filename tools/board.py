#!/usr/bin/env python3
"""Agent message board: the pinned GitHub issue the team's agents talk through.

Agents are addressed by ROLE. One GitHub login may run several agents (e.g. reo + data, app + qa),
each in its own clone with its own `git config hackathon.role`.

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
ROLES = {  # role -> GitHub login of the human who runs that agent
    "engine": "egeunluer",
    "reo": "EywaSahbi",
    "data": "EywaSahbi",
    "app": "RaneemK-commits",
    "qa": "RaneemK-commits",
}
LOGINS = list(dict.fromkeys(ROLES.values()))
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


def canon_login(name: str) -> str | None:
    return {lg.lower(): lg for lg in LOGINS}.get(name.lstrip("@").lower())


def roles_of(login: str) -> list[str]:
    return [r for r, lg in ROLES.items() if lg.lower() == login.lower()]


def me() -> tuple[str, str]:
    """(login, role) of this clone's agent."""
    raw = gh("api", "user", "--jq", ".login").strip()
    login = canon_login(raw)
    if not login:
        sys.exit(f"board: gh is logged in as {raw}, who is not on the team {LOGINS}.")
    role = subprocess.run(["git", "config", "hackathon.role"], capture_output=True, text=True).stdout.strip()
    mine = roles_of(login)
    if not role and len(mine) == 1:
        role = mine[0]
    if role not in mine:
        sys.exit(f"board: `git config hackathon.role` is '{role or 'unset'}', but {login} runs {mine}. "
                 f"Run: git config hackathon.role <{'|'.join(mine)}>")
    return login, role


def resolve(to: str, my_role: str) -> list[str]:
    """--to value -> list of roles."""
    out: list[str] = []
    for part in (p.strip() for p in to.split(",") if p.strip()):
        key = part.lstrip("@").lower()
        if key == "all":
            out += [r for r in ROLES if r != my_role]
        elif key == "humans":
            out += list(ROLES)
        elif key in ROLES:
            out.append(key)
        elif canon_login(key):
            out += [r for r in roles_of(canon_login(key)) if r != my_role]
        else:
            sys.exit(f"board: unknown recipient '{part}'. Use a role {list(ROLES)}, a login, 'all' or 'humans'.")
    return list(dict.fromkeys(out))


def fetch(since: str | None = None) -> list[dict]:
    path = f"repos/{REPO}/issues/{BOARD_ISSUE}/comments?per_page=100"
    if since:
        path += f"&since={since}"
    jq = ".[] | {id, created_at, url: .html_url, author: .user.login, body}"
    out = gh("api", path, "--paginate", "--jq", jq)
    return sorted((json.loads(line) for line in out.splitlines() if line.strip()), key=lambda c: c["id"])


def to_roles(values: list[str]) -> list[str]:
    """Marker values are roles (v2) or logins (v1, before roles existed)."""
    out: list[str] = []
    for v in values:
        out += [v] if v in ROLES else roles_of(canon_login(v) or v)
    return list(dict.fromkeys(out))


def parse(c: dict) -> dict:
    """Turn a raw comment into a message: sender role, recipient roles, type, text."""
    body = c["body"] or ""
    m = MARKER.search(body)
    if m:
        meta = dict(kv.split("=", 1) for kv in m.group(1).split() if "=" in kv)
        frm = meta.get("from", "")
        sender = frm if frm in ROLES else (roles_of(frm) or ["?"])[0]
        to = to_roles([t for t in meta.get("to", "").split(",") if t])
        typ = meta.get("type", "FYI").upper()
        text = body[m.end():].strip()
        text = text.split("\n", 1)[1].strip() if text.startswith("**`") and "\n" in text else text
        return {**c, "from_role": sender, "to": to, "type": typ, "text": text, "agent": True}
    # A human wrote in the issue directly: route by @mentions; `[qa]`-style tags narrow to roles.
    tagged = [lg for lg in LOGINS if re.search(rf"@{re.escape(lg)}\b", body, re.I)]
    to = [r for lg in tagged for r in roles_of(lg)]
    narrowed = [r for r in to if re.search(rf"\[{r}\]", body, re.I)]
    return {**c, "from_role": None, "to": narrowed or to, "type": "HUMAN", "text": body.strip(), "agent": False}


def for_me(msg: dict, role: str) -> bool:
    if not canon_login(msg["author"]):
        return False  # only the team can address agents
    if msg["agent"] and msg["from_role"] == role:
        return False  # my own posts
    return role in msg["to"]


def show(msg: dict) -> str:
    who = f"{msg['from_role']} agent ({msg['author']})" if msg["agent"] else f"human {msg['author']}"
    to = ", ".join(msg["to"]) or "-"
    when = msg["created_at"].replace("T", " ")[:16]
    return f"--- {msg['type']} from {who} to {to} · {when} UTC · {msg['url']}\n{msg['text']}\n"


def load_cursor(role: str) -> dict:
    try:
        return json.loads((CURSOR_DIR / f"{role}.json").read_text())
    except (OSError, ValueError):
        return {"last_id": 0, "since": None}


def save_cursor(role: str, comments: list[dict], cur: dict) -> None:
    if not comments:
        return
    last = max(comments, key=lambda c: c["id"])
    if last["id"] <= cur["last_id"]:
        return
    CURSOR_DIR.mkdir(exist_ok=True)
    (CURSOR_DIR / f"{role}.json").write_text(json.dumps({"last_id": last["id"], "since": last["created_at"]}))


def unread(role: str) -> tuple[list[dict], list[dict], dict]:
    cur = load_cursor(role)
    new = [c for c in fetch(cur["since"]) if c["id"] > cur["last_id"]]
    return new, [m for m in map(parse, new) if for_me(m, role)], cur


def cmd_whoami(_: argparse.Namespace) -> None:
    login, role = me()
    issue = json.loads(gh("api", f"repos/{REPO}/issues/{BOARD_ISSUE}", "--jq", "{title, state, url: .html_url}"))
    print(f"login: {login}\nrole:  {role}\nboard: #{BOARD_ISSUE} {issue['title']} ({issue['state']}) {issue['url']}")
    hooks = subprocess.run(["git", "config", "core.hooksPath"], capture_output=True, text=True).stdout.strip()
    if hooks != "tools/hooks":
        print("warning: ownership hook not enabled. Run: git config core.hooksPath tools/hooks")


def cmd_post(a: argparse.Namespace) -> None:
    login, role = me()
    typ = a.type.upper()
    text = Path(a.file).read_text(encoding="utf-8") if a.file else " ".join(a.text)
    if text.strip() == "-":
        text = sys.stdin.read()
    if not text.strip():
        sys.exit("board: empty message.")
    to = list(ROLES) if typ == "DECISION" else (resolve(a.to, role) if a.to else [])
    if not to and typ not in {"FYI", "ACK"}:
        sys.exit("board: --to is required for this type.")
    if typ == "DECISION":
        mentions, targets = " ".join(f"@{lg}" for lg in LOGINS), "humans"
    else:
        mentions = " ".join(dict.fromkeys(f"@{ROLES[r]}" for r in to))
        targets = ", ".join(to) or "everyone"
    header = f"**`{typ}`** · {role} → {targets}" + (f" · {mentions}" if mentions else "")
    if typ == "DECISION":
        header += f" · _needs a human: reply here, tag_ `{login}` _and write_ `[{role}]`"
    marker = f"<!-- board v2 from={role} to={','.join(to)} type={typ} -->"
    body = f"{marker}\n{header}\n\n{text.strip()}\n"
    res = json.loads(gh("api", "--method", "POST", f"repos/{REPO}/issues/{BOARD_ISSUE}/comments",
                        "--input", "-", stdin=json.dumps({"body": body})))
    print(f"posted {typ} from {role} to {', '.join(to) or 'board'}: {res['html_url']}")


def cmd_inbox(a: argparse.Namespace) -> None:
    _, role = me()
    new, msgs, cur = unread(role)
    print("\n".join(map(show, msgs)) if msgs else "inbox: no new messages.")
    if not a.peek:
        save_cursor(role, new, cur)


def cmd_wait(a: argparse.Namespace) -> None:
    login, role = me()
    start = time.time()
    print(f"waiting for messages to {role} ({login}) on #{BOARD_ISSUE}, every {a.interval}s ...", flush=True)
    while True:
        new, msgs, cur = unread(role)
        if any(m["type"] not in QUIET for m in msgs):
            print("\n".join(map(show, msgs)), flush=True)
            save_cursor(role, new, cur)
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
