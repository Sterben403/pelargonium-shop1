def test_widget_admin_and_demo_are_served(client):
    js = client.get("/static/widget/pelargonium.js")
    assert js.status_code == 200 and "pelargonium-catalog" in js.text
    assert client.get("/static/i18n.json").json()["kk"]["cart"] == "Себет"
    assert "pelargonium.js" in client.get("/demo").text
    assert "admin.js" in client.get("/admin").text


def test_cors_allows_tilda_sites_only(client):
    for origin in ("https://pelargonium.tilda.ws", "https://project123.tilda.ws", "https://tilda.cc"):
        r = client.get("/api/varieties", headers={"Origin": origin})
        assert r.headers.get("access-control-allow-origin") == origin, origin
    r = client.get("/api/varieties", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_preflight_for_order_from_tilda(client):
    r = client.options("/api/orders", headers={"Origin": "https://pelargonium.tilda.ws",
                                               "Access-Control-Request-Method": "POST",
                                               "Access-Control-Request-Headers": "content-type"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://pelargonium.tilda.ws"
