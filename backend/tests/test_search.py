import json

import pytest

from app import ai_search, config


@pytest.fixture()
def ai_on(monkeypatch):
    monkeypatch.setattr(config, "AI_SEARCH_ENABLED", True)
    ai_search._cache.clear()
    yield
    ai_search._cache.clear()


def fake_model(monkeypatch, answer=None, error=None):
    calls = []

    def call(system_prompt, query):
        calls.append((system_prompt, query))
        if error:
            raise ai_search.AISearchError(error)
        return answer if isinstance(answer, str) else json.dumps(answer)

    monkeypatch.setattr(ai_search, "_call_model", call)
    return calls


def ids_by_name(client):
    return {v["name"]: v["id"] for v in client.get("/api/varieties").json()}


def test_ai_off_by_default_answers_with_regular_search(client):
    assert client.get("/api/search/status").json() == {"enabled": False, "ready": False}
    r = client.get("/api/search", params={"q": "lord"}).json()
    assert r["mode"] == "name" and r["fallback"] is False
    assert [v["name"] for v in r["items"]] == ["Lord Bute"]


def test_ai_picks_varieties_and_drops_unknown_ids(client, ai_on, monkeypatch):
    names = ids_by_name(client)
    apple = names["Apple Blossom Rosebud"]
    calls = fake_model(monkeypatch, {"status": "found", "ids": [apple, 999, apple]})
    r = client.get("/api/search", params={"q": "белые розочки до 4000"}).json()
    assert r["mode"] == "ai" and r["status"] == "found"
    assert [v["name"] for v in r["items"]] == ["Apple Blossom Rosebud"]  # 999 and the duplicate are gone
    assert r["items"][0]["price"] == 3500  # card data comes from the database
    system_prompt, query = calls[0]
    assert "Apple Blossom Rosebud" in system_prompt and query == "белые розочки до 4000"


def test_ai_clarify_and_none_show_no_products(client, ai_on, monkeypatch):
    fake_model(monkeypatch, {"status": "clarify", "ids": [1, 2]})
    r = client.get("/api/search", params={"q": "какой сорт можно съесть?"}).json()
    assert r == {"mode": "ai", "status": "clarify", "items": [], "fallback": False}


@pytest.mark.parametrize("answer, error", [(None, "ConnectError"), ("not json", None),
                                           ({"status": "maybe", "ids": []}, None),
                                           ({"status": "found", "ids": [999]}, None)])
def test_model_failure_falls_back_to_regular_search(client, ai_on, monkeypatch, answer, error):
    fake_model(monkeypatch, answer, error)
    r = client.get("/api/search", params={"q": "Pink Ivy"}).json()
    assert r["mode"] == "name" and r["fallback"] is True
    assert [v["name"] for v in r["items"]] == ["Pink Ivy"]


def test_answers_are_cached_until_the_catalog_changes(client, admin, ai_on, monkeypatch):
    calls = fake_model(monkeypatch, {"status": "none", "ids": []})
    for _ in range(2):
        assert client.get("/api/search", params={"q": "синие"}).json()["status"] == "none"
    assert len(calls) == 1
    first = client.get("/api/varieties").json()[0]
    admin.patch(f"/api/admin/varieties/{first['id']}", json={"price": first["price"] + 100})
    client.get("/api/search", params={"q": "синие"})
    assert len(calls) == 2


def test_long_and_blank_queries(client, ai_on, monkeypatch):
    calls = fake_model(monkeypatch, {"status": "none", "ids": []})
    client.get("/api/search", params={"q": "ы" * 1000})
    assert len(calls[0][1]) == ai_search.MAX_QUERY
    assert client.get("/api/search", params={"q": "   "}).json()["status"] == "clarify"
