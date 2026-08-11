# Deployment (self-hosted, Docker)

CareConnect runs as two containers — a FastAPI backend and a Next.js
frontend — orchestrated by `docker-compose.yml` at the repo root. This
replaces the earlier Railway (backend) + Vercel (frontend) setup with
self-hosted infrastructure (a DigitalOcean VPS, deployed via Coolify).

This document is generated from the actual `os.environ`/`process.env` reads
in the code, not from memory — see the grep commands in each section if you
need to re-verify it after a future change.

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

```bash
# from the repo root, with .env populated per the tables above
docker compose build
docker compose up -d
```

Coolify: point it at this repo, let it detect `docker-compose.yml`, and set
the same env vars in Coolify's own environment-variable UI (Coolify injects
them the same way `env_file` does locally) rather than committing a real
`.env`.

## Verifying a deploy

```bash
curl -f http://localhost:8000/health          # backend
curl -f http://localhost:3000                  # frontend homepage
```
