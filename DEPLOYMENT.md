# Deployment

## Status: Railway + Vercel is the live deployment. Docker/VPS is prepared, not active.

**CareConnect currently runs on Railway (backend) + Vercel (frontend) —
that is the real, live deployment as of this writing.** The Docker/VPS/
Coolify material in this document (images, `docker-compose*.yml`,
`docker-publish.sh`) was built and verified (both images build clean, boot
clean, pass a request round-trip) but **deliberately not deployed** — it's
parked for a later self-hosted VPS move, expected to matter once the ERP
products need it, not something currently serving traffic. If you're
reading this in a future session trying to figure out "which deployment is
actually live," it's Railway/Vercel; treat any Docker/VPS section below as
documentation-in-waiting until this status line is updated to say
otherwise.

The two setups don't conflict — see "Coexistence with Railway/Vercel"
below for exactly why nothing in the Docker work could have broken the
live deployment.

## Current deployment: Railway + Vercel

- **Backend (Railway)**: `railway.toml` at the repo root pins
  `builder = "NIXPACKS"` explicitly — Railway builds from source via
  Nixpacks (`pip install -r requirements.txt`, no Dockerfile involved),
  and runs `uvicorn core.main:app --host 0.0.0.0 --port $PORT` ($PORT is
  Railway's own assigned port, not the `8000` the Docker image hardcodes).
  Health check: `/health`. Env vars are set in Railway's own dashboard
  (Project → Variables) — see the tables further down for the full list;
  they're read identically regardless of which platform runs the process,
  since they're plain `os.environ` reads in `core/main.py`/etc., nothing
  Railway-specific.
- **Frontend (Vercel)**: no `vercel.json` — Vercel auto-detects Next.js and
  runs its own build/output pipeline (`npm run build`, its own serverless
  function packaging), independent of `frontend/Dockerfile` or
  `next.config.ts`'s `output: "standalone"` (Vercel does its own file
  tracing and ignores that setting — it exists only for the Docker image's
  benefit). `NEXT_PUBLIC_API_BASE_URL` is set as a Vercel **Environment
  Variable** and, because Next.js inlines `NEXT_PUBLIC_*` values at build
  time, changing it requires a Vercel **redeploy** to take effect, not
  just a dashboard save (this project hit exactly this gotcha once
  already — Spec.md Section 0).

## Coexistence with Railway/Vercel — real incident, corrected below

**This was wrong once already — corrected, not just theorized.** Adding
the root `Dockerfile` for the VPS path did in fact coincide with a real
Railway production outage: `startCommand`'s `--port $PORT` was deployed
literally (uvicorn errored on `'$PORT' is not a valid integer`), meaning
whatever ran the container did **not** go through a shell to expand it.
`railway.toml`'s `builder = "NIXPACKS"` pin was assumed sufficient to keep
Railway off the new Dockerfile — that assumption was stated here with more
confidence than it deserved, without ever being verified against a live
Railway deploy. Root cause not confirmed with certainty (Railway's
dashboard-level builder setting can override `railway.toml`, or Railway's
Docker-builder path may just not shell-wrap `startCommand` the way Nixpacks
does — either is consistent with the symptom); fixed defensively either
way by making `startCommand` explicitly invoke a shell itself
(`sh -c "uvicorn ... --port $PORT"`), which expands `$PORT` correctly
regardless of which builder actually runs it.

**Takeaway for next time**: don't assert a build-tool config setting
prevents a platform behavior without a live deploy confirming it — the
"builder pin" claim above was exactly this mistake.

- `railway.toml` pins `NIXPACKS` as the builder, intended to keep Railway
  off the new root `Dockerfile` — **not fully verified to hold in
  practice**, see the incident above. `startCommand` is now shell-wrapped
  as a defensive fix that works regardless.
- `frontend/next.config.ts`'s `output: "standalone"` only affects `next
  build`'s output layout on disk (an extra `.next/standalone` folder for
  the Docker image to copy) — Vercel's own build pipeline doesn't consume
  that folder and isn't affected by the setting being present.
- No GitHub Actions workflow (`.github/workflows/*.yml`) references Docker,
  a registry, or either compose file — CI still just runs the Python test
  suite, unrelated to either deployment path.
- Nothing in `core/main.py`'s CORS/`FRONTEND_ORIGIN` handling or the
  Section 15 OAuth work (`user_auth.py`, `SessionMiddleware`) is
  Docker-specific — same `os.environ` reads either way, verified by
  reading through `core/main.py` fresh rather than assuming from memory.

This document is generated from the actual `os.environ`/`process.env` reads
in the code, not from memory — see the grep commands in each section if you
need to re-verify it after a future change.

---

**Everything below this line describes the Docker/VPS/Coolify path — built
and verified, not currently deployed.** Skip to here only once the actual
move off Railway/Vercel is decided.

## Images

- **`Dockerfile`** (repo root) — backend. `python:3.12-slim` (matches
  `.github/workflows/tests.yml`'s pinned CI version), single stage —
  `pip install -r requirements.txt`, copy the app, run
  `uvicorn core.main:app --host 0.0.0.0 --port 8000` (no `--reload`, that's
  dev-only). No build stage: every dependency this project actually needs
  compiled (`psycopg2-binary`, `cryptography` via Authlib) ships a prebuilt
  wheel for this base image already, so there's nothing a multi-stage build
  would trim.
- **`frontend/Dockerfile`** — frontend. `node:22-alpine` (matches this
  repo's own dev/lockfile Node version; Next's own `package.json` requires
  `>=20.9.0`). Three stages (`deps` → `builder` → `runner`) — genuinely
  worth it here, unlike the backend: `next build`'s toolchain and
  devDependencies never belong in the runtime image. Uses Next's
  `output: "standalone"` (`frontend/next.config.ts`) so the final image
  ships only the traced runtime files, not the full `node_modules` tree
  `next start` would otherwise require.

## Registry: Docker Hub (`daaprime`)

Images publish to:
```
daaprime/careconnect-backend
daaprime/careconnect-frontend
```

No registry hostname prefix needed in image references — `docker.io` is
the Docker CLI's default registry, so `daaprime/careconnect-backend` and
`docker.io/daaprime/careconnect-backend` refer to the same image.

**Authenticating**: use a Docker Hub **Access Token**, not your real account
password — Docker Hub → Account Settings → Security → New Access Token
(scope: Read & Write for push from your dev machine; Read-only is enough
for the VPS's pull). Then:

```bash
docker login -u daaprime
# paste the Access Token as the password when prompted
```

By default a newly pushed Docker Hub repository under a personal namespace
is **private** on the free plan up to a small number of private repos —
confirm `daaprime/careconnect-backend` and `daaprime/careconnect-frontend`
are set to the visibility you want in Docker Hub's own repository settings;
if private, the VPS's `docker login` above is what authorizes it to pull.

## Publishing images (`docker-publish.sh`)

Builds and pushes both images with two tags each — a version tag
(`git describe --tags --always --dirty`, e.g. a real semver tag if you've
made one, otherwise the short commit hash) and `latest`:

```bash
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com ./docker-publish.sh
```

`NEXT_PUBLIC_API_BASE_URL` is required (the script refuses to run without
it, on purpose — see "Frontend" below for why a missing/wrong value here
is easy to get wrong silently). Use `--no-push` to build and tag without
pushing, e.g. to sanity-check a build before publishing it.

The version tag is what actually matters for a real rollout — it's how you
roll back to a specific known-good build; `latest` always means "whatever
was pushed most recently," which can't express "go back to what was
running before." Pin `IMAGE_TAG` (below) to a real version tag for
anything beyond a first deploy.

## Database: kept on Neon, not self-hosted — flagging the decision

**Recommendation: keep the existing managed Neon Postgres**, just pointed
at from the VPS via `DATABASE_URL`, rather than also self-hosting Postgres
on the same box. Reasons:
- It's already working in production, with real data (hospital #1, DaaPrime).
- `db/connection.py`'s reconnect-on-idle-disconnect logic was written
  specifically to handle Neon's serverless behavior (it closes idle
  connections server-side) — self-hosting removes the problem that code
  exists to solve, but the code doesn't need to change either way, so
  there's no cleanup payoff from switching.
- Self-hosting Postgres on the same VPS as the app adds a real operational
  burden (backups, disk monitoring, version upgrades) the app doesn't
  currently carry, for a database that's small enough Neon's free/low tier
  already handles it.

If you want to self-host instead, `docker-compose.dev-db.yml` already has a
working `postgres:16-alpine` service definition (the same image the test
suite provisions via `testcontainers`) to copy from — move it into
`docker-compose.yml`, add a named volume, and point `DATABASE_URL` at it.
Not done here since it's a real infrastructure decision, not a default to
pick silently.

## Reverse proxy: not included, on the assumption this runs behind Coolify

Coolify runs its own reverse proxy (Traefik) and terminates TLS for
whatever it manages — `docker-compose.yml` deliberately has no Nginx/Caddy
service, since adding one would just be a second, redundant proxy hop.

**If you're deploying this compose file without Coolify** (bare VPS, no
PaaS layer), you'll need to add a reverse-proxy service yourself for
HTTPS — say so and it can be added; it changes the shape of the compose
file (both app services would move to an internal-only network, with only
the proxy publishing ports 80/443).

## Environment variables

### Backend (read via `os.environ` — see `Dockerfile`'s `env_file: .env`)

**Required — the app won't start / auth won't work at all without these:**

| Variable | Read in | Purpose |
|---|---|---|
| `DATABASE_URL` | `db/connection.py` | Postgres connection string. No default — raises on startup if missing. |
| `WHATSAPP_VERIFY_TOKEN` | `core/main.py` | Meta webhook verification challenge. No default — raises `KeyError` on startup if missing. |

**Required for real (non-empty) security — each of these defaults to `""`,
which means "this feature is permanently disabled" rather than "insecure
default," but you need every one of them set for the app to actually work
as intended:**

| Variable | Read in | Purpose |
|---|---|---|
| `ADMIN_SECRET` | `admin/onboarding.py` | Gates creating a new hospital via the onboarding wizard. Empty = onboarding can never succeed (compares `bool(ADMIN_SECRET) and hmac.compare_digest(...)`, so an empty secret never matches anything, including another empty string). |
| `TENANTS_ADMIN_SECRET` | `admin/tenants_api.py` | Gates `/admin/tenants`, `/admin/edit-tenant` — deliberately a *different* secret from `ADMIN_SECRET`, so a leaked onboarding secret can't also expose every tenant's stored credentials. |
| `PORTAL_SECRET` | `portal.py`, also `core/storage.py` | Signs the hospital-staff portal's session token (`portal.py`); also doubles as `core/storage.py`'s fallback HMAC secret for locally-stored patient documents when `S3_BUCKET` isn't set. |
| `AUTH_SECRET` | `user_auth.py`, `core/main.py` | Signs the Google-OAuth user session token (separate from `PORTAL_SECRET` on purpose — see `user_auth.py`'s module docstring); also used as the secret for Starlette's `SessionMiddleware`, which only holds the OAuth handshake's short-lived state/nonce. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | `user_auth.py` | Google OAuth app credentials (Section 15). Get these from Google Cloud Console — see below for the exact redirect URIs to register. |

**Optional — real defaults or graceful fallback, but you'll likely want
these set in production:**

| Variable | Read in | Purpose | Default / fallback |
|---|---|---|---|
| `FRONTEND_ORIGIN` | `core/main.py`, `user_auth.py` | Added to the CORS allow-list; also where `/auth/google/callback` redirects the browser back to after sign-in. | `core/main.py` only adds it to CORS if set at all (always includes `localhost:3000`); `user_auth.py` defaults to `http://localhost:3000` if unset. **Set this to your real deployed frontend URL** (e.g. `https://app.yourdomain.com`) or Google sign-in will redirect users back to `localhost`. |
| `INTERNAL_SECRET` | `core/main.py` | Gates `/internal/send-reminders` and `/internal/top-up-slots` (checked against an `X-Internal-Secret` header) — whatever cron/scheduler calls these needs to send it. | `""` (both routes 403 on every request until set) |
| `REDIS_URL` | `core/history.py`, `core/main.py`, `core/rate_limit.py`, `modules/booking/calendar.py` | Session store, per-message locking, and rate-limiting backend. | Falls back to in-memory automatically — **fine for a single container, NOT safe if you ever run more than one backend replica** (each process would have its own separate in-memory state). |

**Optional — patient document storage (`core/storage.py`), only relevant if
the `booking`/patient-records features are used:**

| Variable | Purpose |
|---|---|
| `S3_BUCKET` | Enables real object storage (AWS S3 or any S3-compatible provider). Omit and uploads fall back to local disk. |
| `S3_REGION` | Passed to boto3; optional depending on provider. |
| `S3_ENDPOINT_URL` | Set for Cloudflare R2/Backblaze B2/etc.; leave unset for real AWS S3. |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | Credentials for the bucket. |
| `LOCAL_STORAGE_DIR` | Local-disk fallback directory when `S3_BUCKET` isn't set. Default `local_storage`. **On a container deployment this directory is ephemeral unless you mount a volume at it** — worth setting `S3_BUCKET` for anything beyond a quick smoke test, since a redeploy would otherwise silently lose every previously uploaded patient document. |

**Optional — first-run seeding only** (`db/init_db.py` uses these to create
a starter hospital row *if the database is completely empty*; irrelevant on
every deploy after the first, and irrelevant at all if you onboard hospitals
through the wizard instead):

`HOSPITAL_NAME`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`

**Not required for deployment** — `GOOGLE_SERVICE_ACCOUNT_JSON` /
`GOOGLE_CALENDAR_ID` / `GOOGLE_CALENDAR_OWNER_EMAIL` are read by
`modules/booking/calendar.py`, a legacy module from before this project's
AI/calendar features were stripped (Spec.md Section 0, Phase 0) — it's not
imported by `core/main.py` or reachable from the running app at all. Safe
to leave unset.

### Frontend (`NEXT_PUBLIC_*`, read via `process.env` — inlined at **build**
time, not read at container start)

| Variable | Read in | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `lib/api.ts`, `lib/adminAuth.ts`, `lib/userAuth.ts`, `lib/portalAuth.ts`, `components/admin/AdminSecretGate.tsx`, `app/portal/login/page.tsx` | The backend's **publicly reachable** URL (e.g. `https://api.yourdomain.com`) — this is what a user's browser calls directly, so it must NOT be the Docker Compose service name (`http://backend:8000`), which only resolves inside the compose network. |

Because Next.js bakes `NEXT_PUBLIC_*` values into the client JS bundle at
**build** time, this is passed as a Docker build ARG
(`docker-compose.yml`'s `frontend.build.args`), not a runtime `environment:`
entry — setting it after the image is built has no effect, the same gotcha
this project already hit once on Vercel (a scheme-less URL baked into a
build needed a full rebuild to fix, not just a redeploy).

## `.env` file

`docker-compose.yml`'s `backend` service reads `env_file: .env` — put every
backend variable above into a single `.env` at the repo root (same file
local dev already uses; **never commit it** — see `.gitignore`). Docker
Compose also auto-loads this same file for `${VAR}` substitution inside
`docker-compose.yml` itself, which is how `NEXT_PUBLIC_API_BASE_URL` reaches
the frontend build — so that variable needs to be in this same `.env` too,
even though the frontend container never reads it at runtime.

Naming note: the feature request that prompted this doc named the portal
session secret `PORTAL_SESSION_SECRET` — the actual variable read by the
code is `PORTAL_SECRET` (see `portal.py`). Use `PORTAL_SECRET`; the table
above matches the code, not the request.

## Google OAuth redirect URIs (Section 15)

When registering/updating the Google Cloud Console OAuth client for the new
production URL, the authorized redirect URI must be exactly:

```
https://<your-backend-domain>/auth/google/callback
```

and the authorized JavaScript origin should include your frontend's real
domain (`https://<your-frontend-domain>`).

## Deploying

Two supported paths — pick one, don't mix them on the same VPS:

### Option A — manual image build + push + pull (this project's current approach)

No Coolify auto-build; images are built on your dev machine, pushed to
Docker Hub, and pulled on the VPS. Uses `docker-compose.prod.yml` (pulls
pre-built images — separate from the root `docker-compose.yml`, which
builds from source and is meant for Option B or local smoke-testing).

**On your dev machine**, after `docker login -u daaprime` (see above):
```bash
NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com ./docker-publish.sh
```

**On the VPS**, once (create `.env` with every backend variable from the
table above — this is the file the containers actually read; see the "env
vars on the VPS" note below):
```bash
docker login -u daaprime   # Docker Hub, Read-only Access Token is enough here
```

**On the VPS**, every deploy:
```bash
IMAGE_TAG=latest docker compose -f docker-compose.prod.yml pull
IMAGE_TAG=latest docker compose -f docker-compose.prod.yml up -d
```
(swap `latest` for a specific version tag once you're pinning releases —
see `docker-publish.sh`'s printed output for the exact tag after each
publish)

**Container names** are fixed (`careconnect-backend`, `careconnect-frontend`
— set via `container_name` in `docker-compose.prod.yml`) specifically so
day-to-day operations don't need to be looked up:
```bash
docker logs -f careconnect-backend
docker restart careconnect-backend
docker stop careconnect-backend careconnect-frontend
```

**Env vars on the VPS**: there's no Coolify dashboard injecting them here —
`docker-compose.prod.yml`'s `backend` service reads `env_file: .env`, so a
real `.env` (every backend variable from the tables above, populated with
real production values) must exist in the same directory as
`docker-compose.prod.yml` on the VPS. It is never built into the image and
never committed — copy it there directly (`scp`) or manage it with
whatever secrets tooling you prefer; either way it needs to exist on disk
before the first `up`. If you'd rather run containers directly instead of
through Compose, the equivalent is:
```bash
docker run -d --name careconnect-backend --restart unless-stopped \
  -p 8000:8000 --env-file .env \
  daaprime/careconnect-backend:latest

docker run -d --name careconnect-frontend --restart unless-stopped \
  -p 3000:3000 \
  daaprime/careconnect-frontend:latest
```
`--restart unless-stopped` on both is what survives a VPS reboot — without
it, containers stay stopped after the host restarts until manually started
again. `docker-compose.prod.yml` already sets this per-service, so it's
automatic when using Compose instead of raw `docker run`.

### Option B — Coolify (auto-build from this repo)

Point Coolify at this repo, let it detect the root `docker-compose.yml`
(the build-from-source one), and set the same env vars in Coolify's own
environment-variable UI (Coolify injects them the same way `env_file` does
locally) rather than committing a real `.env`. Coolify's Traefik handles
the reverse proxy/TLS itself in this path — the Nginx/Certbot section below
is specifically for Option A, which has no such thing in front of it.

## Reverse proxy + HTTPS (Option A only — Nginx + Certbot)

Option A's containers each publish a plain HTTP port (`8000`, `3000`) with
nothing terminating TLS in front of them — unlike Option B, where Coolify's
Traefik does this automatically. On a bare VPS, put Nginx in front of both
and use Certbot for free Let's Encrypt certificates, one subdomain per
service (e.g. `api.yourdomain.com` → backend, `app.yourdomain.com` →
frontend) rather than path-based routing, since the frontend's own
`NEXT_PUBLIC_API_BASE_URL` build already expects the backend on its own
origin.

Install (Ubuntu/Debian, the common DigitalOcean base image):
```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
```

Two server blocks, `/etc/nginx/sites-available/careconnect`:
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name app.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/careconnect /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# issues certs for both server_names and rewrites the config above to
# redirect HTTP -> HTTPS automatically
sudo certbot --nginx -d api.yourdomain.com -d app.yourdomain.com

# certbot installs a systemd timer/cron job for renewal automatically;
# confirm it with a dry run
sudo certbot renew --dry-run
```

Point both subdomains' DNS `A` records at the VPS's IP before running
`certbot --nginx` — it validates domain ownership over HTTP on port 80,
which needs to already resolve correctly.

Once this is up: `DATABASE_URL`... no — **`FRONTEND_ORIGIN`** in the
backend's `.env` should be `https://app.yourdomain.com` (so CORS and the
Google OAuth post-sign-in redirect both point at the real HTTPS frontend
origin, not `localhost`), and `NEXT_PUBLIC_API_BASE_URL` at publish time
should be `https://api.yourdomain.com` — both are the **public HTTPS
subdomain**, not the container's internal `8000`/`3000` port directly.

## Verifying a deploy

```bash
curl -f http://localhost:8000/health          # backend, from on the VPS
curl -f http://localhost:3000                  # frontend homepage, from on the VPS
curl -f https://api.yourdomain.com/health      # backend, through Nginx/TLS
curl -f https://app.yourdomain.com             # frontend, through Nginx/TLS
```
