import io

from PIL import Image


def variety_by_name(client, name):
    return next(v for v in client.get("/api/varieties").json() if v["name"] == name)


def order_payload(**overrides):
    data = {"name": "Айгерим", "phone": "8 (701) 234-56-78", "delivery": "pickup", "items": []}
    data.update(overrides)
    return data


# ---------- catalog ----------

def test_catalog_lists_seeded_varieties(client):
    items = client.get("/api/varieties").json()
    assert len(items) == 15
    first = items[0]
    assert first["name"] == "Apple Blossom Rosebud"
    assert set(first["description"]) == {"ru", "kk", "en"}
    assert first["photo_credit"]["license"].startswith("CC")


def test_catalog_filters_and_sorting(client):
    rosebud = client.get("/api/varieties", params={"type": "rosebud"}).json()
    assert {v["type"] for v in rosebud} == {"rosebud"}

    colors = client.get("/api/varieties", params=[("color", "red"), ("color", "white")]).json()
    assert {v["color"] for v in colors} <= {"red", "white"} and len(colors) > 0

    in_stock = client.get("/api/varieties", params={"in_stock": True}).json()
    assert all(v["stock"] > 0 for v in in_stock)

    search = client.get("/api/varieties", params={"q": "LORD"}).json()
    assert [v["name"] for v in search] == ["Lord Bute"]

    prices = [v["price"] for v in client.get("/api/varieties", params={"sort": "price_asc"}).json()]
    assert prices == sorted(prices)


def test_unknown_filter_value_is_rejected(client):
    assert client.get("/api/varieties", params={"type": "tulip"}).status_code == 422


# ---------- orders ----------

def test_order_decrements_stock_and_returns_number(client):
    v = variety_by_name(client, "Scarlet Zonal")
    r = client.post("/api/orders", json=order_payload(items=[{"variety_id": v["id"], "qty": 2}]))
    assert r.status_code == 201, r.text
    assert r.json() == {"number": "PS-1001", "total": v["price"] * 2}
    assert variety_by_name(client, "Scarlet Zonal")["stock"] == v["stock"] - 2


def test_order_validation(client):
    v = variety_by_name(client, "Scarlet Zonal")
    items = [{"variety_id": v["id"], "qty": 1}]
    assert client.post("/api/orders", json=order_payload(phone="123", items=items)).status_code == 422
    assert client.post("/api/orders", json=order_payload(name=" ", items=items)).status_code == 422
    assert client.post("/api/orders", json=order_payload(items=[])).status_code == 422
    # courier needs an address
    assert client.post("/api/orders", json=order_payload(delivery="courier", items=items)).status_code == 422
    ok = client.post("/api/orders", json=order_payload(delivery="courier", address="ул. Абая 10", items=items))
    assert ok.status_code == 201


def test_cannot_order_more_than_stock(client):
    v = variety_by_name(client, "Lord Bute")  # stock 1
    r = client.post("/api/orders", json=order_payload(items=[{"variety_id": v["id"], "qty": 2}]))
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "out_of_stock"
    assert variety_by_name(client, "Lord Bute")["stock"] == 1  # nothing was taken


def test_failed_order_does_not_partially_take_stock(client):
    ok, short = variety_by_name(client, "Scarlet Zonal"), variety_by_name(client, "Lord Bute")
    items = [{"variety_id": ok["id"], "qty": 1}, {"variety_id": short["id"], "qty": 5}]
    assert client.post("/api/orders", json=order_payload(items=items)).status_code == 409
    assert variety_by_name(client, "Scarlet Zonal")["stock"] == ok["stock"]


# ---------- admin ----------

def test_admin_requires_token(client):
    assert client.get("/api/admin/orders").status_code == 401
    assert client.post("/api/admin/login", json={"password": "nope"}).status_code == 401
    client.headers["Authorization"] = "Bearer forged.token"
    assert client.get("/api/admin/orders").status_code == 401


def test_admin_sees_orders_and_cancel_returns_stock(admin):
    v = variety_by_name(admin, "Rocky Mountain White")
    admin.post("/api/orders", json=order_payload(items=[{"variety_id": v["id"], "qty": 3}]))
    orders = admin.get("/api/admin/orders").json()
    assert len(orders) == 1 and orders[0]["status"] == "new" and orders[0]["phone"] == "+77012345678"

    oid = orders[0]["id"]
    assert admin.patch(f"/api/admin/orders/{oid}", json={"status": "cancelled"}).json()["status"] == "cancelled"
    assert variety_by_name(admin, "Rocky Mountain White")["stock"] == v["stock"]
    admin.patch(f"/api/admin/orders/{oid}", json={"status": "confirmed"})
    assert variety_by_name(admin, "Rocky Mountain White")["stock"] == v["stock"] - 3

    assert len(admin.get("/api/admin/orders", params={"status": "confirmed"}).json()) == 1
    assert admin.get("/api/admin/orders", params={"status": "new"}).json() == []
    stats = admin.get("/api/admin/stats").json()
    assert stats["in_progress"] == 1 and stats["new_orders"] == 0


def test_admin_creates_edits_and_deletes_variety(admin):
    r = admin.post("/api/admin/varieties", json={
        "name": "Pink Rambler", "type": "rosebud", "color": "pink", "price": 3200, "stock": 4,
        "desc_ru": "Тестовый сорт"})
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["description"]["en"] == "Тестовый сорт"  # falls back to Russian
    assert any(v["name"] == "Pink Rambler" for v in admin.get("/api/varieties").json())

    dup = admin.post("/api/admin/varieties", json={"name": "pink rambler", "type": "ivy", "color": "red",
                                                   "price": 1, "stock": 0})
    assert dup.status_code == 409

    upd = admin.patch(f"/api/admin/varieties/{new['id']}", json={"price": 2900, "stock": 0})
    assert upd.json()["price"] == 2900 and upd.json()["stock"] == 0

    assert admin.delete(f"/api/admin/varieties/{new['id']}").status_code == 204
    assert all(v["name"] != "Pink Rambler" for v in admin.get("/api/varieties").json())
    # re-adding a deleted name revives it instead of failing on the unique constraint
    again = admin.post("/api/admin/varieties", json={"name": "Pink Rambler", "type": "rosebud", "color": "pink",
                                                     "price": 3000, "stock": 1})
    assert again.status_code == 201 and again.json()["id"] == new["id"]


def test_photo_upload_resizes_and_serves(admin):
    v = variety_by_name(admin, "Lord Bute")
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), "pink").save(buf, "PNG")
    r = admin.post(f"/api/admin/varieties/{v['id']}/photo", files={"file": ("p.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["photo_url"].startswith("/uploads/") and body["photo_credit"] is None

    img = Image.open(io.BytesIO(admin.get(body["photo_url"]).content))
    assert max(img.size) == 1200

    bad = admin.post(f"/api/admin/varieties/{v['id']}/photo", files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400
