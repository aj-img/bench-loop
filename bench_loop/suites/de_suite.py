"""DE-15 data extraction suite — 15 standalone JSON task files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bench_loop.config import TASKS_DIR
from bench_loop.models import BenchmarkTask, TaskResult
from bench_loop.suites.base import BenchmarkSuite

DE_TASKS_DIR = Path(__file__).resolve().parent.parent.parent / "tasks" / "de"

CATEGORY_WEIGHTS = {"A": 15, "B": 20, "C": 25, "D": 25, "E": 15}


class DE15Suite(BenchmarkSuite):
    """Declarative, JSON-backed data-extraction suite with per-task schema validation."""

    name = "de15"
    _task_files: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------ low-level helpers
    def _task_file_path(self, task_id: str) -> Path:
        return DE_TASKS_DIR / f"{task_id}.json"

    def _load_task_files(self) -> list[dict[str, Any]]:
        if self._task_files is not None:
            return self._task_files
        files = sorted(DE_TASKS_DIR.glob("DE-*.json"))
        if not files:
            raise FileNotFoundError(f"No DE-*.json files found in {DE_TASKS_DIR}")
        self._task_files = []
        for fp in files:
            with open(fp, "r", encoding="utf-8") as f:
                self._task_files.append(json.load(f))
        return self._task_files

    # ------------------------------------------------------------------ task loading
    async def load_tasks(self) -> list[BenchmarkTask]:
        tasks: list[BenchmarkTask] = []
        for raw in self._load_task_files():
            task_id: str = raw["id"]
            input_text: str = raw["input"]
            ground_truth = raw.get("ground_truth")
            schema = raw.get("schema", {})

            # Build a system prompt that describes the extraction rules.
            system_text = (
                "You are a data extraction assistant. Your job is to extract structured "
                "information from unstructured text. You will receive:\n"
                "1. The raw source text\n"
                "2. A JSON schema describing the expected output structure\n"
                "3. The ground-truth extraction (for evaluation only; use it as reference)\n\n"
                "Rules:\n"
                "- Extract ONLY information explicitly stated in the source text.\n"
                "- For string fields, copy the exact value from the source text.\n"
                "- Do NOT paraphrase, summarize, translate, expand abbreviations, "
                "correct typos, or rewrite values.\n"
                "- If a field's value cannot be determined from the source text, "
                "use null.\n"
                "- Do NOT infer, guess, or use background knowledge.\n"
                "- Output valid JSON matching the provided schema.\n"
                "- Output ONLY the JSON object or array. No explanations, no markdown fences.\n"
                "- Preserve original capitalization, punctuation, and wording."
            )
            user_text = (
                "Extract data from the following text according to the schema.\n\n"
                "--- SOURCE TEXT ---\n"
                f"{input_text}\n\n"
                "--- SCHEMA ---\n"
                f"{json.dumps(schema, indent=2)}\n\n"
                "--- INSTRUCTIONS ---\n"
                "Output ONLY the JSON. No explanation."
            )

            messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_text},
            ]

            validation = {
                "expected": ground_truth,
                "scenario_id": task_id.upper(),
                "category": raw.get("category", ""),
                "title": raw.get("title", ""),
                "difficulty": raw.get("difficulty", ""),
            }

            tasks.append(
                BenchmarkTask(
                    id=task_id,
                    suite=self.name,
                    messages=messages,
                    title=str(raw.get("title", "")),
                    difficulty=str(raw.get("difficulty", "")),
                    capability_tags=["data-extraction", "structured-output"],
                    config={"max_tokens": 2048, "temperature": 0.0},
                    validation=validation,
                )
            )
        return tasks

    # ------------------------------------------------------------------ comparison helpers
    def _normalize_string(self, value: str) -> str:
        return value.strip()

    def _compare_scalar(self, expected: Any, actual: Any) -> tuple[bool, str | None]:
        if expected is None:
            return actual is None, None if actual is None else "expected null"
        if isinstance(expected, str):
            if not isinstance(actual, str):
                return False, "expected string"
            return self._normalize_string(actual) == self._normalize_string(expected), None
        if isinstance(expected, bool):
            return actual is expected, None if isinstance(actual, bool) else "expected boolean"
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return False, "expected number"
            return abs(float(actual) - float(expected)) <= 0.01, None
        return False, "unsupported scalar"

    def _compare_scalar_array(self, expected: list[Any], actual: Any) -> tuple[int, int, list[str]]:
        if not isinstance(actual, list):
            return 0, 1, ["expected array"]
        if len(expected) != len(actual):
            return 0, 1, [f"expected {len(expected)} items but received {len(actual)}"]
        remaining = list(actual)
        for exp_item in expected:
            match_idx = -1
            for i, cand in enumerate(remaining):
                ok, _ = self._compare_scalar(exp_item, cand)
                if ok:
                    match_idx = i
                    break
            if match_idx == -1:
                return 0, 1, ["array values did not match expected set"]
            remaining.pop(match_idx)
        return 1, 1, []

    def _compare_dict(self, expected: dict[str, Any], actual: Any) -> tuple[int, int, list[str]]:
        if not isinstance(actual, dict):
            return 0, len(expected) or 1, ["expected object"]
        correct = 0
        total = 0
        notes: list[str] = []
        for key, exp_val in expected.items():
            act_val = actual.get(key)
            sub_c, sub_t, sub_n = self._compare_value(exp_val, act_val, key)
            correct += sub_c
            total += sub_t
            notes.extend(sub_n)
        return correct, total, notes

    def _compare_array(self, expected: list[Any], actual: Any, path: str) -> tuple[int, int, list[str]]:
        if not isinstance(actual, list):
            return 0, len(expected) or 1, ["expected array"]
        if len(expected) != len(actual):
            return 0, len(expected), [f"array length mismatch: expected {len(expected)}, got {len(actual)}"]
        correct = 0
        total = 0
        notes: list[str] = []
        for i, (exp_item, act_item) in enumerate(zip(expected, actual)):
            if isinstance(exp_item, dict) and isinstance(act_item, dict):
                # Compare as nested dicts with index-based anchoring
                sub_c, sub_t, sub_n = self._compare_dict(exp_item, act_item)
            elif isinstance(exp_item, list) and isinstance(act_item, list):
                sub_c, sub_t, sub_n = self._compare_array(exp_item, act_item, f"{path}[{i}]")
            else:
                sub_c, sub_t, sub_n = self._compare_value(exp_item, act_item, f"{path}[{i}]")
            correct += sub_c
            total += sub_t
            notes.extend(sub_n)
        return correct, total, notes

    def _compare_value(self, expected: Any, actual: Any, path: str = "") -> tuple[int, int, list[str]]:
        if isinstance(expected, list):
            if expected and isinstance(expected[0], dict):
                return self._compare_array(expected, actual, path or "$root")
            return self._compare_scalar_array(expected, actual)
        if isinstance(expected, dict):
            return self._compare_dict(expected, actual)
        ok, _ = self._compare_scalar(expected, actual)
        return (1 if ok else 0), 1, ([] if ok else [f"{path or '$root'}: scalar mismatch"])

    def _evaluate_compliance(self, expected: Any, actual: Any) -> tuple[bool, bool, bool, list[str]]:
        notes: list[str] = []
        exact_shape = type(expected) == type(actual) or (
            isinstance(expected, (int, float)) and isinstance(actual, (int, float))
        ) or (isinstance(expected, list) and isinstance(actual, list))
        if not exact_shape:
            notes.append(f"top-level shape mismatch: expected {type(expected).__name__}, got {type(actual).__name__}")
        requested_fields_only = True
        no_missing = True
        if isinstance(expected, dict) and isinstance(actual, dict):
            extra = sorted(set(actual.keys()) - set(expected.keys()))
            missing = sorted(set(expected.keys()) - set(actual.keys()))
            if extra:
                requested_fields_only = False
                notes.append(f"extra fields: {', '.join(extra)}")
            if missing:
                no_missing = False
                notes.append(f"missing fields: {', '.join(missing)}")
        return exact_shape, requested_fields_only, no_missing, notes

    # ------------------------------------------------------------------ scoring
    def _score_field(self, expected: Any, actual: Any, field_name: str) -> tuple[float, str | None]:
        """Score a single field. Exact match = 1.0, fuzzy (string) = 0.5-0.9, type mismatch = 0."""
        if isinstance(expected, dict):
            # Nested object — score each sub-field
            if not isinstance(actual, dict):
                return 0.0, f"expected object for {field_name}"
            sub_fields = len(expected) or 1
            sub_correct = 0.0
            sub_total = 0.0
            sub_notes: list[str] = []
            for k, ev in expected.items():
                av = actual.get(k)
                s, n = self._score_field(ev, av, f"{field_name}.{k}")
                sub_correct += s
                sub_total += s if s > 0 else 1.0
                sub_notes.append(n or "")
            avg = sub_correct / sub_total if sub_total > 0 else 0.0
            return avg, " | ".join(sub_notes) if sub_notes else None
        if isinstance(expected, list):
            # Array of objects or scalars
            if not isinstance(actual, list):
                return 0.0, f"expected array for {field_name}"
            if expected and isinstance(expected[0], dict):
                # Array of objects — match by content
                score_per_item = 0.0
                count = 0
                for exp_item in expected:
                    if exp_item not in actual:
                        continue
                    idx = actual.index(exp_item)
                    s, _ = self._score_field(exp_item, actual[idx], f"{field_name}[{count}]")
                    score_per_item += s
                    count += 1
                avg = score_per_item / len(expected) if expected else 0.0
                return avg, None
            # Scalar array — use compare_scalar_array
            if not isinstance(actual, list) or len(expected) != len(actual):
                return 0.0, f"array mismatch for {field_name}"
            matches = sum(1 for e, a in zip(expected, actual) if e == a)
            return matches / len(expected) if expected else 0.0, None

        # Scalar
        if expected is None:
            return 1.0 if actual is None else 0.0, None
        if isinstance(expected, bool):
            return 1.0 if actual is expected else 0.0, None
        if isinstance(expected, (int, float)):
            if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                return 0.0, f"type mismatch for {field_name}: expected number, got {type(actual).__name__}"
            if abs(float(actual) - float(expected)) <= 0.01:
                return 1.0, None
            return 0.5, f"numeric mismatch for {field_name}: expected {expected}, got {actual}"
        if isinstance(expected, str):
            if not isinstance(actual, str):
                return 0.0, f"type mismatch for {field_name}: expected string, got {type(actual).__name__}"
            if actual.strip() == expected.strip():
                return 1.0, None
            # Fuzzy string match — check similarity
            if expected.lower() in actual.lower() or actual.lower() in expected.lower():
                return 0.7, f"partial match for {field_name}"
            # Word-overlap score
            exp_words = set(expected.lower().split())
            act_words = set(actual.lower().split())
            if exp_words and act_words:
                overlap = len(exp_words & act_words) / max(len(exp_words), len(act_words))
                return 0.5 + 0.3 * overlap, f"partial string match for {field_name}"
            return 0.0, f"no match for {field_name}: expected '{expected}', got '{actual}'"
        return 0.0, f"unsupported type for {field_name}"

    def _extract_all_field_scores(
        self, expected: Any, actual: Any, path: str = ""
    ) -> tuple[int, int, list[str]]:
        """Count correct (1.0) and total atomic fields with notes."""
        notes: list[str] = []
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                return 0, len(expected), [f"expected object at {path or '$root'}"]
            for k, ev in expected.items():
                sub_c, sub_t, sub_n = self._extract_all_field_scores(ev, actual.get(k), f"{path}.{k}" if path else k)
                notes.extend(sub_n)
                # Count atomic leaves only
                leaves = self._count_leaves(ev)
                total_leaves_actual = self._count_leaves(actual.get(k))
                if sub_c == sub_t == 0 and sub_n:
                    notes.append(f"{path}.{k}: {sub_n[0]}")
                # We count each atomic scalar as 1 field
                note_fields = sum(1 for n in sub_n if n)
                correct = sum(
                    1 for k2, v2 in expected.items()
                    if self._is_atomic(expected) and self._is_atomic(actual.get(k2)) and expected[k2] == actual.get(k2)
                )
        elif isinstance(expected, list):
            if not isinstance(actual, list):
                return 0, len(expected), [f"expected array at {path or '$root'}"]
            return len(expected), len(expected), []
        else:
            ok, _ = self._compare_scalar(expected, actual)
            return (1 if ok else 0), 1, ([] if ok else [f"{path or '$root'}: mismatch"])
        # Simplify: just compare with _compare_value for consistency
        return self._compare_value(expected, actual, "", path or "")

    def _count_leaves(self, obj: Any) -> int:
        """Count atomic leaf values in a nested structure."""
        if isinstance(obj, dict):
            return sum(self._count_leaves(v) for v in obj.values())
        if isinstance(obj, list):
            return sum(self._count_leaves(v) for v in obj)
        return 1

    def _is_atomic(self, val: Any) -> bool:
        return not isinstance(val, (dict, list))

    # ------------------------------------------------------------------ evaluation
    def evaluate(self, task: BenchmarkTask, response: dict[str, Any]) -> TaskResult:
        response_text = self.response_text(response)
        expected = task.validation.get("expected")
        scenario_id = str(task.validation.get("scenario_id") or task.id.upper())

        # 1. JSON parse
        try:
            parsed = json.loads(response_text)
        except Exception as exc:
            return self.build_result(
                task=task,
                passed=False,
                score=0.0,
                response=response,
                output=response_text,
                error=f"Invalid JSON: {exc}",
                metadata={
                    "scenario_id": scenario_id,
                    "evaluation_status": "invalid_json",
                    "summary": f"Invalid JSON: {exc}",
                    "note": "Official score is 0 when the response is not valid JSON.",
                    "category": task.validation.get("category"),
                    "title": task.validation.get("title"),
                },
            )

        # 2. Schema compliance
        exact_shape, fields_only, no_missing, comp_notes = self._evaluate_compliance(expected, parsed)

        # 3. Atomic field comparison
        correct, total, notes = self._compare_value(expected, parsed, "")
        score_pct = 0 if total == 0 else round(correct / total * 100)

        # 4. Field-level scoring for detailed metadata
        field_scores: list[tuple[str, float]] = []
        self._collect_field_scores(expected, parsed, "", field_scores)
        avg_field_score = (
            sum(s for _, s in field_scores) / len(field_scores) * 100 if field_scores else 0.0
        )
        # Blend: use atomic comparison as primary, field-level as secondary signal
        final_score = max(score_pct, round(avg_field_score))
        final_score = min(final_score, 100)

        passed = final_score >= 85
        summary = (
            f"{correct}/{total} atomic fields correct ({score_pct}%). "
            f"{'shape ok' if exact_shape else 'shape fail'}, "
            f"{'fields only' if fields_only else 'extra fields'}, "
            f"{'no missing' if no_missing else 'missing fields'}. "
            f"Field-level avg: {round(avg_field_score, 1)}%."
        )
        note = " | ".join(comp_notes + notes) if (comp_notes or notes) else ""

        return self.build_result(
            task=task,
            passed=passed,
            score=float(final_score),
            response=response,
            output=response_text,
            error="" if passed else note,
            metadata={
                "scenario_id": scenario_id,
                "evaluation_status": self._status_for_score(final_score),
                "summary": summary,
                "note": note,
                "category": task.validation.get("category"),
                "title": task.validation.get("title"),
                "field_scores": [{"field": k, "score": round(v * 100, 1)} for k, v in field_scores],
            },
        )

    def _collect_field_scores(
        self, expected: Any, actual: Any, path: str, out: list[tuple[str, float]]
    ) -> None:
        if isinstance(expected, dict):
            if isinstance(actual, dict):
                for k in expected:
                    self._collect_field_scores(expected[k], actual.get(k), f"{path}.{k}" if path else k, out)
            else:
                out.append((path or "$root", 0.0))
        elif isinstance(expected, list):
            if isinstance(actual, list):
                if expected and isinstance(expected[0], dict):
                    for exp_item in expected:
                        match = next((a for a in actual if all(a.get(k) == v for k, v in exp_item.items() if v is not None)), None)
                        if match:
                            self._collect_field_scores(exp_item, match, f"{path}[]", out)
                        else:
                            out.append((f"{path}[]", 0.0))
                else:
                    for i, exp_item in enumerate(expected):
                        act_item = actual[i] if i < len(actual) else None
                        out.append((f"{path}[{i}]", 1.0 if exp_item == act_item else 0.0))
            else:
                out.append((path or "$root", 0.0))
        else:
            score, _ = self._score_field(expected, actual, path)
            out.append((path or "$root", score))

    def _status_for_score(self, score: int) -> str:
        if score >= 85:
            return "pass"
        if score >= 60:
            return "partial"
        return "fail"

    # ------------------------------------------------------------------ aggregation
    def aggregate_score(self, task_results: list[TaskResult]) -> float:
        """Weighted average across categories, returning a score /15 scale."""
        grouped: dict[str, list[float]] = {key: [] for key in CATEGORY_WEIGHTS}
        for result in task_results:
            category = str(result.metadata.get("category") or "")
            if category in grouped:
                grouped[category].append(result.score)
        weighted = 0.0
        for category, weight in CATEGORY_WEIGHTS.items():
            avg = sum(grouped[category]) / len(grouped[category]) if grouped[category] else 0.0
            weighted += avg * (weight / 100.0)
        # Convert 0-100 scale to 0-15 scale
        return round(weighted * 15 / 100, 2)