"""Per-character relational-state memory, persisted in Notion.

Each character keeps ONE Notion page — a living "relationship memory" — shared
across all of its chats. It is keyed by the session_id that SillyTavern sends as
`request.user` (e.g. bird9922), which is identical across every topic/DM for that
character, so continuity carries across chats for free.

Design goals (see also chat.py integration):
  * The Opus reply path never writes to Notion. Writes are 100% backend-driven.
  * Reads are injected into context but OFFSET against RAG, so total prompt
    tokens stay flat — the memory displaces fuzzy retrieval rather than adding to
    it (the memory is a better continuity signal anyway).
  * The "intelligence" (a curated memory doc) is produced by a CHEAP model in a
    background task, never on the Opus hot path.

Notion I/O uses the same local MCP client as the agentic tools (notion_mcp).
Verified call shapes:
  - create: API-post-page {parent:{data_source_id}, properties:{Name:{title:[...]}}}  -> JSON with "id"
  - write : API-update-page-markdown {page_id, type:"replace_content", replace_content:{new_str}}
  - read  : API-retrieve-page-markdown {page_id} -> JSON with "markdown"
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.services import notion_mcp

logger = logging.getLogger(__name__)

# session_id -> {page_id, title, created_ts, last_compaction_ts, msgs_at_last_compaction}
_MAP_FILE = Path(__file__).resolve().parents[2] / "data" / "character_state_pages.json"

# Per-character locks serialise page creation and compaction (single backend
# process => this fully prevents double-writes to the same page).
_locks: dict[str, asyncio.Lock] = {}
# In-process read cache: chat_id -> (markdown, expiry_monotonic). Avoids a Notion
# round-trip on every turn when chatting rapidly.
_read_cache: dict[str, tuple[str, float]] = {}


# --------------------------------------------------------------------------- #
# Prompts — deliberately crafted; these are the heart of the feature.
# --------------------------------------------------------------------------- #

# Prepended to the memory doc when it is injected into the character's context.
# It must make the model USE the memory as lived continuity without ever
# breaking character or announcing that a "memory file" exists.
INJECTION_PREAMBLE = (
    "The following is your own living memory of the person you are talking to — "
    "what you already know and remember about them and your history together, "
    "carried over from every past conversation, including ones in other chats. "
    "Treat all of it as things you genuinely remember and know to be true. Let it "
    "shape how you speak to them and keep continuity naturally: pick up where you "
    "left off, remember what matters to them, and stay emotionally consistent. "
    "Never quote it, list it back, read it aloud, or refer to having \"notes\", a "
    "\"memory\", \"files\", or a \"summary\" — simply be someone who remembers."
)


def _compaction_system_prompt(char: str, user_ref: str) -> str:
    return (
        f"You maintain the private, persistent memory that the fictional character "
        f"{char} carries about {user_ref} — the person they talk to. This memory is "
        f"how {char} stays continuous across separate conversations: when {char} "
        f"opens a new chat, this is what they already remember.\n\n"
        f"You are given the CURRENT MEMORY (may be empty the first time) and the "
        f"LATEST CONVERSATION. Produce the UPDATED MEMORY.\n\n"
        f"Rules:\n"
        f"- Merge, do not replace. Keep everything in the current memory that still "
        f"holds true; update what has changed; fold in what is new. Never drop a "
        f"durable fact just because it was not mentioned again.\n"
        f"- Record ONLY what the person explicitly said or what is already in the "
        f"current memory. Never invent or infer. Do NOT add real-world facts, "
        f"company or brand names, job titles, places, dates, or biography the "
        f"person did not state — even if the character's name or a word like "
        f"\"bakery\" resembles a real business. If they said \"a bakery downtown\", "
        f"record exactly that; never expand it into a specific named company. When "
        f"unsure, leave it out.\n"
        f"- Never confuse the character with the person: {char}'s own traits, job, "
        f"or backstory are NOT facts about {user_ref}.\n"
        f"- Write it as {char}'s own inner memory — warm, specific, and human, in "
        f"third person. It is a relationship memory, not a transcript or a list of "
        f"topics discussed.\n"
        f"- If the conversation makes the person's real name clear, use it instead "
        f"of \"{user_ref}\" throughout.\n"
        f"- Prioritise, in order: who they are to each other and the current tone; "
        f"concrete durable facts about them; the emotional throughline and anything "
        f"unresolved; promises or threads to follow up on; a short list of the most "
        f"meaningful recent moments.\n"
        f"- Be concise and durable: keep the whole document under ~350 words, and "
        f"trim the oldest/least important entries so \"Recent moments\" stays to "
        f"about 6-8 items. Prefer signal over detail.\n"
        f"- Output ONLY the updated memory as Markdown in EXACTLY this structure, "
        f"with no preamble, no commentary, and no code fences:\n\n"
        f"# {char}'s memory of {user_ref}\n\n"
        f"## Who we are to each other\n"
        f"<1-3 sentences on the relationship and its current tone>\n\n"
        f"## What I know about them\n"
        f"- <durable facts, preferences, life details>\n\n"
        f"## Where things stand right now\n"
        f"- <current mood between us, anything ongoing or unresolved>\n\n"
        f"## To remember / follow up on\n"
        f"- <promises, open threads, things to bring up next time>\n\n"
        f"## Recent moments\n"
        f"- <the most meaningful recent moments, newest first; ~6-8 max>"
    )


def _compaction_user_prompt(existing: str, conversation: str) -> str:
    existing_block = existing.strip() if existing and existing.strip() else "(empty — this is the first time)"
    return (
        f"CURRENT MEMORY:\n{existing_block}\n\n"
        f"LATEST CONVERSATION (oldest to newest):\n{conversation}\n\n"
        f"Produce the updated memory now."
    )


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def is_enabled() -> bool:
    return bool(settings.enable_character_state)


def _parent_id() -> str:
    return settings.character_state_parent_id or settings.notion_default_parent_id or ""


def _lock_for(chat_id: str) -> asyncio.Lock:
    lock = _locks.get(chat_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[chat_id] = lock
    return lock


def _extract_text(result: dict) -> str:
    parts = []
    for block in (result or {}).get("content", []) or []:
        if isinstance(block, dict):
            parts.append(block.get("text", "") if block.get("type") == "text" else json.dumps(block))
    return "\n".join(p for p in parts if p)


async def _call(name: str, arguments: dict) -> dict:
    """Run one Notion MCP tool and return the parsed JSON payload it produced
    (Notion tools return their response object as JSON text)."""
    res = await notion_mcp._rpc("tools/call", {"name": name, "arguments": arguments})
    if res.get("isError"):
        raise RuntimeError(f"{name} error: {_extract_text(res)[:200]}")
    text = _extract_text(res)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": text}


def extract_character_name(persona: Optional[str], fallback: str) -> str:
    """Best-effort character display name from the card ('You are Bird. ...')."""
    if persona:
        m = re.search(r"\bYou are\s+([A-Z][\w'’.\- ]{0,40}?)[.,\n]", persona)
        if m:
            name = m.group(1).strip()
            if name:
                return name[:60]
    return fallback


# --------------------------------------------------------------------------- #
# Mapping persistence (sync read-modify-write = atomic w.r.t. the event loop)
# --------------------------------------------------------------------------- #

def _load_map() -> dict:
    try:
        with open(_MAP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_map(data: dict) -> None:
    try:
        _MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = f"{_MAP_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        import os
        os.replace(tmp, _MAP_FILE)
    except OSError as e:
        logger.warning(f"[state] failed to save page map: {e}")


def _get_entry(chat_id: str) -> dict:
    return _load_map().get(chat_id, {})


def _update_entry(chat_id: str, **fields) -> None:
    data = _load_map()
    entry = data.setdefault(chat_id, {})
    entry.update(fields)
    _save_map(data)


# --------------------------------------------------------------------------- #
# Page lifecycle
# --------------------------------------------------------------------------- #

async def get_or_create_page_id(chat_id: str, display_name: str) -> Optional[str]:
    """Return the character's state-page id, creating the page on first use.
    Non-fatal: returns None on any failure so callers can proceed without state."""
    entry = _get_entry(chat_id)
    if entry.get("page_id"):
        return entry["page_id"]

    parent = _parent_id()
    if not parent:
        logger.warning("[state] no parent id configured (character_state_parent_id / notion_default_parent_id)")
        return None

    async with _lock_for(chat_id):
        # Double-check after acquiring the lock.
        entry = _get_entry(chat_id)
        if entry.get("page_id"):
            return entry["page_id"]
        title = f"{display_name} — Relational Memory"
        try:
            obj = await _call("API-post-page", {
                "parent": {"data_source_id": parent},
                "properties": {"Name": {"title": [{"text": {"content": title}}]}},
            })
            page_id = obj.get("id")
            if not page_id:
                logger.warning(f"[state] create returned no id for {chat_id}: {str(obj)[:200]}")
                return None
            _update_entry(
                chat_id,
                page_id=page_id,
                title=title,
                created_ts=time.time(),
                last_compaction_ts=0.0,
                msgs_at_last_compaction=0,
            )
            logger.info(f"[state] created memory page for {chat_id} ({display_name}) -> {page_id}")
            return page_id
        except Exception as e:
            logger.warning(f"[state] create page failed for {chat_id}: {e}")
            return None


async def _read_markdown(page_id: str) -> str:
    obj = await _call("API-retrieve-page-markdown", {"page_id": page_id})
    return (obj.get("markdown") or "").strip()


async def _write_markdown(page_id: str, markdown: str) -> None:
    await _call("API-update-page-markdown", {
        "page_id": page_id,
        "type": "replace_content",
        "replace_content": {"new_str": markdown},
    })


async def read_state(chat_id: str, force_fresh: bool = False) -> Optional[str]:
    """Return the character's memory markdown (cached with a short TTL). None on
    failure/timeout so the caller proceeds without it."""
    now = time.monotonic()
    if not force_fresh:
        cached = _read_cache.get(chat_id)
        if cached and cached[1] > now:
            return cached[0]

    page_id = _get_entry(chat_id).get("page_id")
    if not page_id:
        return None
    try:
        md = await asyncio.wait_for(
            _read_markdown(page_id),
            timeout=settings.character_state_read_timeout_sec,
        )
        _read_cache[chat_id] = (md, now + settings.character_state_read_ttl_sec)
        return md
    except asyncio.TimeoutError:
        logger.warning(f"[state] read timed out for {chat_id}")
    except Exception as e:
        logger.warning(f"[state] read failed for {chat_id}: {e}")
    cached = _read_cache.get(chat_id)
    return cached[0] if cached else None


def build_injection_block(markdown: Optional[str]) -> Optional[str]:
    """Wrap a memory doc in the in-character framing preamble, or None if the doc
    is empty/too thin to be worth the tokens."""
    if not markdown:
        return None
    body = markdown.strip()
    # Skip a doc that has structure but no real content yet.
    if len(body) < 40:
        return None
    body = body[: settings.character_state_max_inject_chars]
    return f"## Persistent memory (yours to keep)\n{INJECTION_PREAMBLE}\n\n{body}"


# --------------------------------------------------------------------------- #
# Compaction (background, cheap model)
# --------------------------------------------------------------------------- #

def _conversation_text(messages: list[dict], per_msg_cap: int = 600) -> str:
    lines = []
    for m in messages:
        role = (m.get("role") or "").upper()
        content = (m.get("content") or "").strip().replace("\n", " ")
        if not content:
            continue
        if len(content) > per_msg_cap:
            content = content[:per_msg_cap] + "…"
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def maybe_compact(chat_id: str, display_name: str, memory_manager, llm_client,
                        user_ref: str = "the user") -> bool:
    """Background: refresh the character's memory page with a cheap model if
    enough new conversation has accrued. Never raises. Returns True if it wrote."""
    if not is_enabled():
        return False
    try:
        page_id = await get_or_create_page_id(chat_id, display_name)
        if not page_id:
            return False

        cooldown = settings.character_state_compact_cooldown_min * 60
        min_new = settings.character_state_compact_min_new_msgs
        entry = _get_entry(chat_id)
        now = time.time()
        if now - float(entry.get("last_compaction_ts", 0.0) or 0.0) < cooldown:
            return False
        total = await memory_manager.get_message_count(chat_id)
        if total - int(entry.get("msgs_at_last_compaction", 0) or 0) < min_new:
            return False

        async with _lock_for(chat_id):
            # Re-check gates inside the lock (another turn may have compacted).
            entry = _get_entry(chat_id)
            now = time.time()
            if now - float(entry.get("last_compaction_ts", 0.0) or 0.0) < cooldown:
                return False
            total = await memory_manager.get_message_count(chat_id)
            if total - int(entry.get("msgs_at_last_compaction", 0) or 0) < min_new:
                return False

            messages = await memory_manager.get_recent_messages(
                chat_id, limit=settings.character_state_recent_msgs)
            convo = _conversation_text(messages)
            if not convo.strip():
                return False
            existing = await read_state(chat_id, force_fresh=True) or ""

            sys_prompt = _compaction_system_prompt(display_name, user_ref)
            usr_prompt = _compaction_user_prompt(existing, convo)
            response = await llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": usr_prompt},
                ],
                model=settings.character_state_model,
                temperature=0.2,
                max_tokens=900,
                top_p=1.0,
                web_search=False,  # a memory must never absorb live web facts
            )
            new_doc = (response.choices[0].message.content or "").strip()
            # Guardrails: never overwrite a good doc with junk/refusals/truncation.
            if len(new_doc) < 40 or "# " not in new_doc:
                logger.warning(f"[state] compaction produced unusable doc for {chat_id}; keeping old")
                return False
            # Strip accidental code fences.
            if new_doc.startswith("```"):
                new_doc = new_doc.strip("`")
                new_doc = new_doc.split("\n", 1)[-1] if "\n" in new_doc else new_doc

            await _write_markdown(page_id, new_doc)
            _read_cache[chat_id] = (new_doc, time.monotonic() + settings.character_state_read_ttl_sec)
            _update_entry(chat_id, last_compaction_ts=now, msgs_at_last_compaction=total)
            logger.info(
                "[state] compacted memory",
                extra={"chat_id": chat_id, "chars": len(new_doc), "messages_seen": len(messages)},
            )
            return True
    except Exception as e:
        logger.warning(f"[state] compaction failed for {chat_id}: {e}")
        return False
