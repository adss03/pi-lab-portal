# pi-lab-portal — Claude Configuration

## Project Overview
A FastAPI-based homelab portal for a Raspberry Pi, containerized with Docker and exposed via Tailscale serve. Provides a central login page with access to modular apps (SaaS Ideas scraper, and future apps).

## Architecture

### Stack
- **Backend**: FastAPI (Python), Uvicorn ASGI server
- **Database**: PostgreSQL 16, runs in its own container with named volume
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **Templates**: Jinja2 (server-rendered HTML)
- **Auth**: Session-based (Starlette SessionMiddleware, itsdangerous signed cookies)
- **Media Storage**: Local volume mount (bind mount to NAS or Pi storage path)
- **Container**: Docker Compose — one compose file manages all services
- **Reverse Proxy**: Nginx (in Docker) → FastAPI (uvicorn)
- **Exposed via**: Tailscale serve pointing at Nginx container port

### Services (docker-compose.yml)
| Service | Image | Notes |
|---|---|---|
| `db` | postgres:16-alpine | Named volume `pgdata` |
| `web` | custom FastAPI image | Uvicorn single worker, depends on `db` |
| `nginx` | nginx:alpine | Proxies to `web` and serves media |

### App Structure
```
app/
  main.py          # FastAPI app, lifespan, exception handlers
  config.py        # Pydantic settings (from env vars)
  database.py      # SQLModel engine, session dependency, init_db()
  models.py        # User, ScrapeJob, IdeaPost, classify_post(), constants
  auth.py          # require_auth dependency, password hashing
  jobs.py          # Threaded scrape job runner
  templates_config.py  # Jinja2Templates instance + custom filters
  routers/
    core.py        # /login, /logout, / (dashboard)
    saas_ideas.py  # /ideas/ routes
  scrapers/
    reddit.py
    hackernews.py
    indiehackers.py
  static/css/
  templates/
```

### Key Design Decisions
- **No Alembic**: `SQLModel.metadata.create_all()` on startup — fine for homelab
- **Admin user**: Created on startup from `ADMIN_USERNAME`/`ADMIN_PASSWORD` env vars if not present
- **No CSRF**: Homelab behind Tailscale; SessionMiddleware with secure signed cookies
- **Static files**: Served by Uvicorn (`StaticFiles` mount at `/static`); Nginx proxies everything
- **No Django admin**: Use the existing list/filter UI for data browsing

## Conventions
- Python: follow PEP8, no unused imports
- All secrets via environment variables (`.env` file, never committed)
- `requirements.txt` pinned versions
- No test stubs unless writing real tests

## Docker
- `docker-compose.yml` at repo root
- `.env.example` committed, `.env` gitignored
- No collectstatic — static files served directly from `app/static/`
- Health checks on `db` service before `web` starts

## What NOT to do
- Don't use SQLite
- Don't store binary media in the database
- Don't add comments explaining what code does — only non-obvious WHY comments
- Don't add placeholder/stub apps — implement or leave out
- Don't add Alembic unless schema migrations become necessary

## Definition of Done
- `docker compose up` brings all three services healthy
- `http://localhost` (via Nginx) → `/login/`
- A logged-in user reaches the dashboard
- Static files load without 404s
- SaaS ideas list, detail, and scrape all work
