# LexAI Professional

AI-powered legal assistant for Uzbekistan's laws. Answers questions about codes, statutes, and legal articles sourced from [Lex.uz](https://lex.uz).

**Stack:** FastAPI · Aiogram 3 · Ollama · PostgreSQL + pgvector · sentence-transformers

---

## Architecture

```
app/
├── core/           Settings, logging, constants
├── interfaces/     ABCs — AbstractScraper, AbstractDatabase, AbstractAgentService
├── repository/     DatabaseRepository (wraps legacy database.py)
├── services/       AgentService, ScraperService, SessionService
├── api/            FastAPI routes, schemas, app factory
└── bot/            Telegram bot — handlers, formatters

web/                Static HTML/CSS/JS frontend
docker/             Dockerfile + docker-compose.yml
main.py             Unified entrypoint (API + bot, same event loop)
```

---

## Quick Start — Local

```bash
# 1. Install Ollama (https://ollama.com/)
ollama pull kmamaroziqov/alloma-8b-q4

# 2. Clone and create env file
cp .env.example .env

# 3. Start PostgreSQL in Docker (required for local development)
docker-compose -f docker/docker-compose.yml up -d postgres

# 4. Fill in OLLAMA_BASE_URL, TELEGRAM_BOT_TOKEN, DB credentials in .env
# DB_HOST=localhost
# DB_PORT=5433

# 5. Install dependencies
pip install -r requirements.txt

# 6. Run
python main.py
```

Open **http://localhost:8000** in your browser.

---

## Quick Start — Docker

```bash
# 1. Copy env file
cp .env.example .env
# Edit .env with real values

# 2. Build and start all services
docker compose -f docker/docker-compose.yml up -d --build

# 3. View logs
docker compose -f docker/docker-compose.yml logs -f

# 4. Stop
docker compose -f docker/docker-compose.yml down
```

The stack will spin up:
| Container | Port |
|-----------|------|
| PostgreSQL (pgvector) | 5433 |
| LexAI API + Telegram bot | 8000 |

---

## Environment Variables

Copy `.env.example` → `.env` and fill in:

| Variable | Description |
|----------|-------------|
| `OLLAMA_BASE_URL` | Ollama API endpoint (default: `http://localhost:11434/v1`) |
| `OLLAMA_MODEL` | Model name (default: `kmamaroziqov/alloma-8b-q4`) |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/botfather) |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | Host (`localhost` or `postgres` in Docker) |
| `DB_PORT` | Port (`5433` local, `5432` in Docker) |
| `LOG_LEVEL` | `INFO` or `DEBUG` |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Send a question, get a legal answer |
| `GET` | `/health` | Health check |
| `GET` | `/sessions/{id}/history` | Retrieve conversation history |
| `DELETE` | `/sessions/{id}` | Delete a session |

**Example:**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Konstitutsiyaning 20-moddasi nima?"}'
```

---

## Telegram Bot Commands

| Command | Action |
|---------|--------|
| `/start` | Start a new session |
| `/new` | Reset conversation |
| `/help` | Show help |

---

## Scraping & Data Ingestion

```bash
# Scrape all laws from Lex.uz
python -c "from app.services.scraper_service import ScraperService; ScraperService().scrape_all()"

# Upload to database
python -c "from app.repository.database import DatabaseRepository; DatabaseRepository().upload_data()"
```
