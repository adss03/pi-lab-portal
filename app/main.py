import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.auth import hash_password
from app.config import settings
from app.database import engine, init_db
from app.models import Note, User
from app.routers import core, notes, pi_health

logging.basicConfig(level=logging.INFO)


_SEED_NOTES = [
    Note(
        title="Claude Code: Skills, Hooks, MCP Servers & Plugins",
        tag="devops",
        body="""A reference for tools that improve quality, consistency, reliability, security, and professionalism
of both the pi-lab-portal and day-to-day engineering work at Santok Group.

━━━ SKILLS (slash commands) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Already installed:
  /code-review         — Review current diff for bugs, reuse, efficiency. Use before every PR.
                         Levels: low/medium (fewer, high-confidence findings) / high/max (broad sweep)
                         Flag --fix to apply findings directly. --comment to post as inline PR comments.
  /security-review     — Full security review of all changes on the current branch.
                         Run this before merging anything that touches auth, env vars, or external APIs.
  /pr-review-toolkit   — Suite of specialised review agents:
    :code-reviewer       — Style guide + best practice check
    :code-simplifier     — Simplify and clean up after writing a chunk of code (runs automatically)
    :comment-analyzer    — Checks comments are accurate and not rotting
    :pr-test-analyzer    — Identifies gaps in test coverage (critical — no tests exist yet)
    :silent-failure-hunter — Finds swallowed exceptions and bad fallback logic
    :type-design-analyzer  — Reviews type/model design (useful for SQLModel schemas)
  /verify              — Launches the app and tests a change end-to-end before pushing.
  /run                 — Starts the app for manual testing.
  /fewer-permission-prompts — Scans transcripts and auto-allowlists frequent read-only commands.
  /deep-research       — Multi-source web research with verified citations.
                         Use when evaluating: RunPod vs Vast.ai, Dramatiq vs RQ, Prometheus setup, etc.
  /schedule            — Create scheduled remote agents (cron-style). Useful for:
                         nightly health checks, weekly deploy summaries, automated dependency audits.
  /loop                — Run a prompt on a recurring interval. Use when watching a CI run in progress.
  /update-config       — Configure hooks and settings.json. Required for any automated behaviour.
  /claude-api          — Reference for Claude API — model IDs, pricing, tool use, streaming, MCP.
                         ALWAYS read this before touching any Anthropic/LLM code.

Recommended workflow:
  write code → /code-review (or auto-triggered simplifier) → /security-review → /verify → push → PR

━━━ HOOKS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hooks are shell commands that fire on Claude Code events, configured in settings.json via /update-config.
They run in the harness — Claude cannot substitute them with memory or preferences.

Recommended hooks to set up:

  PreToolUse (Bash, filter on git commit):
    ruff check app/ --fix && ruff check app/
    → Catches and auto-fixes lint violations before any commit lands. Stops CI failures before they happen.

  PreToolUse (Bash, filter on git push):
    docker compose build web
    → Verifies the image still builds locally before the push triggers CI.
    → Saves the ~2 minute CI Docker build round-trip on broken pushes.

  PostToolUse (Edit/Write, filter on *.py files):
    ruff format {file_path}
    → Auto-formats every Python file after Claude edits it. Keeps style consistent without manual intervention.

  Stop (after Claude finishes a task):
    echo "Run /verify before committing if you changed routes or templates."
    → Reminder prompt so end-to-end testing doesn't get skipped.

To add these: use /update-config and describe the behaviour you want.

━━━ MCP SERVERS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Already connected (available in every Claude Code session):

  Notion (claude.ai)
    Read/write pages, databases, create pages, query databases.
    Direct relevance: EAL Holdings case file hub, Santok automation docs, pi-lab-portal learning notes.
    Use: push notes from this app back to Notion, query EAL borrower data, draft automation SOPs.

  n8n (claude.ai)
    Direct integration with N8N workflows.
    HIGH relevance — N8N is the primary automation tool at Santok Group.
    Use: inspect running workflows, trigger executions, debug failures, build new workflows via Claude.

  Linear (claude.ai)
    Issue tracking and project management.
    Use: track pi-lab-portal features/bugs as proper issues rather than ad-hoc notes.
    Could also track Santok automation project backlog formally.

  Slack (claude.ai)
    Read channels, send messages, search.
    Use: post deploy notifications to a #deployments channel after CI completes.
    Could notify on failed jobs or Pi health alerts.

  Atlassian (claude.ai)
    Jira + Confluence.
    Use if Santok adopts Jira for project tracking (currently unclear).

  ticktick (claude.ai)
    Task management with full CRUD.
    Use: personal task tracking for engineering work across Santok and pi-lab-portal.

  Context7 (claude.ai)
    Fetches current library documentation on demand.
    ALWAYS use when working with FastAPI, SQLModel, Docker, GitHub Actions, Tailscale, N8N APIs.
    Prevents using outdated API syntax from training data.

  Microsoft Learn (claude.ai)
    Official Azure/Microsoft documentation.
    Use if Santok workloads move to Azure or if working with Microsoft 365 APIs.

━━━ PLUGINS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Already installed (from settings.json):
  code-review@claude-plugins-official      — /code-review skill
  pr-review-toolkit@claude-plugins-official — /pr-review-toolkit:* suite

These install via the official Anthropic plugins marketplace (github.com/anthropics/claude-plugins-official).
No additional plugins are needed right now — the toolkit suite is comprehensive.

━━━ GAPS IN THE CURRENT PI-LAB-PORTAL SETUP ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

These are things that exist in the design doc and the deploy workflow but are not yet implemented:

  No tests at all
    → /pr-review-toolkit:pr-test-analyzer will identify coverage gaps
    → Add pytest + pytest-asyncio. Start with auth routes and model validation.
    → Add a test job to ci.yml alongside lint and build.

  No health endpoints
    → /healthz (is the process alive?), /readyz (can it serve traffic — checks DB), /version (git commit + build time)
    → Docker Compose health checks currently only test postgres, not the web service itself.

  No structured logging
    → logging.basicConfig(level=INFO) is not enough for production.
    → Add python-json-logger or structlog. Include request_id, route, method, status, duration.

  No type checking in CI
    → ruff checks style but not types.
    → Add mypy or pyright as a CI job. SQLModel has full type support.

  No dependency vulnerability scanning
    → Add pip-audit or safety to ci.yml. Checks pinned requirements.txt against CVE databases.
    → One extra CI step, high value for a public-facing app.

  No secrets scanning
    → Add gitleaks or trufflehog to ci.yml. Catches accidentally committed API keys before they go public.

  No production approval gate
    → deploy.yml deploys to production automatically on merge to main.
    → Add a GitHub Environment protection rule requiring manual approval before production deploy.
    → This is one settings change in GitHub, not a code change.

  Single-worker Uvicorn
    → CMD in Dockerfile runs --workers 1. Fine for homelab but worth knowing.
    → For higher load: switch to gunicorn with uvicorn workers, or increase workers.

  No multi-stage Docker build
    → Current Dockerfile copies all source including dev files.
    → Multi-stage: builder installs deps, final image copies only what's needed. Smaller image, faster deploys.

━━━ RELEVANCE TO SANTOK GROUP WORK ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

As sole AI/automation engineer, the highest-value tools from this list for day-to-day work:

  /security-review    — Any automation that handles financial data (EAL underwriting, Santok ERP)
                        should be security reviewed. You are the only reviewer.

  /deep-research      — When evaluating tools (Notion vs alternatives, RunPod for GPU jobs, etc.)
                        use this for multi-source, fact-checked comparison reports.

  n8n MCP             — Direct Claude Code ↔ N8N integration. Debug, build, and inspect
                        N8N workflows without leaving the terminal.

  Notion MCP          — Already connected. EAL Holdings case file hub is in Notion.
                        Claude can read borrower case files and help draft agent prompts.

  /schedule           — Set up a nightly Claude agent that checks pi-lab-portal health,
                        summarises any errors, and posts to Slack or Notion automatically.

  Context7            — Critical when building N8N HTTP Request nodes or FastAPI integrations.
                        Always fetch current docs before writing API integration code.""",
    ),
    Note(
        title="CI/CD Pipeline Overview",
        tag="ci-cd",
        body="""Two GitHub Actions workflows run automatically.

ci.yml — runs on every push and pull request. Two parallel jobs:
  - Lint: pip install ruff && ruff check app/
  - Docker build: cp .env.example .env && docker compose build web
Failing either blocks a merge.

deploy.yml — runs on push to main/develop, or manually via workflow_dispatch.
Steps:
  1. Joins the Pi's Tailscale network using OAuth credentials (secrets: TS_OAUTH_CLIENT_ID, TS_OAUTH_SECRET)
  2. Writes SSH key from secrets to /tmp/deploy_key
  3. SSHes into the Pi and runs:
       git pull
       docker compose [args] --env-file [file] up -d --build --remove-orphans
       docker image prune -f

Branch → environment:
  main    → production  (docker-compose.yml + .env)
  develop → staging     (docker-compose.yml + docker-compose.staging.yml + .env.staging)

Pi host, user, and deploy path come from GitHub Actions vars.*
SSH key and Tailscale credentials come from GitHub Actions secrets.*""",
    ),
    Note(
        title="Ruff: What the Lint Step Actually Does",
        tag="ci-cd",
        body="""ruff check app/ runs the Ruff linter over the entire app/ directory without executing any code.

It catches:
  - Unused imports (F401)
  - Undefined variables (F821)
  - Style violations (wrong quote style, trailing whitespace)
  - Common bug patterns (bare except, mutable default arguments)

If any violation is found, ruff exits non-zero and the CI job fails. The error message includes the file path, line number, and rule code so you know exactly what to fix.

Ruff is written in Rust and runs in milliseconds — it is the fastest check in CI. It runs as a separate parallel job from the Docker build, so neither blocks the other.

No test runner is currently configured. Ruff only checks code quality, not correctness.""",
    ),
    Note(
        title="Secrets Management: Levels of Maturity",
        tag="devops",
        body="""Level 1 — .env files
Store secrets in a .env file on the server, gitignored. Fine for homelab.
Risk: accidentally committing it, or leaving it world-readable on disk.
The .env.example file (committed) contains only placeholder values like SECRET_KEY=changeme.

Level 2 — GitHub Actions Secrets
CI credentials (SSH keys, Tailscale OAuth) stored in GitHub Secrets, injected at runtime.
Encrypted at rest, never exposed in logs.
This is what deploy.yml uses for PI_SSH_KEY, TS_OAUTH_CLIENT_ID, TS_OAUTH_SECRET.

Level 3 — HashiCorp Vault / AWS Secrets Manager / GCP Secret Manager
Secrets stored centrally with automatic rotation, fine-grained access control, and full audit logs.
Apps fetch them at runtime rather than from a file on disk.

Level 4 — Kubernetes Secrets + external-secrets operator
Pulls from a secrets manager into k8s at deploy time.
The app reads env vars normally; the infrastructure handles the fetch and rotation.

For this Pi homelab:
Level 1 on the Pi for runtime config (.env gitignored) +
Level 2 in GitHub for deploy credentials
is the right balance. The threat model does not justify more complexity.""",
    ),
    Note(
        title="Staging vs Production: How the Setup Works",
        tag="devops",
        body="""Both environments run on the same Pi, using Docker Compose override files.

Production:
  docker compose -f docker-compose.yml --env-file .env up -d --build

Staging:
  docker compose -f docker-compose.yml -f docker-compose.staging.yml --env-file .env.staging up -d --build

The override file (docker-compose.staging.yml) can change port numbers, resource limits, or image tags.
Everything not overridden is inherited from the base compose file.

deploy.yml checks github.ref_name to pick the stack. push to main = prod. push to develop = staging.

What staging should be:
  Same OS, same Docker setup, same data shape (anonymised where needed).
  Different: credentials, ports, possibly resource caps.
  If staging differs too much from prod, environment-specific bugs survive into production.

Correct workflow:
  feature branch → open PR against develop
  merge to develop → staging deploy fires automatically
  verify in staging over Tailscale
  merge develop → main → production deploy fires""",
    ),
    Note(
        title="Docker Cleanup: --remove-orphans and image prune",
        tag="devops",
        body="""These two cleanup operations run on every deploy. They clean different layers.

--remove-orphans (flag for docker compose up)
Stops and removes containers whose service name no longer exists in docker-compose.yml.
Example: you rename the service from 'nginx' to 'proxy'. Without --remove-orphans, the old nginx container keeps running silently alongside the new proxy container — two containers serving the same role, one invisible.
With --remove-orphans, the old container is stopped and removed automatically.

docker image prune -f
Deletes all dangling images: untagged images not referenced by any running container.
Every --build creates a new image for the web service. The previous image becomes untagged and sits on disk.
On a Raspberry Pi with limited storage, this adds up quickly across many deploys.
The -f flag skips the confirmation prompt (required in non-interactive CI/SSH context).

Both are good practice on every push, especially on resource-constrained hardware like a Pi.

Mental model:
  containers  ←  --remove-orphans cleans these up
  images      ←  docker image prune cleans these up""",
    ),
    Note(
        title="Branch-to-Environment Mapping: Practical Example",
        tag="ci-cd",
        body="""The deploy workflow uses github.ref_name (the branch name that triggered the push) to decide which environment to deploy. No manual config required per deploy.

Full walkthrough:

1. You push feature/dark-mode and open a PR against develop.
   CI runs (lint + build). Deploy does NOT run — feature/dark-mode is not in on.push.branches.

2. You merge the PR into develop.
   Deploy fires with github.ref_name = develop.
   Pi receives: docker compose -f docker-compose.yml -f docker-compose.staging.yml --env-file .env.staging up -d --build
   Staging updates.

3. You test the feature at the staging address over Tailscale. Looks good.

4. You open a PR from develop into main and merge it.
   Deploy fires with github.ref_name = main.
   Pi receives: docker compose -f docker-compose.yml --env-file .env up -d --build
   Production updates.

The branch name is the sole input to the environment decision.
Feature branches never deploy anywhere automatically.""",
    ),
    Note(
        title="GitHub Actions Concurrency: Queueing Deploys",
        tag="ci-cd",
        body="""The concurrency block in deploy.yml:

  concurrency:
    group: deploy-${{ github.ref_name }}
    cancel-in-progress: false

This is counterintuitively named. The feature manages concurrency by preventing it — serialising overlapping runs into a queue.

group: deploy-${{ github.ref_name }}
Scoped per branch. Production (deploy-main) and staging (deploy-develop) are independent groups.
They can run at the same time as each other — they just cannot overlap within the same branch.

cancel-in-progress: false
When a second run arrives while the first is still running, the second WAITS rather than cancelling the first.
This is the safe choice for deployments. Killing a half-finished docker compose up can leave the stack mid-transition: some containers on the new image, some on the old, some not running at all.

cancel-in-progress: true is fine for:
  - Preview builds (fast, idempotent, no shared state)
  - Static site generation
NOT for deployments.

Most common real trigger:
  You push to main, realise you forgot something, push again 30 seconds later.
  Without this: both deploys race each other on the Pi, potentially corrupting the stack.
  With this: the second waits for the first to finish cleanly, then runs.""",
    ),
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(engine) as session:
        existing = session.exec(
            select(User).where(User.username == settings.admin_username)
        ).first()
        if not existing:
            session.add(User(
                username=settings.admin_username,
                password_hash=hash_password(settings.admin_password),
            ))
            session.commit()

        if not session.exec(select(Note)).first():
            for note in _SEED_NOTES:
                session.add(note)
            session.commit()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=86400 * 30)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(core.router)
app.include_router(pi_health.router)
app.include_router(notes.router)


@app.exception_handler(HTTPException)
async def auth_redirect_handler(request: Request, exc: HTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login/", status_code=302)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
