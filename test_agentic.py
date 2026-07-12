"""Offline test for OpenRouterClient.chat_completion_agentic (the Notion tool loop).
Run in the RAG venv from the project dir:
    venv/bin/python test_agentic.py
"""
import asyncio
import sys

from app.services.openrouter_client import OpenRouterClient

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _client():
    # Bypass __init__ (no network / keys needed for loop logic)
    c = OpenRouterClient.__new__(OpenRouterClient)
    c.default_model = "test-model"
    c.total_input_tokens = 0
    c.total_output_tokens = 0
    return c


def _tool_call(name, args_json, cid="call_1"):
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": args_json}}


async def test_single_tool_then_answer():
    c = _client()
    calls = []

    async def fake_executor(name, args):
        calls.append((name, args))
        return "search result: teal"

    seq = [
        {"message": {"content": "", "tool_calls": [_tool_call("API-post-search", '{"query":"teal"}')]},
         "finish_reason": "tool_calls", "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        {"message": {"content": "Bird's favorite color is teal.", "tool_calls": None},
         "finish_reason": "stop", "usage": {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28}},
    ]
    idx = {"i": 0}

    async def fake_raw(messages, tools, model, temperature, max_tokens, top_p):
        r = seq[idx["i"]]; idx["i"] += 1
        return r

    c._agentic_raw_call = fake_raw
    resp = await c.chat_completion_agentic(
        messages=[{"role": "user", "content": "what's bird's favorite color?"}],
        tools=[{"type": "function", "function": {"name": "API-post-search"}}],
        tool_executor=fake_executor,
    )
    check("executor called once with the search tool",
          calls == [("API-post-search", {"query": "teal"})], calls)
    check("final answer returned to caller",
          resp.choices[0].message.content == "Bird's favorite color is teal.",
          resp.choices[0].message.content)
    check("usage carried from final turn", resp.usage.total_tokens == 28, resp.usage.total_tokens)


async def test_no_tool_needed():
    c = _client()
    calls = []

    async def fake_executor(name, args):
        calls.append(name); return "x"

    async def fake_raw(messages, tools, model, temperature, max_tokens, top_p):
        return {"message": {"content": "just chatting", "tool_calls": None},
                "finish_reason": "stop", "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}

    c._agentic_raw_call = fake_raw
    resp = await c.chat_completion_agentic(messages=[{"role": "user", "content": "hi"}],
                                           tools=[{"type": "function", "function": {"name": "x"}}],
                                           tool_executor=fake_executor)
    check("no tool executed when model doesn't ask", calls == [], calls)
    check("plain answer passes through", resp.choices[0].message.content == "just chatting")


async def test_max_iters_forces_final():
    c = _client()
    n = {"i": 0}

    async def fake_executor(name, args):
        return "loop result"

    async def fake_raw(messages, tools, model, temperature, max_tokens, top_p):
        # Always ask for a tool while tools are offered; when forced (tools=None) answer.
        if tools:
            n["i"] += 1
            return {"message": {"content": "", "tool_calls": [_tool_call("API-post-search", "{}", f"c{n['i']}")]},
                    "finish_reason": "tool_calls", "usage": {"total_tokens": 1}}
        return {"message": {"content": "forced final", "tool_calls": None},
                "finish_reason": "stop", "usage": {"total_tokens": 2}}

    c._agentic_raw_call = fake_raw
    resp = await c.chat_completion_agentic(messages=[{"role": "user", "content": "go"}],
                                           tools=[{"type": "function", "function": {"name": "API-post-search"}}],
                                           tool_executor=fake_executor, max_iters=3)
    check("looped exactly max_iters times before forcing", n["i"] == 3, n["i"])
    check("forced tool-free final answer returned", resp.choices[0].message.content == "forced final")


async def main():
    await test_single_tool_then_answer()
    await test_no_tool_needed()
    await test_max_iters_forces_final()
    print(f"\nRESULTS: {len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    asyncio.run(main())
