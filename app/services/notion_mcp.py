"""Lightweight MCP Streamable-HTTP client for the local Notion MCP server.

Deliberately avoids the heavyweight `mcp` SDK, whose transitive starlette
dependency conflicts with this app's pinned fastapi/starlette. Speaks
JSON-RPC 2.0 over the MCP Streamable HTTP transport using httpx (already a
dependency).

For the chat agentic loop it exposes:
  - get_openai_tools(): allowlisted Notion tools in OpenAI function format
  - call_tool(name, arguments): run one Notion tool, return text result
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


def _load_env_fallback() -> None:
    """Populate os.environ from the project .env if the app didn't already.

    The RAG reads config via pydantic, which does NOT push values into
    os.environ, so this module loads what it needs itself (also makes the
    module runnable standalone for testing)."""
    if os.getenv("NOTION_MCP_URL") and os.getenv("NOTION_MCP_AUTH_TOKEN"):
        return
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env_fallback()


def _url() -> str:
    return os.getenv("NOTION_MCP_URL", "http://127.0.0.1:3001/mcp")


def _auth() -> str:
    return os.getenv("NOTION_MCP_AUTH_TOKEN", "")


# Safety allowlist: which of the Notion MCP's 24 tools characters may use.
# Conservative start: search, read a page (markdown), create a page.
TOOL_ALLOWLIST = {
    "API-post-search",
    "API-retrieve-page-markdown",
    "API-post-page",
}

# Notion's native create-page schema is ~3.6k chars and dominates the tool-token
# cost. We expose this tiny schema to the model instead, and expand the simple
# {title, content} into Notion's full create-page payload in call_tool(). The
# real MCP tool (API-post-page) is unchanged.
_SLIM_CREATE_PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short title for the new Notion page"},
        "content": {"type": "string", "description": "Optional plain-text body for the page"},
    },
    "required": ["title"],
}
_SLIM_CREATE_PAGE_DESC = (
    "Create a new page in the user's Notion. Provide a short title and optional "
    "plain-text body; it is filed in the user's Character Knowledge database."
)


def _build_create_page_payload(args: dict) -> dict:
    """Expand {title, content} into Notion's full create-page request, parented
    under the configured default database (NOTION_DEFAULT_PARENT_ID)."""
    title = args.get("title", "")
    content = args.get("content", "")
    parent_id = os.getenv("NOTION_DEFAULT_PARENT_ID", "")
    # Write the note into the Name (title) + Content columns, matching how
    # existing rows store data so search surfaces created notes too.
    properties: dict = {"Name": {"title": [{"text": {"content": title}}]}}
    if content:
        properties["Content"] = {"rich_text": [{"text": {"content": content}}]}
    payload: dict = {"properties": properties}
    if parent_id:
        payload["parent"] = {"data_source_id": parent_id}
    return payload

_PROTOCOL_VERSION = "2025-03-26"
_tools_cache: Optional[list[dict]] = None

# --- Lazy / layered tool loading (cost) -----------------------------------
# The full Notion tool schemas (~4.6k tokens) used to be attached to EVERY
# character reply, yet Notion is actually invoked ~1% of the time. Instead we
# attach only this tiny "gateway" tool by default; the model calls it to unlock
# the real search/read/create tools, so their heavy schema is sent only on the
# rare turns Notion is genuinely needed. The agentic loop performs the swap via
# its `expand_tools` mapping (see openrouter_client.chat_completion_agentic).
GATEWAY_TOOL_NAME = "open_notion"
_GATEWAY_TOOL = {
    "type": "function",
    "function": {
        "name": GATEWAY_TOOL_NAME,
        "description": (
            "Unlock the user's PRIVATE Notion tools (search / read / create their own "
            "personal notes). Call this ONLY when the user explicitly asks about their "
            "own Notion notes, or asks you to save / write something down to Notion. Do "
            "NOT call it for general knowledge, facts, web lookups, TV shows, people, or "
            "current events — those are already answered for you without any tools."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_gateway_tool() -> list[dict]:
    """The single lightweight tool offered by default. When the model calls it,
    the agentic loop swaps in the full tool set from get_openai_tools()."""
    return [_GATEWAY_TOOL]

# Explicit, unambiguous descriptions for the allowlisted read tools so the model
# does NOT grab the Notion "search" tool for general/web lookups. These operate
# ONLY on the user's private Notion workspace, never the web.
_TOOL_DESC_OVERRIDES = {
    "API-post-search": (
        "Search ONLY the user's private Notion workspace (their personal notes and "
        "pages). This does NOT search the web or general knowledge. Do not use it to "
        "look up TV shows, movies, people, facts, or current events — those are handled "
        "by web search automatically. Use only when the user explicitly asks about their "
        "own Notion notes."
    ),
    "API-retrieve-page-markdown": (
        "Read the full markdown of a specific page in the user's private Notion "
        "workspace. Not for web or general-knowledge lookups."
    ),
}


def _headers(session_id: Optional[str] = None) -> dict:
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if _auth():
        h["Authorization"] = f"Bearer {_auth()}"
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def _parse_rpc(resp: httpx.Response) -> dict:
    """Extract the JSON-RPC payload from a JSON or SSE response."""
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        last = None
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if not payload:
                    continue
                try:
                    obj = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                    last = obj
        if last is None:
            raise RuntimeError(f"No JSON-RPC data in SSE response: {resp.text[:300]}")
        return last
    return resp.json()


async def _open_session(client: httpx.AsyncClient) -> str:
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "emotional-rag", "version": "1.0"},
        },
    }
    r = await client.post(_url(), headers=_headers(), json=init)
    r.raise_for_status()
    session_id = r.headers.get("mcp-session-id", "")
    _parse_rpc(r)
    note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    await client.post(_url(), headers=_headers(session_id), json=note)
    return session_id


async def _rpc(method: str, params: dict | None = None) -> dict:
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        session_id = await _open_session(client)
        req = {"jsonrpc": "2.0", "id": 2, "method": method}
        if params is not None:
            req["params"] = params
        r = await client.post(_url(), headers=_headers(session_id), json=req)
        r.raise_for_status()
        obj = _parse_rpc(r)
        if "error" in obj:
            raise RuntimeError(f"MCP error for {method}: {obj['error']}")
        return obj.get("result", {})


async def get_openai_tools() -> list[dict]:
    """Allowlisted Notion tools in OpenAI function-tool format (cached)."""
    global _tools_cache
    if _tools_cache is not None:
        return _tools_cache
    result = await _rpc("tools/list")
    out = []
    for t in result.get("tools", []):
        name = t.get("name")
        if name not in TOOL_ALLOWLIST:
            continue
        if name == "API-post-page":
            params = _SLIM_CREATE_PAGE_SCHEMA
            desc = _SLIM_CREATE_PAGE_DESC
        else:
            params = t.get("inputSchema", {"type": "object", "properties": {}})
            desc = _TOOL_DESC_OVERRIDES.get(name) or (t.get("description") or "").strip()[:1024]
        out.append({
            "type": "function",
            "function": {"name": name, "description": desc, "parameters": params},
        })
    _tools_cache = out
    return out


async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute one Notion tool; return its textual result."""
    if name == GATEWAY_TOOL_NAME:
        # No real work: the agentic loop swaps in the actual tools when it sees
        # this call. Just tell the model the toolset is now available.
        return ("Notion tools unlocked: you can now search, read, and create pages in "
                "the user's private Notion. Call the specific tool you need.")
    if name not in TOOL_ALLOWLIST:
        return f"Error: tool '{name}' is not permitted."
    # Expand the slim create-page args into Notion's full payload.
    if name == "API-post-page" and "title" in arguments and "parent" not in arguments:
        arguments = _build_create_page_payload(arguments)
    try:
        result = await _rpc("tools/call", {"name": name, "arguments": arguments})
    except Exception as e:
        logger.warning(f"Notion tool {name} failed: {e}")
        return f"Tool '{name}' failed: {e}"
    parts = []
    for block in result.get("content", []):
        if isinstance(block, dict):
            parts.append(block.get("text", "") if block.get("type") == "text" else json.dumps(block))
    text = "\n".join(p for p in parts if p)
    if result.get("isError"):
        return f"Tool error: {text}"
    return text or "(empty result)"


if __name__ == "__main__":
    import asyncio

    async def _test():
        tools = await get_openai_tools()
        print(f"allowlisted tools ({len(tools)}): {[t['function']['name'] for t in tools]}")
        print("\n--- search test (query='Character Knowledge') ---")
        print((await call_tool("API-post-search", {"query": "Character Knowledge"}))[:600])

    asyncio.run(_test())
