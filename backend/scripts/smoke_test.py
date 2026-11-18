"""Live smoke test against a running API (default http://localhost:8010).

    python scripts/smoke_test.py [base_url] [admin_password]

Creates one test order and one test variety, then cleans the variety up
(and cancels the order, so stock is restored).
"""
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8010"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "pelargonium2026"
token = None
results = []


def call(method, path, body=None, *, auth=False, raw=None, ctype=None):
    headers = {}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if raw is not None:
        data, headers["Content-Type"] = raw, ctype
    if auth and token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        payload, status = e.read(), e.code
    try:
        return status, json.loads(payload) if payload else None
    except ValueError:
        return status, payload


def check(name, ok, info=""):
    results.append(ok)
    print(f"  {'OK  ' if ok else 'FAIL'} {name}" + (f"  — {info}" if info else ""))


def multipart_png():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (2400, 1600), (230, 120, 160)).save(buf, "PNG")
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"t.png\"\r\n"
            f"Content-Type: image/png\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


for _ in range(30):  # wait for the server
    try:
        if call("GET", "/api/health")[0] == 200:
            break
    except OSError:
        time.sleep(0.5)
else:
    sys.exit(f"API is not reachable at {BASE}")

print(f"\nAPI: {BASE}\n\n[Каталог]")
s, items = call("GET", "/api/varieties")
check("GET /api/varieties", s == 200 and len(items) > 0, f"{len(items)} сортов")
s, r = call("GET", "/api/varieties?type=rosebud")
check("фильтр по типу", s == 200 and all(v["type"] == "rosebud" for v in r), f"{len(r)} розобудных")
s, r = call("GET", "/api/varieties?color=red&color=white")
check("фильтр по нескольким цветам", s == 200 and {v["color"] for v in r} <= {"red", "white"}, f"{len(r)} шт.")
s, r = call("GET", "/api/varieties?in_stock=true")
check("только в наличии", s == 200 and all(v["stock"] > 0 for v in r), f"{len(r)} шт.")
s, r = call("GET", "/api/varieties?q=lord")
check("поиск по названию", s == 200 and [v["name"] for v in r] == ["Lord Bute"])
s, r = call("GET", "/api/varieties?sort=price_desc")
check("сортировка по цене", s == 200 and [v["price"] for v in r] == sorted((v["price"] for v in r), reverse=True))
target = next(v for v in items if v["stock"] >= 2)
s, r = call("GET", f"/api/varieties/{target['id']}")
check("GET /api/varieties/{id}", s == 200 and r["name"] == target["name"], target["name"])
check("несуществующий сорт → 404", call("GET", "/api/varieties/999999")[0] == 404)

print("\n[Заказ]")
order = {"name": "Smoke Test", "phone": "8 (701) 000-00-00", "delivery": "courier", "address": "ул. Тестовая 1",
         "comment": "автотест", "lang": "ru", "items": [{"variety_id": target["id"], "qty": 2}]}
s, r = call("POST", "/api/orders", {**order, "phone": "12345"})
check("неверный телефон → 422", s == 422)
s, r = call("POST", "/api/orders", {**order, "address": ""})
check("курьер без адреса → 422", s == 422)
s, r = call("POST", "/api/orders", {**order, "items": [{"variety_id": target["id"], "qty": target["stock"] + 1}]})
check("больше, чем в наличии → 409", s == 409 and r["detail"]["code"] == "out_of_stock")
s, created = call("POST", "/api/orders", order)
summary = f"{created.get('number')} на {created.get('total')} ₸" if s == 201 else str(created)
check("POST /api/orders", s == 201, summary)
after = call("GET", f"/api/varieties/{target['id']}")[1]
check("наличие уменьшилось на 2", after["stock"] == target["stock"] - 2, f"{target['stock']} → {after['stock']}")

print("\n[Вебхук Тильды]")
TILDA_TOKEN = sys.argv[3] if len(sys.argv) > 3 else "dev-tilda-token"
form = lambda d: urllib.parse.urlencode(d).encode()  # noqa: E731
s, r = call("POST", "/api/tilda/webhook", raw=form({"test": "test"}), ctype="application/x-www-form-urlencoded")
check("проверочный запрос Тильды → ok", s == 200 and r == b"ok")
s, r = call("POST", "/api/tilda/webhook?token=wrong", raw=form({"name": "X", "phone": "87010000000",
                                                                "variety": target["name"]}),
            ctype="application/x-www-form-urlencoded")
check("чужой токен → 401", s == 401)
s, tilda_order = call("POST", f"/api/tilda/webhook?token={TILDA_TOKEN}",
                      raw=form({"Name": "Tilda Smoke", "Phone": "+7 701 000 00 01", "variety": target["name"],
                                "qty": "1", "delivery": "Самовывоз"}),
                      ctype="application/x-www-form-urlencoded")
check("заявка с формы Тильды → заказ", s == 201, tilda_order.get("number") if s == 201 else str(tilda_order))

print("\n[Кабинет владелицы]")
check("без токена → 401", call("GET", "/api/admin/orders")[0] == 401)
check("неверный пароль → 401", call("POST", "/api/admin/login", {"password": "wrong"})[0] == 401)
s, r = call("POST", "/api/admin/login", {"password": PASSWORD})
check("POST /api/admin/login", s == 200 and "token" in r)
token = r.get("token") if s == 200 else None

s, orders = call("GET", "/api/admin/orders", auth=True)
mine = next((o for o in orders or [] if o["number"] == created.get("number")), None)
check("заказ виден в реестре", s == 200 and mine is not None and mine["status"] == "new",
      mine and f"{mine['customer_name']}, {mine['phone']}")
s, r = call("GET", "/api/admin/orders?status=new", auth=True)
check("фильтр заказов по статусу", s == 200 and all(o["status"] == "new" for o in r))
s, r = call("PATCH", f"/api/admin/orders/{mine['id']}", {"status": "confirmed"}, auth=True)
check("смена статуса → confirmed", s == 200 and r["status"] == "confirmed")
s, st = call("GET", "/api/admin/stats", auth=True)
check("GET /api/admin/stats", s == 200, json.dumps(st, ensure_ascii=False))
s, r = call("PATCH", f"/api/admin/orders/{mine['id']}", {"status": "cancelled"}, auth=True)
tilda_mine = next((o for o in orders or [] if o["number"] == tilda_order.get("number")), None)
if tilda_mine:
    check("заказ с Тильды в реестре", tilda_mine["comment"].endswith("[Tilda]"), tilda_mine["customer_name"])
    call("PATCH", f"/api/admin/orders/{tilda_mine['id']}", {"status": "cancelled"}, auth=True)
back = call("GET", f"/api/varieties/{target['id']}")[1]
check("отмена возвращает растения", s == 200 and back["stock"] == target["stock"], f"наличие снова {back['stock']}")

name = f"Smoke Variety {uuid.uuid4().hex[:6]}"
s, v = call("POST", "/api/admin/varieties", {"name": name, "type": "rosebud", "color": "pink",
                                             "price": 3100, "stock": 3, "desc_ru": "Тестовый сорт"}, auth=True)
check("добавление сорта", s == 201, name)
duplicate = {"name": name.upper(), "type": "ivy", "color": "red", "price": 1, "stock": 0}
check("повтор названия → 409", call("POST", "/api/admin/varieties", duplicate, auth=True)[0] == 409)
s, r = call("PATCH", f"/api/admin/varieties/{v['id']}", {"price": 2800, "stock": 5}, auth=True)
check("изменение цены и наличия", s == 200 and r["price"] == 2800 and r["stock"] == 5)
body, ctype = multipart_png()
s, r = call("POST", f"/api/admin/varieties/{v['id']}/photo", raw=body, ctype=ctype, auth=True)
check("загрузка фото", s == 200 and r["photo_url"].startswith("/uploads/"), r.get("photo_url") if s == 200 else r)
if s == 200:
    ps, img = call("GET", r["photo_url"])
    is_jpeg = isinstance(img, bytes) and img[:2] == b"\xff\xd8"
    check("фото раздаётся сервером", ps == 200 and is_jpeg, f"{len(img)} байт JPEG")
check("в каталоге есть новый сорт", any(x["name"] == name for x in call("GET", "/api/varieties")[1]))
check("удаление сорта", call("DELETE", f"/api/admin/varieties/{v['id']}", auth=True)[0] == 204)
check("сорт пропал из каталога", all(x["name"] != name for x in call("GET", "/api/varieties")[1]))

passed = sum(results)
print(f"\nИтого: {passed}/{len(results)} проверок прошло")
sys.exit(0 if passed == len(results) else 1)
