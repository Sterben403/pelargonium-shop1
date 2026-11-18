# Публичный сайт: Render + Neon

Сайт для других команд и заказчика:

- **Neon** — база PostgreSQL (бесплатно, не удаляется по сроку);
- **Render** — сайт: каталог, виджет для Тильды, кабинет владелицы (бесплатно);
- настройки Render лежат в репозитории — [`render.yaml`](../render.yaml).

Каждое слияние в `main` (только через PR с зелёными проверками) Render выкатывает автоматически.

## 1. Neon — база

1. neon.tech → **Sign up with GitHub**.
2. Create project: имя `pelargonium`, регион **AWS Europe Central 1 (Frankfurt)**.
3. **Connect** → скопировать строку подключения `postgresql://…neon.tech/neondb?sslmode=require`.
   Это секрет: в репозиторий и чаты не отправляем.

## 2. Render — сайт

1. render.com → **Sign up with GitHub**, разрешить доступ к репозиторию `pelargonium-shop1`.
2. **New → Blueprint** → выбрать `pelargonium-shop1` → Render прочитает `render.yaml`.
3. Заполнить два поля:
   - `DATABASE_URL` — строка из Neon;
   - `ADMIN_PASSWORD` — новый пароль владелицы (не демо-пароль из репозитория).

   `SECRET_KEY` и `TILDA_WEBHOOK_TOKEN` Render создаст сам.
4. **Apply**. Первая сборка — 5–10 минут.
5. Проверка: `https://<имя>.onrender.com/api/health` → `"status": "ok"`, `"database": "ok"`,
   `version` — коммит из `main`.

## Адреса для других команд

| Что | Адрес |
| --- | --- |
| Сайт (UAT) | `https://<имя>.onrender.com/demo` |
| Кабинет владелицы | `https://<имя>.onrender.com/admin` |
| Код для блока T123 в Тильде | `<script src="https://<имя>.onrender.com/static/widget/pelargonium.js"></script>` |

## Ограничения бесплатного тарифа

- Без посетителей 15 минут сайт засыпает, первое открытие после этого — около минуты.
  Перед UAT или защитой откройте `/api/health`, чтобы его разбудить.
- Загруженные в кабинете фото хранятся на диске сервера и пропадают при новом выкате.
  Фото стартовых сортов не пропадают: они берутся с Wikimedia Commons.

## Откат

Render → сервис → **Events** → у предыдущего успешного выката **Rollback**,
либо Revert PR в GitHub — см. [релизный план](release-plan.md#план-отката).
