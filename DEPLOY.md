# Deployment Setup

## Overview

| Branch    | Environment | URL (tailnet)              | Port |
|-----------|-------------|----------------------------|------|
| `main`    | production  | `https://<pi-hostname>`    | 80   |
| `develop` | staging     | `http://<pi-hostname>:8081` | 8081 |

CI runs on every push/PR. Deploys only trigger on `main` and `develop`.

---

## One-time Pi Setup

### 1. Clone the repo
```bash
git clone https://github.com/<you>/pi-lab-portal.git ~/pi-lab-portal
cd ~/pi-lab-portal
```

### 2. Create env files
```bash
cp .env.example .env
# edit .env with real values

cp .env.staging.example .env.staging
# edit .env.staging with staging values (different passwords, DB name, etc.)
```

### 3. Create a deploy SSH key (on your local machine)
```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/pi_deploy_key -N ""
```

Copy the public key to the Pi:
```bash
ssh-copy-id -i ~/.ssh/pi_deploy_key.pub <pi-user>@<pi-hostname>
```

---

## GitHub Configuration

### Tailscale OAuth Client

1. Go to [admin.tailscale.com → Settings → OAuth clients](https://login.tailscale.com/admin/settings/oauth)
2. Create a client with **Devices → Core → Write** scope and tag `tag:ci`
3. Add the ACL tag to your Tailscale policy:
   ```json
   "tagOwners": {
     "tag:ci": ["autogroup:admin"]
   }
   ```

### GitHub Environments

Create two environments in **Settings → Environments**: `production` and `staging`.

#### Secrets (per environment)
| Secret             | Value                                      |
|--------------------|--------------------------------------------|
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID                |
| `TS_OAUTH_SECRET`    | Tailscale OAuth client secret            |
| `PI_SSH_KEY`         | Contents of `~/.ssh/pi_deploy_key` (private key) |

#### Variables (per environment)
| Variable          | Production              | Staging                 |
|-------------------|-------------------------|-------------------------|
| `PI_HOST`         | Pi's Tailscale hostname | Pi's Tailscale hostname |
| `PI_USER`         | `adam` (or your user)   | `adam`                  |
| `PI_DEPLOY_PATH`  | `/home/adam/pi-lab-portal` | `/home/adam/pi-lab-portal` |

---

## Local Development

```bash
# Start with hot reload, no nginx, port 8000
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# App at http://localhost:8000
```

## Workflows

| Workflow     | Trigger                     | Jobs                     |
|--------------|-----------------------------|--------------------------|
| `ci.yml`     | All pushes + PRs            | Lint (ruff), Docker build |
| `deploy.yml` | Push to `main` or `develop` | Tailscale join → SSH → `git pull` → `docker compose up` |
