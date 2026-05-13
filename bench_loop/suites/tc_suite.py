"""TC-15 tool-calling suite — 15 JSON-backed tasks across 5 tool backends."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bench_loop.config import TASKS_DIR
from bench_loop.models import BenchmarkTask, TaskResult
from bench_loop.suites.base import BenchmarkSuite

TASKS_DIR = TASKS_DIR / "tc"


# ---------------------------------------------------------------------------
# Tool backends (mock implementations for execution tracing)
# ---------------------------------------------------------------------------

def _calc(expr: str) -> float:
    """Evaluate a simple arithmetic expression safely."""
    # Normalize unicode operators → ASCII
    expr = expr.replace("×", "*").replace("÷", "/").replace("−", "-").replace("−", "-")
    # Strip only allowed tokens: digits, operators, whitespace, dots, parens
    cleaned = re.sub(r"[^0-9+\-*/(). ]", "", expr)
    if not cleaned.strip():
        raise ValueError("empty expression")
    return eval(cleaned, {"__builtins__": {}}, {})  # noqa: S307, SIM115


def _weather(location: str) -> dict[str, Any]:
    return {"location": location, "temp_f": 68.0, "conditions": "partly cloudy"}


def _stock_lookup(symbol: str) -> dict[str, Any]:
    prices = {"AAPL": 189.50, "MSFT": 425.22, "GOOGL": 175.80, "AMZN": 198.30}
    sym = symbol.upper()
    price = prices.get(sym, 150.00)
    return {"symbol": sym, "price": price, "change": round(price * 0.02 - 1.5, 2)}


def _string_tools(operation: str, text: str) -> str | int:
    if operation in ("reverse", "Reverse"):
        return text[::-1]
    if operation in ("uppercase", "upper"):
        return text.upper()
    if operation in ("char_count", "charcount", "length"):
        return len(text)
    raise ValueError(f"unknown operation: {operation}")


def _datetime(operation: str, **kwargs: Any) -> str | int:
    from datetime import date, datetime, timedelta

    datefmt = "%Y-%m-%d"

    def _parse(d: str) -> date:
        # Try ISO first, then month-name formats
        for fmt in (datefmt, "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(d.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"unrecognized date: {d}")

    if operation == "day_of_week":
        d = _parse(kwargs["date"])
        return d.strftime("%A")
    if operation == "date_diff":
        d1 = _parse(kwargs["date1"])
        d2 = _parse(kwargs["date2"])
        return abs((d2 - d1).days)
    raise ValueError(f"unknown datetime operation: {operation}")


TOOL_BACKENDS: dict[str, dict[str, Any]] = {
    "calculator": {"fn": _calc, "arg_key": "expression"},
    "weather": {"fn": _weather, "arg_key": "location"},
    "stock_lookup": {"fn": _stock_lookup, "arg_key": "symbol"},
    "string_tools": {"fn": _string_tools, "arg_key": "operation"},
    "datetime": {"fn": _datetime, "arg_key": "operation"},
}


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def _load_json_tasks() -> list[BenchmarkTask]:
    """Load all tc-NN.json files from tasks/tc/."""
    tasks: list[BenchmarkTask] = []
    pattern = re.compile(r"^tc-(\d+)\.json$")
    if not TASKS_DIR.is_dir():
        return tasks

    for path in sorted(TASKS_DIR.iterdir()):
        m = pattern.match(path.name)
        if not m:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        task_id = f"tc-{m.group(1).zfill(2)}"
        difficulty = data.get("difficulty", "medium")
        messages = [{"role": "user", "content": data["input"]}]
        tasks.append(
            BenchmarkTask(
                id=task_id,
                suite="tc_suite",
                messages=messages,
                title=f"Tool-call {task_id}: {data['expected_tool']}",
                difficulty=difficulty,
                validation={
                    "expected_tool": data["expected_tool"],
                    "expected_args": data["expected_args"],
                    "acceptable_alternatives": data.get("acceptable_alternatives", []),
                    "tool_backend": data.get("tool_backend", ""),
                },
                metadata={"input": data["input"]},
            )
        )
    return tasks


# ---------------------------------------------------------------------------
# Suite class
# ---------------------------------------------------------------------------

class TcSuite(BenchmarkSuite):
    """TC-15 tool-calling benchmark.

    Scores each task:
      1.0 — exact tool name + args match (100%)
      0.5 — correct tool but wrong args (50%)
      0.0 — wrong tool or no tool call (0%)

    Returns aggregated score out of 15 (expressed as percentage / 100 scale).
    """

    name = "tc_suite"
    task_file = None  # JSON-backed; load_tasks() is overridden

    async def load_tasks(self) -> list[BenchmarkTask]:
        return _load_json_tasks()

    # -- tool-call extraction (reuse patterns from toolcall.py / tool_use.py) --

    def _extract_tool_calls(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Return list of {name, args} dicts from the model response."""
        calls: list[dict[str, Any]] = []

        # 1) Structured tool_calls in response
        for call in (response.get("tool_calls") or []):
            if not isinstance(call, dict):
                continue
            fn = call.get("function") if isinstance(call.get("function"), dict) else call
            if isinstance(fn, dict):
                name = str(fn.get("name", ""))
                args = self._parse_args(fn.get("arguments", {}))
                if name:
                    calls.append({"name": name, "args": args})

        # 2) Nested inside raw_response.message.tool_calls
        raw = response.get("raw_response") or {}
        if isinstance(raw, dict):
            msg = raw.get("message") or {}
            if isinstance(msg, dict):
                for call in (msg.get("tool_calls") or []):
                    if not isinstance(call, dict):
                        continue
                    fn = call.get("function") if isinstance(call.get("function"), dict) else call
                    if isinstance(fn, dict):
                        name = str(fn.get("name", ""))
                        args = self._parse_args(fn.get("arguments", {}))
                        item = {"name": name, "args": args}
                        if name and item not in calls:
                            calls.append(item)

        return calls

    @staticmethod
    def _parse_args(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
            # Fallback: try to extract key=value pairs
            return dict(re.findall(r'(\w+)\s*=\s*["\']([^"\']*)["\']', value))
        return {}

    # -- matching logic --

    def _normalize(self, value: Any) -> str:
        return str(value).strip().lower()

    def _arg_match(self, expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        """Check whether actual args satisfy the expected args subset match."""
        for key, exp_val in expected.items():
            act_val = actual.get(key)
            if act_val is None:
                return False
            if isinstance(exp_val, (int, float)):
                try:
                    if float(act_val) != float(exp_val):
                        return False
                except Exception:
                    return False
            else:
                if self._normalize(exp_val) not in self._normalize(act_val):
                    return False
        return True

    def _accept_any(self, actual: dict[str, Any], alternatives: list[dict[str, Any]]) -> bool:
        """Check if actual call matches any acceptable_alternative."""
        for alt in alternatives:
            if self._arg_match(alt, actual):
                return True
        return False

    def evaluate(self, task: BenchmarkTask, response: dict[str, Any]) -> TaskResult:
        content = self.response_text(response).strip()
        actual_calls = self._extract_tool_calls(response)
        expected_tool = task.validation.get("expected_tool")
        expected_args = dict(task.validation.get("expected_args", {}))
        alternatives = task.validation.get("acceptable_alternatives", [])
        tool_backend = task.validation.get("tool_backend", "")

        # Execute tool if we have a call (for tracing/debugging)
        executed_result = None
        if actual_calls and tool_backend and tool_backend in TOOL_BACKENDS:
            tool_cfg = TOOL_BACKENDS[tool_backend]
            call = actual_calls[0]
            try:
                executed_result = tool_cfg["fn"](**call["args"])
            except Exception:
                executed_result = None

        # Score
        score: float = 0.0
        notes: list[str] = []

        if not actual_calls:
            # No tool call — check if model answered directly (partial credit)
            if content:
                score = 25.0
                notes.append("answered directly without tool call")
            else:
                notes.append("no tool call and no response content")
        else:
            first = actual_calls[0]
            tool_name = first["name"]

            if tool_name == expected_tool:
                # Correct tool — check args
                if self._arg_match(expected_args, first["args"]):
                    score = 100.0
                    notes.append("exact match")
                elif self._accept_any(first["args"], alternatives):
                    score = 100.0
                    notes.append("accepted alternative args")
                else:
                    score = 50.0
                    notes.append(f"correct tool, wrong args: expected {expected_args}, got {first['args']}")
            else:
                # Wrong tool
                if expected_tool:
                    notes.append(f"wrong tool: expected {expected_tool}, got {tool_name}")
                else:
                    notes.append(f"unexpected tool: {tool_name}")

        passed = score >= 85.0
        return self.build_result(
            task=task,
            passed=passed,
            score=round(score, 1),
            response=response,
            output=content,
            error="; ".join(notes),
            metadata={
                "actual_tool_calls": actual_calls,
                "expected_tool": expected_tool,
                "expected_args": expected_args,
                "tool_backend": tool_backend,
                "executed_result": str(executed_result) if executed_result else None,
                "evaluation_status": "pass" if passed else ("partial" if score >= 60 else "fail"),
            },
        )

    def aggregate_score(self, task_results: list[TaskResult]) -> float:
        """Return score out of 15 tasks (0–15 range)."""
        if not task_results:
            return 0.0
        # Each task is scored 0–100, so 100% = 1 task correct
        total = sum(r.score for r in task_results)
        max_score = len(task_results) * 100.0
        return round(total / max_score * 15, 2)
