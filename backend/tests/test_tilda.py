import json

URL = "/api/tilda/webhook?token=dev-tilda-token"


def stock_of(client, name):
    return next(v for v in client.get("/api/varieties").json() if v["name"] == name)["stock"]


def test_connection_test_request(client):
    r = client.post("/api/tilda/webhook", data={"test": "test"})
    assert r.status_code == 200 and r.text == "ok"


def test_rejects_wrong_token(client):
    form = {"name": "Ая", "phone": "87011112233", "variety": "Lord Bute"}
    r = client.post("/api/tilda/webhook?token=wrong", data=form)
    assert r.status_code == 401


def test_plain_form_creates_order(admin):
    before = stock_of(admin, "Scarlet Zonal")
    r = admin.post(URL, data={"Name": "Аяулым", "Phone": "+7 (701) 111-22-33", "variety": "scarlet zonal",
                              "qty": "2", "delivery": "Курьер", "address": "ул. Абая 10"})
    assert r.status_code == 201, r.text
    assert r.json()["number"] == "PS-1001"
    assert stock_of(admin, "Scarlet Zonal") == before - 2
    order = admin.get("/api/admin/orders").json()[0]
    assert order["delivery"] == "courier" and order["comment"].endswith("[Tilda]")


def test_tilda_cart_payment_json(client):
    payment = {"orderid": "123", "products": [{"name": "Lord Bute", "quantity": 1, "price": 5000},
                                              {"name": "Rocky Mountain White, горшок 9 см", "quantity": 3}]}
    r = client.post(URL, data={"name": "Еснур", "phone": "87012223344", "payment": json.dumps(payment)})
    assert r.status_code == 201, r.text
    assert r.json()["total"] == 5000 + 3 * 1200


def test_tilda_cart_flattened_fields(client):
    r = client.post(URL, data={"name": "Еснур", "phone": "87012223344",
                               "payment[products][0][name]": "Silver Glitter", "payment[products][0][quantity]": "1",
                               "payment[products][1][name]": "Robyn Hannah", "payment[products][1][quantity]": "2"})
    # Silver Glitter is out of stock in the seed data
    assert r.status_code == 409


def test_unknown_variety(client):
    r = client.post(URL, data={"name": "Ая", "phone": "87011112233", "variety": "Несуществующий"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "variety_not_found"
