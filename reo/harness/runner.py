"""One loop for every skill: model call -> tool calls (through the effect gate) -> results -> repeat until the skill
calls `finish` or the budget runs out. Every step is recorded in a Run; guards run in code and are logged as steps.
Without an API key (or on any LLM failure) the skill's scripted planner calls the same tools in a fixed order.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import anthropic

import llm
import demo_guard
from harness import guards
from harness.tools import REGISTRY, Ctx

log = logging.getLogger("reo.harness")
RUNS: dict[str, dict] = {}  # live and recent runs (api persists finished runs with the plan store)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _summ(obj, n: int = 160) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def _design_summary(r: dict) -> str | None:
    c = r.get("components")
    if not c:
        return None
    parts = [f"{k} {v['size']:g} {v['unit']}" for k, v in c.items() if v["recommended"] and v["size"]]
    return f"{', '.join(parts) or 'no components'}; €{r['total_eur']:,.0f}; autarky {r['economics']['autarky_pct']:.0f}%"


class Runner:
    def __init__(self, skill, ctx: Ctx, trigger: str, lease=None):
        self.skill, self.ctx = skill, ctx
        self.known: list[float] = guards.collect(ctx.facts)
        self.t0 = time.time()
        self.run = {"id": uuid.uuid4().hex[:10], "skill": skill.name, "plan_id": ctx.plan["id"], "trigger": trigger,
                    "status": "running", "steps": [], "output": None, "model": "scripted", "started_at": _now(), "duration_s": None}
        self._lease = lease or demo_guard.reserve_run()
        RUNS[self.run["id"]] = self.run

    # ---------- recording ----------
    def step(self, kind: str, tool: str | None, args: str, result: str, ms: int = 0, effect: str | None = None, ok: bool | None = None):
        s = {"n": len(self.run["steps"]) + 1, "kind": kind, "args_summary": args, "result_summary": result, "ms": ms}
        if tool:
            s["tool"] = tool
        if effect:
            s["effect"] = effect
        if ok is not None:
            s["ok"] = ok
        self.run["steps"].append(s)

    def call(self, name: str, args: dict) -> dict:
        """Every tool call, from the model or the scripted planner, goes through here."""
        blocked = guards.effect_gate(name, self.skill.tools, REGISTRY)
        if blocked:
            self.step("guard", "effect_gate", name, blocked, ok=False)
            return {"error": blocked}
        tool = REGISTRY[name]
        t = time.time()
        try:
            result = tool.handler(self.ctx, args or {})
        except (KeyError, TypeError, ValueError) as e:
            result = {"error": f"bad arguments: {e}"}
        self.known += guards.collect(result)
        self.step("tool", name, _summ(args or {}, 100), _design_summary(result) or _summ(result), int((time.time() - t) * 1000),
                  effect=tool.effect)
        return result

    def over_budget(self) -> bool:
        return time.time() - self.t0 > self.skill.max_seconds

    # ---------- guards on the output ----------
    def check(self) -> list[str]:
        bad = guards.grounding(self.skill.texts(self.ctx), self.known)
        self.step("guard", "grounding", f"{len(self.skill.texts(self.ctx))} texts", "ok" if not bad else "; ".join(bad[:3]), ok=not bad)
        missing = self.skill.missing(self.ctx)
        if missing:
            self.step("guard", "completeness", "output", missing, ok=False)
        return bad + ([missing] if missing else [])

    # ---------- modes ----------
    def run_llm(self) -> bool:
        c = llm.client()
        if c is None:
            return False
        self.run["model"] = self.skill.model()
        tools = [{"name": n.replace(".", "_"), "description": REGISTRY[n].description, "input_schema": REGISTRY[n].schema}
                 for n in self.skill.tools]
        by_api_name = {n.replace(".", "_"): n for n in self.skill.tools}
        messages = [{"role": "user", "content": self.skill.context(self.ctx)}]
        retried = False
        for _ in range(self.skill.max_steps):
            if self.over_budget():
                self.step("guard", "budget", f"{self.skill.max_seconds}s", "time budget used up", ok=False)
                return False
            t = time.time()
            try:
                r = c.beta.messages.create(model=self.run["model"], max_tokens=16000, system=self.skill.prompt(), tools=tools,
                                           messages=messages, output_config={"effort": self.skill.effort},
                                           **llm.fallback_kwargs(self.run["model"]))
            except anthropic.APIError as e:
                self.step("think", "llm", self.run["model"], f"LLM error {type(e).__name__}", int((time.time() - t) * 1000), ok=False)
                return False
            text = " ".join(b.text for b in r.content if b.type == "text").strip()
            self.step("think", "llm", self.run["model"], _summ(text or f"{sum(b.type == 'tool_use' for b in r.content)} tool call(s)"),
                      int((time.time() - t) * 1000))
            if r.stop_reason in ("refusal", "max_tokens"):
                return False
            messages.append({"role": "assistant", "content": r.content})
            results, finished = [], False
            for b in r.content:
                if b.type != "tool_use":
                    continue
                out = self.call(by_api_name.get(b.name, b.name), b.input if isinstance(b.input, dict) else {})
                if b.name == "finish" and self.ctx.finish:
                    bad = self.check()
                    if not bad:
                        finished = True
                    elif not retried:
                        retried, self.ctx.finish = True, None
                        out = {"error": "not accepted, fix and call finish again: " + "; ".join(bad[:5])}
                    else:
                        return False
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out, ensure_ascii=False, default=str)})
            if finished:
                return True
            if not results:
                self.step("guard", "budget", "no tool call", "model stopped without finish", ok=False)
                return False
            messages.append({"role": "user", "content": results})
        self.step("guard", "budget", f"{self.skill.max_steps} steps", "step budget used up", ok=False)
        return False

    def run_scripted(self) -> None:
        self.run["model"] = "scripted"
        self.ctx.reset()
        self.skill.scripted(self.ctx, self.call)
        self.check()

    def go(self) -> dict:
        try:
            return self._go()
        finally:
            self._lease.release()

    def _go(self) -> dict:
        try:
            if not (self.skill.loop and self.run_llm()):
                if self.run["model"] != "scripted":
                    self.step("guard", "fallback", self.run["model"], "switching to the scripted planner", ok=False)
                self.run_scripted()
            if self.skill.label:
                self.run["model"] = self.skill.label(self.ctx)
            self.run["output"] = self.skill.output(self.ctx, self.run)
            self.run["status"] = "needs_approval" if any(a["status"] == "proposed" for a in self.ctx.actions) else "done"
        except Exception as e:  # a run must always end with a status the UI can show
            log.exception("run failed")
            self.step("guard", "error", type(e).__name__, str(e)[:160], ok=False)
            self.run["status"] = "failed"
        self.run["duration_s"] = round(time.time() - self.t0, 1)
        return self.run
