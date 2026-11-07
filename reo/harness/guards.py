"""Guardrails in code (not in the prompt). Each check returns violations; the runner logs it as a guard step."""
import json
import re

_NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(?![\w])")


def numbers_in(text: str) -> list[float]:
    """Numbers as a reader sees them: 18,400 / 18.400 -> 18400; 8,5 / 8.5 -> 8.5."""
    out = []
    for m in _NUM.findall(text or ""):
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", m):
            out.append(float(re.sub(r"[.,]", "", m)))
        else:
            out.append(float(m.replace(",", ".")))
    return out


def collect(obj) -> list[float]:
    """Every number inside a tool result (dicts, lists, numbers and numbers inside strings)."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, str):
        return numbers_in(obj)
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in collect(v)]
    if isinstance(obj, (list, tuple)):
        return [n for v in obj for n in collect(v)]
    return collect(json.loads(json.dumps(obj, default=str)))


def _grounded(n: float, known: list[float]) -> bool:
    if n <= 12 and n == int(n):
        return True  # small counts ("3 variants", "2 options") are words, not engine numbers
    for t in known:
        tol = 50 if abs(t) >= 1000 else 5 if abs(t) >= 100 else 0.5  # persona rounding: €100, €10, 0.5 kWp / whole units
        if abs(n - t) <= tol or abs(n - t * 100) <= 0.5 or abs(n * 100 - t) <= 0.5:  # 0.35 €/kWh said as 35 ct
            return True
    return False


def grounding(texts: list[str], known: list[float]) -> list[str]:
    """Hard rule 2: every number in output text must appear (rounded) in a tool result of the same run."""
    bad = []
    for text in texts:
        for n in numbers_in(text):
            if not _grounded(n, known):
                bad.append(f"{n:g} in \"{text[:60]}\"")
    return bad


def effect_gate(tool_name: str, allowed: list[str], registry: dict) -> str | None:
    """A skill may call only its own tools, and never an execute tool."""
    tool = registry.get(tool_name)
    if tool is None or tool_name not in allowed:
        return f"{tool_name} is not allowed in this skill"
    if tool.effect == "execute":
        return f"{tool_name} is an execute tool; only the planner's approval runs it"
    return None
