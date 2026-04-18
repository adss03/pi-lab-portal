# pi-lab-portal — Claude Configuration

## Project Overview
A Django-based homelab portal for a Raspberry Pi, containerized with Docker and exposed via Tailscale serve. Provides a central login page with access to modular apps (media archive, and future apps).

## Architecture

### Stack
- **Backend**: Django (Python)
- **Database**: PostgreSQL 16, runs in its own container with named volume
- **Media Storage**: Local volume mount for photos/videos (bind mount to NAS or Pi storage path)
- **Container**: Docker Compose — one compose file manages all services
- **Reverse Proxy**: Nginx (in Docker) → Django (gunicorn)
- **Auth**: Django's built-in auth (login required on all non-public routes)
- **Exposed via**: Tailscale serve pointing at Nginx container port

### Services (docker-compose.yml)
| Service | Image | Notes |
|---|---|---|
| `db` | postgres:16-alpine | Named volume `pgdata` |
| `web` | custom Django image | Gunicorn, depends on `db` |
| `nginx` | nginx:alpine | Proxies to `web`, serves media/static |

### App Structure
```
portal/          # Django project root
  apps/
    core/        # Login, dashboard, user management
  static/
  media/         # Served by Nginx, bind-mounted to Pi storage
```

## Conventions
- Python: follow PEP8, no unused imports
- Django apps in `portal/apps/`
- All secrets via environment variables (`.env` file, never committed)
- `requirements.txt` pinned versions
- Migrations committed to repo
- No test stubs unless writing real tests

## Docker
- `docker-compose.yml` at repo root
- `.env.example` committed, `.env` gitignored
- Static files collected to `staticfiles/` volume at build/startup
- Health checks on `db` service before `web` starts

## What NOT to do
- Don't use SQLite
- Don't store binary media in the database
- Don't add comments explaining what code does — only non-obvious WHY comments
- Don't add placeholder/stub apps — implement or leave out

## Baseline Definition of Done
The initial scaffold is complete when:
- `docker compose up` brings all three services healthy
- `http://localhost` (via Nginx) redirects to `/login/`
- A logged-in user reaches the dashboard
- Static files load without 404s
