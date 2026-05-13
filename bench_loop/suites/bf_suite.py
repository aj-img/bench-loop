"""BF-15 Bug-Finding Suite.

Presents a buggy Python function to the model, asks it to find and fix the bug,
then compares the model's fix against the expected correction.

Scoring (per task):
  - 1.0 : model's fix exactly matches the expected correction
  - 0.5 : model correctly identified the bug but the fix is imperfect
  - 0.0 : model missed the bug entirely or produced wrong code
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any

from bench_loop.config import TASKS_DIR
from bench_loop.models import BenchmarkTask, TaskResult
from bench_loop.suites.base import BenchmarkSuite


# Mapping from task ID to the corresponding Python file name
TASK_FILE_MAP = {
    "BF-001": "BF-001_off_by_one.py",
    "BF-002": "BF-002_logic_inversion.py",
    "BF-003": "BF-003_missing_edge_case.py",
    "BF-004": "BF-004_type_confusion.py",
    "BF-005": "BF-005_index_oob.py",
    "BF-006": "BF-006_wrong_operator.py",
    "BF-007": "BF-007_missing_return.py",
    "BF-008": "BF-008_float_precision.py",
    "BF-009": "BF-009_infinite_loop.py",
    "BF-010": "BF-010_wrong_sort_order.py",
    "BF-011": "BF-011_regex_boundary.py",
    "BF-012": "BF-012_uninitialized_variable.py",
    "BF-013": "BF-013_wrong_default.py",
    "BF-014": "BF-014_encoding.py",
    "BF-015": "BF-015_race_condition.py",
}


class BFSuite(BenchmarkSuite):
    name = "bf"
    task_file = Path(TASKS_DIR) / "bf" / "tasks.yaml"

    def _extract_function_code(self, task: BenchmarkTask) -> str:
        """Extract the buggy function code from the task's YAML prompt."""
        content = self.response_text(task.messages[0] if task.messages else {})
        # Extract code from a fenced code block in the prompt
        match = re.search(r"```python\s*(.*?)```", content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return content

    def _extract_expected_correction(self, task_id: str) -> str | None:
        """Extract the CORRECTED section from the reference Python file."""
        filename = TASK_FILE_MAP.get(task_id)
        if not filename:
            return None
        filepath = Path(TASKS_DIR) / "bf" / filename
        if not filepath.exists():
            return None
        text = filepath.read_text(encoding="utf-8")
        # Find the # CORRECTED: comment and extract what follows
        corrected_match = re.search(r"# CORRECTED:\s*\n(.*?)(?=\n\n|\Z)", text, re.DOTALL)
        if corrected_match:
            return corrected_match.group(1).strip()
        return None

    def _extract_model_fix(self, response_text: str) -> str:
        """Extract the model's proposed fix from its response."""
        # Try Python code blocks first
        match = re.search(r"```python\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Try generic code blocks
        match = re.search(r"```\s*(.*?)```", response_text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # If no code block, try to extract a function definition
        func_match = re.search(r"(def\s+\w+.*?(?:\n|$))", response_text, re.DOTALL)
        if func_match:
            return func_match.group(1).strip()
        # Last resort: return the trimmed response
        return response_text.strip()

    def _compute_similarity(self, fix_a: str, fix_b: str) -> float:
        """Compute similarity ratio between two fix strings."""
        # Normalize: strip whitespace, collapse runs of whitespace
        norm_a = re.sub(r"\s+", " ", fix_a.strip())
        norm_b = re.sub(r"\s+", " ", fix_b.strip())
        if norm_a == norm_b:
            return 1.0
        # Use difflib ratio for partial matching
        return difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

    def _detect_bug_in_response(self, response_text: str) -> bool:
        """Heuristic: check if the model's response explicitly identifies the bug."""
        lower = response_text.lower()
        bug_keywords = [
            "bug", "missing", "wrong", "incorrect", "error", "inverted",
            "off by one", "should be", "needs", "fix", "change",
            "comparison", "return", "loop", "range", "type",
            "empty", "bound", "index", "sort", "regex", "encode",
            "lock", "race", "atomic", "mutable", "default",
            "precision", "round", "float",
        ]
        return any(kw in lower for kw in bug_keywords)

    def evaluate(self, task: BenchmarkTask, response: dict[str, Any]) -> TaskResult:
        """Evaluate the model's bug-fix attempt.

        Returns:
            1.0 — exact match with expected correction
            0.5 — correct bug identification but imperfect fix
            0.0 — missed the bug entirely
        """
        response_text = self.response_text(response)
        task_id = task.id
        expected = self._extract_expected_correction(task_id)
        model_fix = self._extract_model_fix(response_text)

        # Case 1: No expected correction file found
        if expected is None:
            has_buggy_code = "BUG" in (self._extract_function_code(task) or "")
            return self.build_result(
                task=task,
                passed=has_buggy_code and self._detect_bug_in_response(response_text),
                score=0.0,
                response=response,
                output=model_fix[:500],
                error="Expected correction file not found",
                metadata={"evaluation_status": "missing_correction_file"},
            )

        # Case 2: Model provided no fix at all
        if not model_fix:
            return self.build_result(
                task=task,
                passed=False,
                score=0.0,
                response=response,
                output=response_text[:500],
                error="No code or fix found in model response",
                metadata={"evaluation_status": "no_fix_provided"},
            )

        # Case 3: Exact or near-exact match with expected correction
        similarity = self._compute_similarity(model_fix, expected)
        if similarity >= 0.95:
            return self.build_result(
                task=task,
                passed=True,
                score=1.0,
                response=response,
                output=model_fix[:500],
                error="",
                metadata={
                    "evaluation_status": "exact_match",
                    "similarity": round(similarity, 4),
                },
            )

        # Case 4: Correct bug identification (model mentions the bug type)
        # but the fix is imperfect
        if self._detect_bug_in_response(response_text):
            partial_score = round(similarity, 4) if similarity > 0.3 else 0.5
            return self.build_result(
                task=task,
                passed=similarity > 0.3,
                score=partial_score,
                response=response,
                output=model_fix[:500],
                error=f"Fix identified but imperfect (similarity={similarity:.2f})",
                metadata={
                    "evaluation_status": "partial_fix",
                    "similarity": round(similarity, 4),
                    "expected": expected[:200],
                    "provided": model_fix[:200],
                },
            )

        # Case 5: Model missed the bug entirely
        return self.build_result(
            task=task,
            passed=False,
            score=0.0,
            response=response,
            output=model_fix[:500],
            error="Model failed to identify or fix the bug",
            metadata={
                "evaluation_status": "missed_bug",
                "expected": expected[:200],
                "provided": model_fix[:200],
            },
        )
