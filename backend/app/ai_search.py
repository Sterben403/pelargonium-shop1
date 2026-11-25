"""Smart search: a local language model (Ollama) picks catalog varieties from a free-text wish.

The whole active catalog goes into the prompt (15 varieties fit easily, no vector search needed).
The model only returns {status, ids}; ids are checked against the database by the caller, and
names, prices and stock always come from the database. Measured in lab12/ (LZ 12): the model
understands descriptions well (Hit@3 91 %) but may add extra varieties, so the widget labels it.
"""
import hashlib
import json
import threading
from collections import OrderedDict
from pathlib import Path

import httpx

from . import config
from .models import Variety

PROMPT = Path(__file__).with_name("ai_search_prompt.txt").read_text(encoding="utf-8")
SCHEMA = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["found", "none", "clarify"]},
                   "ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 3}},
    "required": ["status", "ids"],
}
MAX_QUERY = 400

_lock = threading.Lock()  # one model call at a time: a laptop or a small server can't run them in parallel
_cache: "OrderedDict[str, dict]" = OrderedDict()


class AISearchError(Exception):
    """The model is off, busy, unreachable or answered something unusable: use the regular search."""


def model_ready() -> bool:
    if not config.AI_SEARCH_ENABLED:
        return False
    try:
        tags = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2).json().get("models", [])
    except (httpx.HTTPError, ValueError):
        return False
    return any(m.get("name") == config.AI_MODEL for m in tags)


def _call_model(system_prompt: str, query: str) -> str:
    if not _lock.acquire(timeout=config.AI_TIMEOUT_S):
        raise AISearchError("model is busy")
    try:
        r = httpx.post(f"{config.OLLAMA_URL}/api/chat", timeout=config.AI_TIMEOUT_S, json={
            "model": config.AI_MODEL, "stream": False, "format": SCHEMA, "keep_alive": "30m",
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
            "options": {"temperature": 0, "seed": 42, "num_predict": 100, "num_ctx": 8192}})
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise AISearchError(type(exc).__name__) from exc
    finally:
        _lock.release()


def pick(query: str, varieties: list[Variety]) -> tuple[str, list[int]]:
    """Returns (status, ids): status is found | none | clarify; ids exist in `varieties`, at most 3."""
    if not config.AI_SEARCH_ENABLED:
        raise AISearchError("disabled")
    catalog = json.dumps([{"id": v.id, "name": v.name, "type": v.type, "color": v.color, "price": v.price,
                           "stock": v.stock, "desc": v.desc_ru or v.desc_en or v.desc_kk} for v in varieties],
                         ensure_ascii=False)
    key = hashlib.sha256(f"{config.AI_MODEL}\n{catalog}\n{query}".encode()).hexdigest()  # a catalog edit invalidates
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]["status"], _cache[key]["ids"]

    raw = _call_model(PROMPT.replace("{catalog}", catalog), query[:MAX_QUERY])
    try:
        parsed = json.loads(raw)
        status = parsed["status"]
        ids = parsed.get("ids") or []
    except (ValueError, KeyError, TypeError) as exc:
        raise AISearchError("bad JSON") from exc
    if status not in ("found", "none", "clarify"):
        raise AISearchError("bad status")
    known = {v.id for v in varieties}
    ids = [i for i in dict.fromkeys(ids) if isinstance(i, int) and i in known][:3] if status == "found" else []
    if status == "found" and not ids:
        raise AISearchError("no known ids")

    _cache[key] = {"status": status, "ids": ids}
    if len(_cache) > 128:
        _cache.popitem(last=False)
    return status, ids
