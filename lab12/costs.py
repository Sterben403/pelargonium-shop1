"""ЛЗ 12: стоимость эксплуатации ИИ-поиска по реальным токенам из results/summary.json.

Тарифы и курсы взяты с официальных страниц 25.11.2026 (ссылки в TARIFFS/RATES).
Нагрузка — наше допущение (в магазине пока нет аналитики поиска), см. LOAD.
    python lab12/costs.py [lab12/results]
"""
import json
import math
import sys
from pathlib import Path

RES = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "results")
s = json.loads((RES / "summary.json").read_text(encoding="utf-8"))
tok = s["tokens"]

RATES = {"date": "2026-11-25", "USD": 458.28, "EUR": 501.45,
         "url": "https://nationalbank.kz/ru/exchangerates/ezhednevnye-oficialnye-rynochnye-kursy-valyut"}
# USD за 1 млн токенов: вход / кэшированный вход / выход
TARIFFS = {
    "OpenAI gpt-5-mini": (0.25, 0.025, 2.00, "https://developers.openai.com/api/docs/pricing"),
    "OpenAI gpt-5-nano": (0.05, 0.005, 0.40, "https://developers.openai.com/api/docs/pricing"),
    "Google gemini-3.5-flash-lite": (0.30, 0.03, 2.50, "https://aistudio.google.com/docs/pricing"),
}
LOAD = {"base": 3_000, "x10": 30_000}  # поисковых запросов в месяц: 100 в день x 30 дней; рост в 10 раз
OPS_HOURS, OPS_RATE_KZT = 4, 5_000      # сопровождение своего сервера: часов в месяц и ставка, допущение
SERVERS = {  # EUR в месяц без НДС, разовая установка
    "Hetzner CCX23 (4 vCPU, 16 GB, CPU)": (73.49, 0, "https://www.hetzner.com/cloud/general-purpose/"),
    "Hetzner GEX45 (RTX PRO 4000, 24 GB)": (214.00, 209.00, "https://www.hetzner.com/dedicated-rootserver/matrix-gpu/"),
}

tin, tout = tok["tiktoken_o200k_in_mean"], tok["tiktoken_o200k_out_mean"]
# общий префикс промпта (инструкция + каталог) одинаков для всех запросов -> кэшируется провайдером
prefix = tok.get("tiktoken_o200k_prefix") or tin
out = {"tokens_per_query": {"in": tin, "out": tout, "cached_prefix": prefix}, "load": LOAD,
       "rates": RATES, "api": {}, "self_hosted": {}}


def kzt(usd):
    return round(usd * RATES["USD"], 2)


for name, (pin, pcache, pout, url) in TARIFFS.items():
    per_q = (tin * pin + tout * pout) / 1e6
    per_q_cache = ((tin - prefix) * pin + prefix * pcache + tout * pout) / 1e6
    out["api"][name] = {"url": url, "usd_per_query": round(per_q, 7), "usd_per_query_cached": round(per_q_cache, 7),
                        "kzt_per_query": kzt(per_q),
                        **{f"kzt_month_{k}": kzt(per_q * n) for k, n in LOAD.items()},
                        **{f"kzt_month_{k}_cached": kzt(per_q_cache * n) for k, n in LOAD.items()}}

main_api = out["api"]["OpenAI gpt-5-mini"]["usd_per_query"]
for name, (eur, setup, url) in SERVERS.items():
    month_kzt = round(eur * RATES["EUR"] + OPS_HOURS * OPS_RATE_KZT, 0)
    out["self_hosted"][name] = {
        "url": url, "eur_month": eur, "setup_eur": setup, "kzt_month_with_ops": month_kzt,
        "setup_kzt": round(setup * RATES["EUR"]),
        # unrounded cost per query: it is about 0.25 tenge, rounding to 0.01 would shift the result by percents
        "breakeven_queries_vs_gpt5mini": math.ceil(month_kzt / (main_api * RATES["USD"])),
        "breakeven_server_only": math.ceil(eur * RATES["EUR"] / (main_api * RATES["USD"])),
    }

(RES / "costs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
