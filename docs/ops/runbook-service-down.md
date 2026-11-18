# Runbook: сайт не открывается (каталог или кабинет не отвечают)

Для кого: дежурный, который видит систему впервые. Все команды — в PowerShell или терминале
в папке проекта `pelargonium-shop`.

## Признаки

- в каталоге на сайте «Не удалось загрузить каталог» или бесконечная загрузка;
- `http://localhost:8010/api/health` не открывается или отвечает не `200`;
- в Uptime Kuma монитор `/api/health` красный.

## 1. Проверить сервер

```bash
curl http://localhost:8010/api/health
```

| Ответ | Что значит | Куда дальше |
| --- | --- | --- |
| `{"status":"ok","database":"ok","version":"..."}` | всё работает | проблема на стороне Тильды или сети покупателя — шаг 5 |
| `{"status":"degraded","database":"unavailable",...}`, код 503 | сервер жив, база недоступна | шаг 2 |
| `Failed to connect` / `Could not connect` | сервер не запущен | шаг 2, затем шаг 3 |

## 2. Проверить Docker и базу

```bash
docker info --format "{{.ServerVersion}}"
```

Ожидаемо: номер версии, например `29.0.1`.
Если ошибка `failed to connect to the docker API` — **Docker Desktop выключен**: запустите его из меню «Пуск»
и подождите 1–2 минуты, пока команда не начнёт отвечать.

```bash
docker compose up -d db
docker inspect -f "{{.State.Health.Status}}" pelargonium-db
```

Ожидаемо: `healthy` (если `starting` — повторить через 10 секунд).

## 3. Запустить сервер

```bash
cd backend
.venv\Scripts\python -m uvicorn app.main:app --port 8010
```

Ожидаемо в выводе: `Application startup complete.` и `Uvicorn running on http://127.0.0.1:8010`.
Строки `Database is not ready (attempt N/30)` в первые секунды — нормально: сервер ждёт базу.

## 4. Проверить, что помогло

```bash
curl http://localhost:8010/api/health
.venv\Scripts\python scripts\smoke_test.py http://localhost:8010
```

Ожидаемо: health — `"status":"ok"`; живой тест — `Итого: 33/33 проверок прошло`.
Тест создаёт и отменяет один тестовый заказ, поэтому каталог после него не меняется.

## 5. Если не помогло

| Ситуация | Что делать |
| --- | --- |
| `Address already in use` на порту 8010 | порт занят другим процессом: `netstat -ano \| findstr :8010`, закрыть процесс или запустить на другом порту |
| `pelargonium-db` не становится `healthy` | `docker logs pelargonium-db --tail 50`; при повреждении данных — восстановление из копии: `docker exec -i pelargonium-db psql -U pelargonium pelargonium < backup.sql` |
| сервер падает при старте с ошибкой `Set these environment variables for production` | в режиме production не заданы секреты: заполнить `backend/.env` по образцу `.env.example` |
| сайт в Тильде не видит каталог, а health в порядке | проверить адрес сервера в блоке T123 и что домен страницы разрешён в `CORS_ORIGINS` |
| ничего из выше | откатиться на предыдущий релиз по [релизному плану](../release-plan.md#план-отката) и сообщить ответственному за релиз |

После восстановления: записать в чат команды время начала и конца сбоя и что помогло — это данные для разбора
и для метрики Time to Restore.
