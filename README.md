<h1 align="center">DAAP CareConnect</h1>

**A WhatsApp appointment-booking receptionist for hospitals and clinics — menu-driven, multi-tenant, self-serve.**

A hospital's patients book, reschedule, cancel, and get reminders entirely inside WhatsApp — no app to install. Staff manage everything (doctors, schedules, bookings, patient records, and the bot's own behavior) from a web portal. New hospitals onboard themselves through a guided wizard; nobody edits config files or touches code to add a tenant.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![Tests](https://github.com/PratikGautam-dev/whatsapp-ai-receptionist/actions/workflows/tests.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

| Capability                    | How                                                                                                                                                                                                                                                        |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Menu-driven booking**       | Department → doctor → date → time → patient name → confirm, entirely via WhatsApp interactive lists/buttons — no LLM in the loop, so it's deterministic and free per conversation                                                                          |
| **Reschedule & cancel**       | Same double-booking-safe path real bookings use, patient-initiated from WhatsApp                                                                                                                                                                           |
| **English / Hindi**           | Session-level language picker; a hospital can also set a default language or skip the picker entirely for a single-language deployment                                                                                                                     |
| **Reminders**                 | WhatsApp reminders at hospital-configurable offsets before an appointment, triggered by an external cron hitting `/internal/send-reminders`                                                                                                                |
| **FAQ bot**                   | A separate lightweight flow for hospital-authored Q&A, independent of the booking state machine                                                                                                                                                            |
| **Human handoff**             | A patient can escalate to a real person; staff see and reply to the queue from the portal                                                                                                                                                                  |
| **Multi-tenant from day one** | Every table, session, and connector call is scoped by `hospital_id` — one deployment serves many hospitals, each with its own WhatsApp number, credentials, and settings                                                                                   |
| **Self-serve onboarding**     | A guided wizard walks a new hospital through Meta setup, WhatsApp credentials, departments/doctors, and feature selection — no code changes, no manual DB edits                                                                                            |
| **Self-serve customization**  | Hospitals control their own menu labels, closing message, business-hours text, default language, and session timeout from `/portal/settings`                                                                                                               |
| **Staff portal**              | Dashboard, appointments, doctors/schedules (breaks, quotas, leave), patient records (visit history, notes, document upload sent straight to the patient's WhatsApp chat), and the message-handoff inbox                                                    |
| **Resilient state**           | Redis-backed session/history/rate-limiting with an automatic in-memory fallback — runs with zero extra infrastructure locally                                                                                                                              |
| **Tiered data access**        | A fixed connector interface (`connectors.py`) abstracts "where booking data lives" — Tier 1 (this app's own Postgres) is fully built; Tiers 2/3 (a hospital's existing system) are a defined extension point, not built speculatively ahead of a real need |

**Deliberately not here:** no AI/LLM anywhere in the booking flow (a fixed, auditable state machine instead — see [Spec.md](Spec.md) for the reasoning), no payment collection over WhatsApp, no Google Calendar dependency (appointments live in this app's own database).

---

## How it works

```
Patient's WhatsApp message
        │
        ▼
┌────────────────────┐
│  FastAPI webhook    │  webhook/routes.py — validates the per-hospital HMAC signature,
│  (webhook/)         │  resolves which hospital owns this phone_number_id
└─────────┬───────────┘
          │
          ▼
┌────────────────────┐
│   flows/router.py    │  the feature-toggle router: owns the top-level menu,
│                     │  language selection, and reset-keyword handling
└─────────┬───────────┘
          │
   ┌──────┴───────┬─────────────┐
   ▼               ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│ flows/   │  │ flows/   │  │ view/cancel/ │
│ booking/ │  │ faq.py   │  │ handoff, etc │
└────┬─────┘  └────┬─────┘  └──────┬───────┘
     │             │                │
     └─────────────┼────────────────┘
                    ▼
          ┌───────────────────┐
          │  connectors/        │  Tier 1/2/3 abstraction
          └─────────┬──────────┘
                     ▼
          ┌───────────────────┐
          │  db/repositories/   │  Postgres (Neon in production)
          └───────────────────┘

          Confirmation (with a generated reference ID) via WhatsApp
```

The **staff portal** is a separate path: the Next.js frontend (`frontend/`) talks to `portal_api.py`'s JSON API, which reads/writes the exact same Postgres tables and goes through the exact same `connectors/` booking path a WhatsApp patient uses — a staff-created booking and a patient-created booking are indistinguishable to the double-booking/quota logic.

---

## Design principles

- **No LLM in the booking path.** Every state sends a fixed WhatsApp list/button message with a closed set of options; a reply is either a valid tap or free text, which re-prompts. Deterministic, auditable, and free per conversation — see [Spec.md](Spec.md)'s non-goals for the full reasoning.
- **Hospital-configurable, not code-configurable.** Onboarding a new tenant, changing a doctor's schedule, or renaming a menu item never requires a code change or a manual database edit — it's a form.
- **Every query is tenant-scoped.** `hospital_id` is threaded through the session store, the database layer, and the connector interface everywhere — there's no code path that can read or write across tenants by accident.
- **Works offline from Redis.** Session state, message history, and rate limiting all have a Redis backend and an automatic in-memory fallback — run the whole stack locally with just Postgres.
- **Build the real thing once it exists, not speculatively.** The Tier 2/3 connector stubs raise a clear "not implemented yet" error rather than guessing at an external API shape before a real hospital on that tier exists.

See [Spec.md](Spec.md) for the full build history, architecture decisions, and an up-to-date progress log — it's the actual source of truth this project is built against, updated as part of every feature, not written once and left stale.

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/PratikGautam-dev/whatsapp-ai-receptionist.git
cd whatsapp-ai-receptionist/backend
uv sync
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your own values
```

Required for the bot to start:

- `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_APP_SECRET` — [Meta Developer Portal](https://developers.facebook.com/)
- `WHATSAPP_VERIFY_TOKEN` — any string you choose (must match the webhook config in Meta's dashboard)
- `INTERNAL_SECRET` — protects `/internal/send-reminders` (the cron-triggered reminder endpoint)
- `ADMIN_SECRET` — gates onboarding a _new_ hospital via the wizard
- `TENANTS_ADMIN_SECRET` — gates the platform-wide tenant list/edit pages, deliberately separate from `ADMIN_SECRET` so a leaked onboarding secret can't also expose every existing tenant's stored credentials
- `PORTAL_SECRET` — signs the hospital-staff portal's session token

Optional:

- `REDIS_URL` — omit it and everything falls back to in-memory automatically (fine for local dev, not for a multi-process production deploy)
- `S3_BUCKET` (+ `S3_REGION`/`S3_ENDPOINT_URL`/`S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY`) — patient document uploads (`core/storage.py`); omit them and uploads fall back to local disk storage, fine for dev
- `FRONTEND_ORIGIN` — the deployed Next.js origin, added to CORS (defaults already include `localhost:3000` for local dev)

To safely preview what's actually set in an env file without printing secret values, use `python scripts/show_env.py .env` rather than `cat`/`type` — it redacts by variable name (fails closed: anything not explicitly known-safe is masked), not by guessing at what a secret's value looks like.

### 3. Database

Local development runs against its own Postgres, never the real deployed database:

```bash
docker compose -f ../docker-compose.dev-db.yml up -d   # starts a local Postgres on localhost:5433 (data persists in a Docker volume)
```

`.env`'s `DATABASE_URL` already points here by default (`postgresql://postgres:postgres@localhost:5433/whatsapp_dev`) — the app creates its schema and seeds a default hospital automatically on first startup, no separate migration step needed. If Docker isn't an option on your machine, any locally-installed Postgres (or a portable, non-Docker binary distribution) works too — just point `DATABASE_URL` at it.

The real, deployed database's connection string lives in `.env.production` (gitignored, never loaded automatically — `app.py` only reads `.env`). Use it only deliberately, e.g. `set -a; source .env.production; set +a` before a one-off command that specifically needs to touch real data. Never rename it to `.env` for routine local development.

### 4. Run the backend

```bash
uv run main.py
```

Serves at `http://127.0.0.1:8000` — creates the schema and seeds a default hospital against whichever `DATABASE_URL` is active on first request (step 3's local Postgres by default).

### 5. Run the staff portal frontend

```bash
cd ../frontend
npm install
npm run dev
```

Serves at `http://localhost:3000`. See [frontend/README.md](frontend/README.md) for frontend-specific details.

### 6. Expose the backend for WhatsApp

Use [ngrok](https://ngrok.com/) for local development:

```bash
ngrok http 8000
```

Set the webhook URL in [Meta Developer Portal](https://developers.facebook.com/) → WhatsApp → Configuration:

- Callback URL: `https://your-ngrok-url.ngrok.io/webhook`
- Verify token: same as your `WHATSAPP_VERIFY_TOKEN`

Then subscribe your app to the WhatsApp Business Account: `POST /{WABA_ID}/subscribed_apps`. Marking fields "Subscribed" in the dashboard alone is **not** sufficient — without this call, Meta logs the event internally but never calls your webhook.

### 7. Onboard your first hospital

Visit `/admin/onboard-hospital` (served by the Next.js frontend) and walk through the wizard — it collects departments, doctors, WhatsApp credentials, and which features (booking, reschedule, cancel, FAQ, etc.) this hospital wants enabled. No manual database work required.

---

## Testing

```bash
uv run pytest
```

499+ tests covering the booking/reschedule/cancel/FAQ state machines, multi-tenant isolation, the staff portal API, onboarding, patient records, rate limiting, and reminders. The suite needs a real Postgres to run against (`tests/conftest.py` provisions one automatically via [testcontainers](https://testcontainers.com/) if Docker is available, or set `TEST_DATABASE_URL` to point at any reachable Postgres instead — useful where Docker itself isn't available).

---

## Deploy

### Backend — Railway

The repo includes `railway.toml` ready to go. Backend code lives in `backend/`, so set the Railway service's Root Directory to `backend` (Settings → Source), then:

```bash
railway up
```

Set the same environment variables described in [Quick start](#2-configure) in the Railway dashboard (pointing `DATABASE_URL` at your real production Postgres, e.g. Neon). Add a cron job for reminders — this project has no in-process scheduler by design:

```
curl -X POST https://your-app.railway.app/internal/send-reminders \
  -H "X-Internal-Secret: $INTERNAL_SECRET"
```

Add a second cron job (e.g. once an hour) to auto-resolve stale "Talk to Reception" handoffs so an unanswered conversation doesn't sit open forever:

```
curl -X POST https://your-app.railway.app/internal/auto-resolve-handoffs \
  -H "X-Internal-Secret: $INTERNAL_SECRET"
```

Any platform that runs Python + FastAPI works just as well; the app starts with:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Frontend — Vercel

The Next.js app in `frontend/` deploys standalone to [Vercel](https://vercel.com/) — set `NEXT_PUBLIC_API_BASE_URL` to your deployed backend's URL, and set `FRONTEND_ORIGIN` on the backend to the deployed frontend's URL so CORS allows it.

---

## Architecture

```
whatsapp-ai-receptionist/
├── backend/                 # FastAPI app (see ARCHITECTURE_PLAN.md for the domain-first reorg in progress)
│   ├── app.py                # composition root: FastAPI app, middleware, lifespan, include_router calls
│   ├── webhook/
│   │   ├── routes.py          # landing page, /health, /webhook GET+POST (the inbound HTTP boundary)
│   │   ├── dispatch.py        # WA-client cache, message locking, flows.handle_incoming() dispatch
│   │   └── cron_routes.py      # /internal/send-reminders, /internal/top-up-slots
│   ├── flows/
│   │   ├── router.py          # the feature-toggle router — the real conversation entry point
│   │   ├── common.py          # cap_rows/is_reset_keyword, shared across every sub-flow
│   │   ├── faq.py             # the FAQ sub-flow
│   │   ├── patient_identity.py # patient registration/selection/consent flow
│   │   └── booking/            # the booking/reschedule/cancel state machine (no LLM), split by sub-flow
│   ├── core/
│   │   ├── history.py         # session state + message history (Redis / in-memory)
│   │   ├── translations.py    # English/Hindi string lookup for the bot's own UI text
│   │   ├── rate_limit.py      # login/secret rate limiting (Redis / in-memory)
│   │   ├── storage.py         # patient document storage (S3/R2-compatible, local-disk fallback)
│   │   ├── whatsapp.py        # WhatsApp Cloud API client
│   │   ├── config.py          # centralized process-level Settings (pydantic-settings)
│   │   └── phone.py           # phone number validation
│   ├── connectors/             # Tier 1/2/3 data-access abstraction (base.py, tier1/2/3.py, dispatch.py)
│   ├── db/
│   │   ├── schema.sql          # idempotent schema (safe to re-run against an existing database)
│   │   ├── models.py           # shared dataclasses (Appointment/Hospital/User), exceptions, constants
│   │   ├── repositories/        # raw SQL by domain (hospitals, doctors, patients, appointments, ...)
│   │   └── init_db.py           # schema + seed, run automatically on startup
│   ├── admin/
│   │   ├── onboarding.py      # the guided onboarding wizard (HTML form route)
│   │   ├── onboarding_api.py  # the same wizard's JSON API, used by the Next.js frontend
│   │   └── tenants_api.py     # platform-admin tenant list/edit
│   ├── portal.py              # hospital-staff portal (legacy server-rendered HTML)
│   ├── portal_api.py          # the same portal's JSON API, used by the Next.js frontend
│   ├── reminders/
│   │   └── scheduler.py       # sends due reminders, called via /internal/send-reminders
│   └── tests/                  # pytest suite, real Postgres required
├── frontend/               # Next.js 16 app — landing page, onboarding wizard, staff portal
├── docker-compose.yml       # backend + frontend, builds from ./backend and ./frontend
└── docker-compose.dev-db.yml # local Postgres for development
```

---

## Contributing

Contributions are welcome. The codebase favors small, direct, auditable code over frameworks-for-the-sake-of-frameworks — please keep it that way.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make sure tests pass (`uv run pytest`)
4. Open a pull request

No issue template, no CLA. Just describe what you changed and why.

---

## Community

- **Issues**: [GitHub Issues](https://github.com/PratikGautam-dev/whatsapp-ai-receptionist/issues) — bug reports, feature requests, questions

---

## License

MIT





One flag before I touch auth: bookings.py is explicitly documented as still using the old hospital-only login (which also accepts a legacy shared portal password, not just per-staff logins) — staff.py/roles.py already migrated to staff-only login, but doing that to all of bookings.py would lock out any hospital still on the legacy shared password from the entire Appointments page, which is far riskier than those two admin-only pages. I'll gate the two new follow-up routes on proper staff role-checks (they're new, so no one depends on reaching them via legacy auth), but leave the existing 9 routes on _authenticate() as-is rather than bundle a bigger migration in — that's a separate, deliberate cleanup this codebase already has flagged for later. Proceeding now.