"""Harness adapter tests.

These prove that each harness:
  - rewrites the outgoing request in its own way (prepare)
  - parses the model's response back into normalized tool_calls (postprocess)

If these tests start failing, the leaderboard's harness comparisons are
meaningless and the public claim ("Same model, four prompting contracts") is a
lie. Treat any regression here as launch-blocking.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from bench_loop.harness import get_harness, list_harnesses


def make_task() -> SimpleNamespace:
    return SimpleNamespace(
        messages=[{"role": "user", "content": "What is the weather in Paris?"}],
        config={
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                            "required": ["location"],
                        },
                    },
                }
            ]
        },
    )


def test_registry_contains_all_four_harnesses():
    names = list_harnesses()
    assert set(names) >= {"raw", "hermes", "qwen", "pi"}


def test_raw_passthrough():
    h = get_harness("raw")
    task = make_task()
    prepared = h.prepare(task, provider_name="ollama")
    assert prepared["messages"] == task.messages
    assert "tools" in prepared
    assert prepared["tools"][0]["function"]["name"] == "get_weather"


@pytest.mark.parametrize("name", ["hermes", "qwen", "pi"])
def test_tagged_harness_injects_system_prompt(name: str):
    h = get_harness(name)
    task = make_task()
    prepared = h.prepare(task, provider_name="ollama")

    # System prompt is prepended.
    assert prepared["messages"][0]["role"] == "system"
    sys_content = prepared["messages"][0]["content"]
    assert "get_weather" in sys_content

    # Tools param is stripped — the schema is now inline in the system prompt.
    assert "tools" not in prepared


def test_hermes_postprocess_parses_tool_call_tags():
    h = get_harness("hermes")
    response = {
        "content": (
            "Let me check.\n"
            '<tool_call>\n{"name": "get_weather", "arguments": {"location": "Paris"}}\n</tool_call>'
        ),
        "tool_calls": [],
    }
    parsed = h.postprocess(dict(response), make_task())
    calls = parsed.get("tool_calls", [])
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "get_weather"
    args = json.loads(calls[0]["function"]["arguments"])
    assert args == {"location": "Paris"}
    # Tagged blob is stripped from content.
    assert "<tool_call>" not in parsed["content"]


def test_qwen_postprocess_parses_function_call_tags():
    h = get_harness("qwen")
    response = {
        "content": (
            "Let me check.\n"
            '<function_call>\n{"name": "get_weather", "arguments": {"location": "Paris"}}\n</function_call>'
        ),
        "tool_calls": [],
    }
    parsed = h.postprocess(dict(response), make_task())
    calls = parsed.get("tool_calls", [])
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "get_weather"


def test_pi_postprocess_strips_think_and_parses_tool_call():
    h = get_harness("pi")
    response = {
        "content": (
            "<think>I should call the weather tool.</think>\n"
            '<tool_call>\n{"name": "get_weather", "arguments": {"location": "Paris"}}\n</tool_call>'
        ),
        "tool_calls": [],
    }
    parsed = h.postprocess(dict(response), make_task())
    assert "<think>" not in parsed["content"]
    md = parsed.get("metadata", {})
    assert md.get("reasoning_blocks") == 1
    calls = parsed.get("tool_calls", [])
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "get_weather"


def test_postprocess_preserves_existing_tool_calls():
    """A model that natively emits tool_calls should keep them."""
    h = get_harness("hermes")
    response = {
        "content": "no tagged calls",
        "tool_calls": [
            {"type": "function", "function": {"name": "native_call", "arguments": "{}"}}
        ],
    }
    parsed = h.postprocess(dict(response), make_task())
    assert any(c["function"]["name"] == "native_call" for c in parsed["tool_calls"])


def test_malformed_tool_call_is_ignored_not_crashed():
    """Garbage inside the tags must not raise."""
    h = get_harness("hermes")
    response = {
        "content": "<tool_call>this is not json</tool_call>",
        "tool_calls": [],
    }
    parsed = h.postprocess(dict(response), make_task())
    assert parsed.get("tool_calls") == []
