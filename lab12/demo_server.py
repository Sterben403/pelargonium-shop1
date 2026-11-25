"""ЛЗ 12: локальное демо умного поиска для защиты. Публичный сайт и backend не меняются.

Поднимает тот же FastAPI-магазин (backend/app) на временной SQLite-базе с каталогом из seed_data.json
и добавляет к нему только страницу /ai-demo и эндпоинт /api/lab12/search:
  mode=baseline — существующий поиск сайта (та же функция list_varieties, подстрока в названии);
  mode=ai       — локальная модель через Ollama с полным каталогом в промпте (тот же prompt.txt,
                  что и в eval). ID проверяются по базе, карточки берутся из базы. При сбое,
                  тайм-ауте или занятой модели — откат на обычный поиск с пометкой fallback.

Запуск: lab12\\start_demo.cmd  (или python lab12/demo_server.py), затем http://127.0.0.1:8012/ai-demo
Выключить ИИ: AI_SEARCH_ENABLED=false — все запросы идут в обычный поиск.
"""
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))

if "DATABASE_URL" not in os.environ:  # своя временная база: демо не трогает базу магазина
    _tmp = Path(tempfile.mkdtemp(prefix="lab12-demo-"))
    os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'demo.db').as_posix()}"
    os.environ.setdefault("UPLOAD_DIR", str(_tmp / "uploads"))

import httpx  # noqa: E402
from fastapi import Depends, Query  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Variety  # noqa: E402
from app.routers.public import list_varieties  # noqa: E402
from app.schemas import VarietyOut  # noqa: E402

OLLAMA = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("AI_MODEL", "qwen2.5:3b")
AI_ENABLED = os.getenv("AI_SEARCH_ENABLED", "true").lower() != "false"
TIMEOUT_S = float(os.getenv("AI_TIMEOUT_S", "60"))
MAX_QUERY = 400
PROMPT = (ROOT / "prompt.txt").read_text(encoding="utf-8")
SCHEMA = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["found", "none", "clarify"]},
                   "ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 3}},
    "required": ["status", "ids"],
}
_model_lock = threading.Lock()  # один вызов модели одновременно: ноутбук не тянет параллельные
_cache: "OrderedDict[str, dict]" = OrderedDict()


def _baseline(q: str, db: Session) -> list[VarietyOut]:
    return list_varieties(q=q, type=None, color=[], in_stock=False, sort="default", db=db)[:3]


def _ask_model(q: str, rows: list[Variety]) -> dict:
    catalog = json.dumps([{"id": v.id, "name": v.name, "type": v.type, "color": v.color, "price": v.price,
                           "stock": v.stock, "desc": v.desc_ru or v.desc_en} for v in rows], ensure_ascii=False)
    key = hashlib.sha256((catalog + "\n" + q).encode()).hexdigest()  # кэш учитывает и каталог
    if key in _cache:
        _cache.move_to_end(key)
        return {**_cache[key], "cached": True}
    if not _model_lock.acquire(timeout=TIMEOUT_S):
        raise TimeoutError("model is busy")
    try:
        r = httpx.post(f"{OLLAMA}/api/chat", timeout=TIMEOUT_S, json={
            "model": MODEL, "stream": False, "format": SCHEMA, "keep_alive": "30m",
            "messages": [{"role": "system", "content": PROMPT.replace("{catalog}", catalog)},
                         {"role": "user", "content": q}],
            "options": {"temperature": 0, "seed": 42, "num_predict": 100, "num_ctx": 8192}})
        r.raise_for_status()
    finally:
        _model_lock.release()
    parsed = json.loads(r.json()["message"]["content"])
    if parsed.get("status") not in ("found", "none", "clarify"):
        raise ValueError("bad status")
    result = {"status": parsed["status"], "ids": parsed.get("ids") or []}
    _cache[key] = result
    if len(_cache) > 128:
        _cache.popitem(last=False)
    return {**result, "cached": False}


@app.get("/api/lab12/search", tags=["lab12"])
def lab12_search(q: str = Query(..., min_length=1), mode: str = "ai", db: Session = Depends(get_db)):
    q = q.strip()[:MAX_QUERY]
    t = time.perf_counter()
    out = {"mode": mode, "used": "baseline", "status": None, "items": [], "fallback": None, "cached": False}
    if mode == "ai" and not AI_ENABLED:
        out["fallback"] = "ИИ выключен (AI_SEARCH_ENABLED=false)"
    elif mode == "ai":
        rows = list(db.scalars(select(Variety).where(Variety.is_active.is_(True)).order_by(Variety.id)))
        by_id = {v.id: v for v in rows}
        try:
            res = _ask_model(q, rows)
            ids = [i for i in dict.fromkeys(res["ids"]) if i in by_id][:3]  # только существующие сорта
            if res["status"] == "found" and not ids:
                raise ValueError("found without valid ids")
            out.update(used="ai", status=res["status"], cached=res["cached"],
                       items=[VarietyOut.from_model(by_id[i]) for i in ids] if res["status"] == "found" else [])
        except Exception as exc:  # сеть, тайм-аут, занятая модель, битый JSON -> обычный поиск
            out["fallback"] = f"Умный подбор недоступен ({type(exc).__name__}), показан обычный поиск"
    if out["used"] == "baseline":
        out["items"] = _baseline(q, db)
        out["status"] = "found" if out["items"] else "none"
    out["latency_ms"] = round((time.perf_counter() - t) * 1000)
    return out


@app.get("/api/lab12/status", tags=["lab12"])
def lab12_status():
    try:
        names = [m["name"] for m in httpx.get(f"{OLLAMA}/api/tags", timeout=3).json().get("models", [])]
        ready = MODEL in names
    except httpx.HTTPError:
        ready = False
    return {"model": MODEL, "enabled": AI_ENABLED, "model_ready": ready}


@app.get("/ai-demo", include_in_schema=False)
def ai_demo_page():
    return FileResponse(ROOT / "demo.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8012")))
