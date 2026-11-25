"""ЛЗ 12: обычный поиск Pelargonium Shop против ИИ-поиска на одном и том же eval-наборе.

Обычный поиск вызывается через настоящий эндпоинт GET /api/varieties?q= (FastAPI TestClient,
временная SQLite-база, каталог из seed_data.json). ИИ-поиск: локальная модель через Ollama,
полный каталог в промпте, ответ JSON {status, ids}; ID проверяются по каталогу, при сбое —
откат на обычный поиск.

Запуск (из корня репозитория, Ollama должен работать на 127.0.0.1:11434):
    python lab12/run_eval.py [--model qwen2.5:3b] [--out lab12/results]
"""
import argparse
import hashlib
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

import httpx
import tiktoken

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO / "backend"))

_tmp = Path(tempfile.mkdtemp(prefix="lab12-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_tmp / 'lab12.db').as_posix()}"
os.environ["UPLOAD_DIR"] = str(_tmp / "uploads")
os.environ.setdefault("ADMIN_PASSWORD", "lab12-local-only")
os.environ.setdefault("SECRET_KEY", "lab12-local-only")

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_if_empty  # noqa: E402

OLLAMA = "http://127.0.0.1:11434"
SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["found", "none", "clarify"]},
        "ids": {"type": "array", "items": {"type": "integer"}, "maxItems": 3},
    },
    "required": ["status", "ids"],
}
ENC = tiktoken.get_encoding("o200k_base")


def baseline(client, query):
    """Существующий поиск сайта: подстрока в названии, первые три результата."""
    t = time.perf_counter()
    rows = client.get("/api/varieties", params={"q": query}).json()
    ms = (time.perf_counter() - t) * 1000
    ids = [r["id"] for r in rows[:3]]
    return {"status": "found" if ids else "none", "ids": ids, "latency_ms": round(ms, 1)}


def catalog_for_prompt(client):
    rows = client.get("/api/varieties").json()
    return [{"id": r["id"], "name": r["name"], "type": r["type"], "color": r["color"],
             "price": r["price"], "stock": r["stock"], "desc": r["description"]["ru"]} for r in rows]


def ai_search(client, model, system_prompt, valid_ids, query):
    body = {
        "model": model, "stream": False, "format": SCHEMA, "keep_alive": "30m",
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": query[:400]}],
        "options": {"temperature": 0, "seed": 42, "num_predict": 100, "num_ctx": 8192},
    }
    t = time.perf_counter()
    out = {"fallback": None, "raw": None, "prompt_tokens": None, "output_tokens": None}
    try:
        r = httpx.post(f"{OLLAMA}/api/chat", json=body, timeout=60)
        r.raise_for_status()
        data = r.json()
        out["raw"] = data["message"]["content"]
        out["prompt_tokens"] = data.get("prompt_eval_count")
        out["output_tokens"] = data.get("eval_count")
        parsed = json.loads(out["raw"])
        status = parsed["status"]
        ids = [i for i in dict.fromkeys(parsed.get("ids") or []) if i in valid_ids][:3]
        if status not in ("found", "none", "clarify"):
            raise ValueError(f"bad status {status!r}")
        if status == "found" and not ids:
            raise ValueError("found without valid ids")
        if status != "found":
            ids = []
        out.update(status=status, ids=ids)
    except Exception as exc:  # тайм-аут, сеть, битый JSON -> обычный поиск
        fb = baseline(client, query)
        out.update(status=fb["status"], ids=fb["ids"], fallback=f"{type(exc).__name__}: {exc}"[:200])
    out["latency_ms"] = round((time.perf_counter() - t) * 1000, 1)
    out["tiktoken_in"] = len(ENC.encode(system_prompt)) + len(ENC.encode(query[:400]))
    out["tiktoken_out"] = len(ENC.encode(out["raw"])) if out["raw"] else 0
    return out


def judge(case, res):
    exp = set(case["expected"])
    strict = res["status"] == case["status"] and (
        case["status"] != "found" or (bool(res["ids"]) and set(res["ids"]) <= exp))
    hit = bool(exp & set(res["ids"][:3])) if case["status"] == "found" else None
    return strict, hit


def pct(a, b):
    return {"n": a, "of": b, "pct": round(100 * a / b, 1) if b else None}


def p95(values):
    s = sorted(values)
    return s[max(0, -(-95 * len(s) // 100) - 1)]  # метод ближайшего ранга


def summarize(rows, system):
    out = {}
    for subset in ("main", "reserve"):
        rs = [r for r in rows if r["set"] == subset]
        found = [r for r in rs if r["gold_status"] == "found"]
        lat = [r[system]["latency_ms"] for r in rs]
        out[subset] = {
            "strict": pct(sum(r[system]["strict"] for r in rs), len(rs)),
            "hit_at_3": pct(sum(r[system]["hit"] for r in found), len(found)),
            "none_correct": pct(sum(r[system]["strict"] for r in rs if r["gold_status"] == "none"),
                                sum(r["gold_status"] == "none" for r in rs)),
            "clarify_correct": pct(sum(r[system]["strict"] for r in rs if r["gold_status"] == "clarify"),
                                   sum(r["gold_status"] == "clarify" for r in rs)),
            "latency_ms_mean": round(statistics.mean(lat), 1),
            "latency_ms_p95": p95(lat),
        }
        kinds = sorted({r["kind"] for r in rs})
        out[subset]["by_kind"] = {k: pct(sum(r[system]["strict"] for r in rs if r["kind"] == k),
                                         sum(r["kind"] == k for r in rs)) for k in kinds}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--out", default=str(ROOT / "results"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases_text = (ROOT / "cases.json").read_text(encoding="utf-8")
    cases = json.loads(cases_text)["cases"]
    template = (ROOT / "prompt.txt").read_text(encoding="utf-8")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_if_empty(db)
    with TestClient(app) as client:
        catalog = catalog_for_prompt(client)
        catalog_json = json.dumps(catalog, ensure_ascii=False)
        system_prompt = template.replace("{catalog}", catalog_json)
        valid = {c["id"] for c in catalog}
        model_info = httpx.post(f"{OLLAMA}/api/show", json={"model": args.model}, timeout=30).json()

        warm = ai_search(client, args.model, system_prompt, valid, "белая пеларгония")  # прогрев, в метрики не входит
        rows = []
        with (out_dir / "raw.jsonl").open("w", encoding="utf-8") as raw:
            for case in cases:
                b = baseline(client, case["query"])
                a = ai_search(client, args.model, system_prompt, valid, case["query"])
                for res in (b, a):
                    res["strict"], res["hit"] = judge(case, res)
                row = {"id": case["id"], "set": case["set"], "kind": case["kind"], "query": case["query"],
                       "gold_status": case["status"], "gold_ids": case["expected"], "baseline": b, "ai": a}
                rows.append(row)
                raw.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(f"{case['id']:>2} base={b['status']}:{b['ids']} ai={a['status']}:{a['ids']} "
                      f"{'OK ' if a['strict'] else 'ERR'} {a['latency_ms']:.0f}ms fb={a['fallback']}")

    ai_rows = [r["ai"] for r in rows]
    summary = {
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "model": args.model,
        "model_details": model_info.get("details"),
        "options": {"temperature": 0, "seed": 42, "num_predict": 100, "num_ctx": 8192},
        "prompt_sha256": hashlib.sha256(template.encode()).hexdigest()[:12],
        "cases_sha256": hashlib.sha256(cases_text.encode()).hexdigest()[:12],
        "catalog_sha256": hashlib.sha256(catalog_json.encode()).hexdigest()[:12],
        "warmup_latency_ms": warm["latency_ms"],
        "baseline": summarize(rows, "baseline"),
        "ai": summarize(rows, "ai"),
        "ai_fallbacks": sum(1 for r in ai_rows if r["fallback"]),
        "tokens": {
            "calls": len(ai_rows),
            "model_tokenizer_in_total": sum(r["prompt_tokens"] or 0 for r in ai_rows),
            "model_tokenizer_out_total": sum(r["output_tokens"] or 0 for r in ai_rows),
            "tiktoken_o200k_in_total": sum(r["tiktoken_in"] for r in ai_rows),
            "tiktoken_o200k_out_total": sum(r["tiktoken_out"] for r in ai_rows),
            "tiktoken_o200k_prefix": len(ENC.encode(system_prompt)),
        },
    }
    t = summary["tokens"]
    for k in list(t):
        if k.endswith("_total"):
            t[k.replace("_total", "_mean")] = round(t[k] / t["calls"], 2)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with (out_dir / "comparison.csv").open("w", encoding="utf-8-sig") as f:
        f.write("id;set;kind;query;gold_status;gold_ids;base_status;base_ids;base_strict;"
                "ai_status;ai_ids;ai_strict;ai_hit3;ai_ms;ai_in_tokens;ai_out_tokens\n")
        for r in rows:
            b, a = r["baseline"], r["ai"]
            f.write(";".join(str(x) for x in (
                r["id"], r["set"], r["kind"], r["query"], r["gold_status"], r["gold_ids"],
                b["status"], b["ids"], b["strict"], a["status"], a["ids"], a["strict"], a["hit"],
                a["latency_ms"], a["prompt_tokens"], a["output_tokens"])) + "\n")
    print(json.dumps({k: summary[k] for k in ("baseline", "ai", "ai_fallbacks", "tokens")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
