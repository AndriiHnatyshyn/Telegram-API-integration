# 🚀 Telegram Chats Parser (API + Bot)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688)]()
[![Telethon](https://img.shields.io/badge/Telethon-1.33.1-2CA5E0)]()
[![Aiogram](https://img.shields.io/badge/Aiogram-3.x-2CA5E0)]()
[![SQLite / Postgres](https://img.shields.io/badge/DB-SQLite%20or%20Postgres-4E9A06)]()

**Telegram Chats Parser** is a production-ready application designed to collect, store, and analyze Telegram chat history.  
It includes a **FastAPI backend** (REST + WebSockets) and a **Telegram bot** (Aiogram) powered by **Telethon** for account sessions and scraping.  
It supports notifications, filtering, multiple accounts, proxies, and much more.

> **TL;DR**: Run `run.sh` to start both the **API** and **bot**. Make sure environment variables are configured.

---

## ✨ Key Features

- 📦 **FastAPI** backend with auto-generated documentation (**/docs**, **/redoc**)  
- 🤖 **Telegram Bot** for verification and notifications  
- 🧰 **Telethon** integration for session handling and chat scraping  
- 🧪 Advanced **filters**, **monitoring**, and **forwarding** system  
- 🧑‍🤝‍🧑 Multi-account and multi-user support  
- 🧵 **WebSocket** for live updates  
- 🗄️ **Async SQLAlchemy** (SQLite or PostgreSQL)  
- 🌐 Built-in **proxy** support for Telethon clients  

---

## 🧩 Architecture Overview

```
FastAPI (api/)
 ├─ routers/ … (botApi, userApi, messageApi, chatsApi, filtersApi, proxyApi, securityApi, …)
 ├─ security/ … (JWT, roles, authorization)
 └─ main.py … CORS, OpenAPI, WebSocket setup, bot layer integration

Telegram Layer (bot/)
 ├─ bot.py … Telethon clients, sessions, monitoring, forwarding
 └─ main.py … TelegramChatHistory entry point

Aiogram Bot (telegram/)
 └─ tgbot.py … /start command, verification, notifications

DB (db/)
 ├─ engine.py … async engine + sessionmaker
 ├─ create_tables.py … model initialization
 ├─ models/ … users, accounts, chats, message, proxy, …
 └─ facade.py, crud.py … CRUD facades
```

---

## ⚙️ Requirements

- Python **3.10+**
- Telegram API credentials (Telethon session files will be auto-created)
- Database access (SQLite by default or PostgreSQL)

Install dependencies:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 🔐 Environment Variables

Create a `.env` file in the root directory:

| Key              | Description                                            |
|------------------|--------------------------------------------------------|
| `TOKEN`          | Telegram Bot Token (for Aiogram bot)                  |
| `DB_URL`         | SQLAlchemy connection string (async)                  |
| `BOT_USERNAME`   | Bot username (without @)                              |
| `SECRET_KEY`     | JWT session secret                                    |
| `FRONT_URL`      | Allowed CORS origin                                   |
| `EMAIL_ADDRESS`  | SMTP email sender                                     |
| `EMAIL_PASSWORD` | SMTP password or app-password                         |
| `SMTP_SERVER`    | SMTP server                                           |
| `SMTP_PORT`      | SMTP port                                             |

> Works out-of-the-box with SQLite.  
> Use `asyncpg` for PostgreSQL.

---

## 🏁 Quick Start

1. Initialize the database (one-time):

```bash
python -m db.create_tables
```

2. Run **API** + **Bot** together:

```bash
bash run.sh
```

Or separately:

```bash
# API
python exe.py
# or
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Bot (Aiogram)
python -m telegram.tgbot
```

After launching:
- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

---

## 🔌 Main API Routers

> View full schema in `/docs`.

- `botApi` — manage Telethon sessions and monitoring tasks  
- `userApi`, `securityApi` — registration/login, JWT tokens, roles  
- `chatsApi`, `messageApi` — chat and message operations  
- `filtersApi` — filtering and notification rules  
- `proxyApi` — proxy configuration for accounts  
- `notificationApi`, `scrapeForwardApi` — notifications & content forwarding  

---

## 🧪 Common Workflows

- Add Telegram account → get code → confirm session → join chat → enable monitoring  
- Configure filters (keywords, authors, media types) → receive bot notifications  
- View message history & events via API or admin panel  

---

## 🧯 Troubleshooting

- **Invalid `DB_URL`** → For Postgres, ensure async driver: `postgresql+asyncpg://...`  
- **403 session creation** → Remove broken `.session` file in `bot/sessions/`  
- **CORS issues** → Check `FRONT_URL` in `.env`  
- **SMTP errors** → Validate `EMAIL_*` credentials and app passwords  

---

## 🧱 Security Guidelines

- Keep `SECRET_KEY` private  
- Protect `/docs` with auth on production  
- Never commit `.env` or `.session` files  

---

## 🗺️ Roadmap

- Docker + Docker Compose setup  
- Retry logic for proxy & flood limits  
- Full-text search (Elasticsearch already included)  
- Admin dashboard for filters/chats management  

---

## 📝 License

Include a `LICENSE` file (e.g., MIT) unless otherwise specified.

---

> Last updated: 2025-10-31
