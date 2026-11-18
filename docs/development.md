# Разработка и запуск

Сайт для покупателей собирается в **Тильде**, данные и заказы хранит наш сервер в **PostgreSQL**.
Как собрать страницу в Тильде — [TILDA.md](../TILDA.md).

```text
backend/                 FastAPI + SQLAlchemy + PostgreSQL
  app/routers/           public (каталог, заказы), admin (кабинет), tilda (вебхук форм)
  app/static/widget/     виджет каталога для блока T123 в Тильде + демо-страница
  app/static/admin/      кабинет владелицы (/admin)
  tests/                 автотесты
  scripts/smoke_test.py  живая проверка запущенного сервера
docker-compose.yml       PostgreSQL 16 + Adminer (просмотр базы)
TILDA.md                 как собрать сайт в Тильде — пошагово
mvp/                     первая версия — один HTML-файл без сервера
```

## Запуск

Нужны Docker Desktop и Python 3.11+.

```bash
# 1. База данных (порт 5433)
docker compose up -d db

# 2. Сервер — первый раз
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 3. Сервер — запуск (порт 8010)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8010
```

| Адрес | Что там |
|---|---|
| http://localhost:8010/demo | страница как в Тильде, с виджетом каталога |
| http://localhost:8010/admin | кабинет владелицы (пароль по умолчанию `pelargonium2026`) |
| http://localhost:8010/docs | документация API (Swagger) |

При первом запуске сервер создаёт таблицы и заполняет каталог 15 сортами.
Сбросить базу к исходному состоянию: `.venv\Scripts\python -m app.seed --reset`.

Порты 5433 и 8010 выбраны, потому что 5432 и 8000 на этом компьютере заняты другим проектом.

Настройки — в `backend/.env` (образец: `backend/.env.example`): пароль владелицы, секреты,
адрес базы, разрешённые домены. Перед реальным запуском обязательно поменяйте пароли и секреты.

## Как показать базу данных

**В браузере (Adminer):** `docker compose up -d` поднимает вместе с базой веб-панель → http://localhost:8081

| Поле | Значение |
|---|---|
| System | PostgreSQL |
| Server | `db` |
| Username / Password | `pelargonium` / `pelargonium` |
| Database | `pelargonium` |

- таблица → **select** — данные (сорта, заказы, позиции заказов);
- **Database schema** — схема таблиц со связями (`order_items` → `orders`, `order_items` → `varieties`);
- **SQL command** — свои запросы, например выручка по сортам:
  ```sql
  SELECT i.name, SUM(i.qty) AS sold, SUM(i.qty * i.price) AS revenue
  FROM order_items i JOIN orders o ON o.id = i.order_id
  WHERE o.status <> 'cancelled'
  GROUP BY i.name ORDER BY revenue DESC;
  ```

**В терминале (psql):**

```bash
docker exec -it pelargonium-db psql -U pelargonium -d pelargonium
```

Внутри: `\dt` — список таблиц, `\d orders` — структура таблицы, `\q` — выход.

## Проверки

```bash
cd backend
.venv\Scripts\python -m pytest -q              # автотесты на отдельной базе pelargonium_test
.venv\Scripts\python scripts\smoke_test.py     # живая проверка запущенного сервера
```

## API

| Метод | Путь | Что делает |
|---|---|---|
| GET | `/api/varieties?q=&type=&color=&in_stock=&sort=` | каталог с фильтрами |
| GET | `/api/varieties/{id}` | один сорт |
| POST | `/api/orders` | оформить заказ (списывает наличие) |
| POST | `/api/tilda/webhook?token=` | заявка с формы / корзины Тильды |
| POST | `/api/admin/login` | вход владелицы → токен |
| GET | `/api/admin/orders?status=` | реестр заказов |
| PATCH | `/api/admin/orders/{id}` | сменить статус (отмена возвращает наличие) |
| GET | `/api/admin/stats` | сводка для кабинета |
| GET/POST | `/api/admin/varieties` | список / добавить сорт |
| PATCH/DELETE | `/api/admin/varieties/{id}` | изменить / удалить сорт |
| POST | `/api/admin/varieties/{id}/photo` | загрузить фото (сжимается до 1200 px) |

Админские запросы требуют заголовок `Authorization: Bearer <token>`.

Фото стартовых сортов — Wikimedia Commons (CC BY / CC BY-SA), автор хранится в базе и показывается на сайте.
