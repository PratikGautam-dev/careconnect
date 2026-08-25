# CareConnect Backend Architecture Redesign

## Context

CareConnect is a multi-tenant WhatsApp appointment-booking system for hospitals (FastAPI + raw psycopg2/Postgres + Redis, no ORM, no LLM — pure conversational state machine), plus a staff/admin portal API consumed by a separate Next.js frontend. This document proposes a target architecture and a phased, incremental migration plan — no big-bang rewrite, no framework/ORM change, app stays shippable and green against the existing testcontainers test suite at every step.

This revision adds a new first phase: the repo currently has `frontend/` as its own self-contained top-level directory (own `Dockerfile`, own `package.json`), while all backend code (`core/`, `db/`, `admin/`, `config/`, loose files, `tests/`, etc.) still sits loose at the repo root, mixed in with project docs and marketing screenshots. The goal is a repo with exactly two top-level code directories, `backend/` and `frontend/`, mirroring each other. That move happens first, as pure relocation with zero logic changes; the domain-first internal reorg (originally designed, now updated for files added since) happens afterward, inside `backend/`.

## What changed since the original version of this plan

- `db/repository.py` grew from 2451 → **2880** lines; `portal_api.py` 1175 → **1205**; `core/booking_flow.py` 1369 → **1873**.
- New file **`core/patient_identity.py`** (646 ln) — a full conversational flow (patient registration, duplicate/relationship resolution, patient selector, unlink, consent/privacy). Belongs in the `flows/` domain grouping alongside `booking/` and `faq.py`, not in `core/`.
- Per-tenant **feature toggle** (`enabled_features`) landed, touching `admin/tenants_api.py`, `db/repository.py`/`db/init_db.py`, `flows.py`, `core/main.py`, `portal_api.py`, `faq_flow.py`, `user_auth.py`, `core/translations.py`. It's config-shaped data living in the `hospitals` table (same pattern as existing per-tenant config) — no new module needed, just carried along wherever each of those files ends up.
- New tests: `test_patient_identity.py`, `test_patient_selection_flow.py`, `test_enabled_features_migration.py`, `test_careconnect_alignment.py`, `test_booking_back_navigation.py`, `test_my_details_flow.py`, `test_hospital_settings.py`, `test_phase8_edge_cases.py` — move with their code, same rule as before.
- Still dead/legacy, unchanged, out of scope: `config/loader.py` + `config.yaml`, `modules/booking/calendar.py`.

## Current pain points (verified by exploration)

- `db/repository.py` (2880 ln) — a single god-file doing raw-SQL data access for ~13 unrelated concerns (hospitals, users, doctors, leave, slots, patients, patient records, appointments, dashboard, FAQ, handoffs). Only 3 dataclasses exist in the whole app; everything else is untyped `dict`.
- `portal_api.py` (1205 ln) — ~35 staff-portal REST endpoints in one flat router, with JSON-shaping and validation logic interleaved inline, including a private-function cross-import from `admin/onboarding.py`.
- `core/booking_flow.py` (1873 ln) — the entire book/cancel/reschedule state machine in one file; `flows.py` imports underscore-prefixed "private" symbols from it directly (no public interface).
- `core/main.py` (413 ln) — mixes app bootstrap, webhook routing, WhatsApp-client caching (has a known stale-credential bug), Redis message locking, and cron endpoints.
- `core/history.py` (208 ln) — two unrelated stores (chat history + session state) in one file.
- `core/patient_identity.py` (646 ln) — a standalone conversational flow living under `core/` even though it's domain-shaped like `flows.py`/`faq_flow.py`, not a core-infrastructure concern.
- No centralized config object — every module does its own `os.environ.get(...)`. (Per-tenant config correctly lives in the `hospitals` DB table already — that part is fine and must not change.)
- Two dead/legacy code paths exist (`config/loader.py`+`config.yaml`, `modules/booking/calendar.py`) — **decision: leave both in place for now**, not part of this restructuring.
- Backend code sits loose at the repo root instead of in its own `backend/` directory, unlike `frontend/` which is already self-contained — this also means `docker-compose.yml`, `docker-publish.sh`, and `railway.toml` reference root-relative backend paths that need to move in lockstep with the code.
- Tests (`tests/`, 34+ files, ~10k+ ln, pytest + testcontainers) largely mirror the size of the prod files they test — any restructuring must move tests alongside the code they cover, in the same PR, never as a deferred cleanup pass.

## Design principles

1. **Top-level move is pure relocation.** `backend/` gets created as one mechanical "move everything, fix build/deploy paths" phase, done and verified green *before* any domain-first internal reorg begins. Don't interleave file moves with restructuring.
2. **Domain-first, not layer-first.** Split by domain (hospitals, doctors, patients, appointments, handoffs...); apply routes/services/repository layering *within* each domain, not as three new giant folders replacing one giant file.
3. **Preserve what already works.** The `Connector` ABC (`connectors.py`) is the one clean abstraction boundary in the app — keep its interface and "resolved once per webhook request" pattern untouched, just relocate the file. Same for the `_HANDLERS` state-dispatch dict pattern in the booking flow.
4. **Public interfaces, not underscore imports.** Every cross-module reach into `_private` symbols gets replaced with an explicit exported API.
5. **No ORM, no framework swap, no Alembic adoption in this pass.** This is a file/module reorganization plus targeted typing, not a data-layer rewrite.
6. **Tests move with the code they test**, same PR, always.

## Target repo layout (top level)

```
careconnect/
  backend/                     # NEW top-level dir — mirrors frontend/
    app.py  core/  webhook/  flows/  connectors/  db/  portal/  admin/  auth/
    reminders/  slots/  scripts/  tests/
    requirements.txt  pytest.ini  Dockerfile  .dockerignore  .env.example
  frontend/                    # unchanged, already self-contained
    src/  public/  package.json  Dockerfile  .dockerignore  ...
  docker-compose.yml           # updated: backend build context -> ./backend
  docker-compose.prod.yml      # unchanged (pulls prebuilt images, no local paths)
  docker-compose.dev-db.yml    # unchanged (just a postgres service)
  docker-publish.sh            # updated: -f backend/Dockerfile backend
  railway.toml                 # kept, startCommand path updated (see Phase A / Phase 4)
  README.md  LICENSE  DECISIONS.md  DEPLOYMENT.md  Spec.md   # stay at root — project-level, not backend/frontend-specific
  public/  *.jpeg  *.png  onboarding-wizard-design.html        # stay at root — marketing/doc assets, not app code
```

**Rationale:** `backend/` becomes the exact mirror of `frontend/` — each independently buildable/testable, each owning its own `Dockerfile`/`.dockerignore`/dependency manifest. Docs and image assets that describe the whole product (not one side of it) stay at the repo root rather than being force-fit into either directory.

## Target directory structure inside `backend/`

```
backend/
  app.py                         # composition root: FastAPI app, middleware, lifespan, include_router calls
  core/
    config.py                    # NEW: centralized Settings (process-level env vars only)
    whatsapp.py / rate_limit.py / storage.py / phone.py / translations.py   # unchanged
    chat_history.py              # was history.py's message-history half
    session_store.py             # was history.py's session/state half
  webhook/
    routes.py                    # /webhook GET+POST, /health
    dispatch.py                  # WA-client cache, message locking, _process_message
    cron_routes.py                # /internal/send-reminders, /internal/top-up-slots
  flows/
    router.py                    # was flows.py
    common.py                    # was core/flow_common.py
    faq.py                       # was faq_flow.py
    patient_identity.py          # was core/patient_identity.py — patient registration/
                                  # selection/unlink/consent flow, same domain grouping as
                                  # booking/faq, moved as-is (no split needed)
    booking/
      __init__.py                # PUBLIC re-export surface (no more underscore imports)
      state.py                   # STATE_* constants, FREE_TEXT_INPUT_STATES, row-id encode/decode helpers
      messages.py                # WA message/menu builders shared across sub-flows
      book.py / cancel.py / reschedule.py   # per-sub-flow handlers
      dispatch.py                # _HANDLERS dict (same pattern, values imported from the 3 files above) + handle_incoming()
  connectors/
    base.py                      # Connector ABC + errors
    tier1.py                     # Tier1Connector
  db/
    connection.py, schema.sql, init_db.py, seed.py   # unchanged
    models.py                    # dataclasses: Appointment, Hospital, User + new ones added alongside each domain split
    repositories/
      hospitals.py / users.py / doctors.py / leave.py / slots.py /
      patients.py / patient_records.py / appointments.py / dashboard.py / faq.py / handoffs.py
  portal/
    deps.py                      # shared auth dependency (get_current_hospital), replaces manual _authenticate()
    routes/     auth.py / dashboard.py / patients.py / documents.py / bookings.py / doctors.py / settings.py / handoffs.py
    services/   patients_service.py / bookings_service.py / doctors_service.py / settings_service.py / handoffs_service.py
  admin/
    onboarding.py / onboarding_api.py / tenants_api.py / theme.py   # unchanged role
    validation.py                # NEW: shared field validators (_validate_doctor_fields), used by admin/* AND portal/services/doctors_service.py
  auth/
    session.py                   # was portal.py
    google_oauth.py              # was user_auth.py
  reminders/scheduler.py, slots/scheduler.py   # unchanged
  tests/
    unit/            # pure-logic tests, no DB
    integration/      # testcontainers-backed, mirrors db/repositories/*, portal/routes/*, flows/booking/*
```

**One-line rationale per new folder:** `webhook/` isolates the inbound HTTP boundary from app bootstrap. `flows/` groups the whole conversation engine (router + booking + faq + patient_identity) instead of scattering flow files at repo top-level. `connectors/` gives Tier2/3 connectors (already anticipated in the code) a home. `db/repositories/` splits the god-file along its own existing `# ---` section boundaries. `portal/routes` + `portal/services` separate thin HTTP handlers from business/validation logic. `auth/` collapses the two independent home-grown token schemes into one clearly-named package (not unified — just named, see Out of Scope). `core/config.py` is one Settings object for process-level env vars, explicitly not a replacement for per-tenant DB config.

## Phase A (NEW) — Move backend code into `backend/`, mechanical only

Move, in one PR, with no internal restructuring:
- Directories: `core/`, `db/`, `admin/`, `config/`, `modules/`, `reminders/`, `slots/`, `scripts/`, `tests/`
- Files: `connectors.py`, `flows.py`, `faq_flow.py`, `portal_api.py`, `portal.py`, `user_auth.py`, `config.yaml`
- Backend-specific tooling: `requirements.txt`, `pytest.ini`, `Dockerfile`, `.dockerignore`, `.env.example`

Then, same PR:
- **`docker-compose.yml`**: `backend.build.context: .` → `./backend` (dockerfile path stays `Dockerfile`, now resolved inside that context).
- **`docker-publish.sh`**: `-f Dockerfile .` → `-f backend/Dockerfile backend` (line ~52).
- **`backend/.dockerignore`**: drop the now-redundant `frontend/` exclusion (frontend is no longer inside the backend build context at all).
- **`railway.toml`**: still in active use (e.g. a Railway staging environment) — keep it, update `startCommand` to match the new module path. In Phase A it becomes `uvicorn core.main:app` run with `backend/` as the working directory (Railway's root/working-dir setting needs the corresponding update, not just the file); after Phase 4 (once `core/main.py` splits into `webhook/` + thin `app.py`), update it again to `uvicorn app:app`.
- **Root `.env.example`**: either move to `backend/.env.example` or duplicate the reference in root `README.md`/`DEPLOYMENT.md` — decide based on whether `docker-compose.yml`'s `env_file: .env` stays root-relative (compose files resolve `env_file` relative to the compose file's own location, so `.env` can stay at repo root even though `.env.example` conceptually documents backend-only vars — verify this at implementation time rather than assuming).
- Run full `pytest` suite from inside `backend/` (or with `pytest backend/` from root, matching wherever CI invokes it) to confirm the move alone broke nothing — no import paths inside the backend package should have needed to change, since everything moved together as one subtree.

This phase must land and be verified (tests green, `docker compose build` succeeds for both services) before Phase 0 of the domain-first reorg starts.

## Key restructuring specifics

**`db/repository.py` split** — cut along the file's own existing section comments into the 11 domain files listed above. During migration, `db/repository.py` becomes a re-export shim (`from db.repositories.hospitals import *`, etc.) so callers keep working while call sites move one at a time; delete the shim once `grep -r "import db.repository"` outside it returns nothing.

**Typed models** — keep the 3 existing dataclasses, move to `db/models.py`. Add dataclasses only for entities crossing the `Connector` boundary or the portal JSON boundary (`Doctor`, `Department`, `DoctorLeave`, `Slot`, `Patient`, `PatientDocument`, `PatientVisitNote`, `HandoffRequest`, `FAQTopic`), introduced in the same PR as that domain's repository split — not a separate typing sweep. Do not type internal SQL row-mapping or one-off dicts (e.g. dashboard aggregates, CSV-import intermediates).

**`portal_api.py` split** — one `APIRouter()` per resource (auth, dashboard, patients, documents, bookings, doctors, settings, handoffs), mounted from `portal/routes/__init__.py`. Extract `_authenticate`/`_session_id` into a FastAPI `Depends(get_current_hospital)` in `portal/deps.py` to remove repeated boilerplate across ~30 handlers. Extract JSON-shaping helpers (`_patient_json`, `_appointment_json`) into matching `*_service.py` files. Move `_validate_doctor_fields` out of `admin/onboarding.py` into `admin/validation.py`, imported by both `admin/onboarding.py` and `portal/services/doctors_service.py` — this directly fixes the private cross-import. Split routes first (pure move, path-string-diff verifiable), extract services as a separate follow-up pass.

**`booking_flow.py` / `flows.py` coupling** — first introduce `flows/booking/__init__.py` as a public re-export module (drop the underscore prefixes, no code moved yet, no behavior change) and update `flows.py` to import through it. Only after that's verified, physically split `core/booking_flow.py` into `state.py` / `messages.py` / `book.py` / `cancel.py` / `reschedule.py` / `dispatch.py`, keeping the `_HANDLERS` dict pattern exactly as it is today. Decide explicitly (flagged for a follow-up, not assumed) whether the now-superseded standalone `handle_incoming()`/`_handle_idle()` entry point kept only for `tests/test_booking_flow.py` should be retired in favor of testing the new public dispatch directly.

**`core/patient_identity.py` move** — move as-is into `flows/patient_identity.py` (no internal split needed at 646 ln); update its own imports and the ~8 files that import from it (`core/history.py`, `flows.py`, `core/booking_flow.py`, and tests).

**`core/main.py` split** — extract webhook routing + WA-client cache + message locking into `webhook/routes.py` + `webhook/dispatch.py`; extract the two cron endpoints into `webhook/cron_routes.py`; leave a thin `app.py` as the composition root (app construction, lifespan, `include_router` calls only).

**Config centralization** — `core/config.py` defines one `Settings` object (pydantic-settings `BaseSettings`, since pydantic is already a dependency) covering only process-level env vars (DB/Redis URLs, secrets, S3/R2 creds, WA API base). Per-tenant config stays in the `hospitals` table, untouched. Migrate module-by-module (`core/main.py`, `db/connection.py`, `core/storage.py`, `admin/*`, `user_auth.py`, `portal.py`, ...), each a small independent diff verified with `grep os.environ` before/after and against the existing `tests/test_show_env_redaction.py`.

## Phased migration plan

Each phase ships independently, keeps `pytest` (full testcontainers suite) green at every commit, and moves the tests covering the code it touches in the same PR.

0. **Phase A — Move to `backend/`.** Mechanical relocation of all backend directories/files plus `docker-compose.yml`/`docker-publish.sh`/`railway.toml` path updates, as described above. No internal restructuring. Must land and verify green before any other phase starts.
1. **Phase 0 — Groundwork.** Add `core/config.py`; migrate `os.environ` reads file-by-file. Add `tests/unit/` and `tests/integration/` scaffolding with a clear split rule (uses testcontainers fixture → integration, else unit).
2. **Phase 1 — `db/repository.py` split.** ~8–10 small PRs, one or two adjacent domains at a time (hospitals+users → doctors+leave → slots → patients+patient_records → appointments → dashboard → faq+handoffs), each introducing that domain's dataclasses and moving its tests into `tests/integration/repositories/`. Delete the shim once nothing imports `db.repository` anymore.
3. **Phase 2 — `connectors.py` → `connectors/` package.** Small, mechanical; update imports to the new repositories.
4. **Phase 3 — `booking_flow.py`/`flows.py` restructuring.** 3a: public re-export module only (no file moves). 3b: physical split into `flows/booking/*`, moving `test_booking_flow.py` and related test files alongside. 3c: move `flows.py`→`flows/router.py`, `flow_common.py`→`flows/common.py`, `faq_flow.py`→`flows/faq.py` with their tests. 3d: move `core/patient_identity.py` → `flows/patient_identity.py` with `test_patient_identity.py`/`test_patient_selection_flow.py`.
5. **Phase 4 — `core/main.py` split** into `webhook/` + thin `app.py`. Update `railway.toml`'s `startCommand` to `uvicorn app:app`.
6. **Phase 5 — `core/history.py` split** into `chat_history.py` + `session_store.py`.
7. **Phase 6 — `portal_api.py` split.** Routes first (7 small PRs by resource group, each moving its slice of `test_portal_api.py`), services extraction as a second pass, including the `admin/validation.py` extraction.
8. **Phase 7 — `admin/`/`portal.py`/`user_auth.py` → `auth/`.** Pure rename, lowest risk, done last.

**Ordering rationale:** the top-level move goes first since every later phase's paths depend on it. Repositories go next since nearly everything else depends on stable data-access paths; booking flow (largest, most coupling) comes once the "public re-export then split" pattern is proven on a smaller phase; portal API is large but has the least cross-phase coupling, so it can absorb schedule slack last among the big items.

## Explicitly out of scope / do not touch

- `Connector` ABC design and its per-request resolution pattern — relocate only, never redesign.
- Per-tenant config in the `hospitals` table — stays exactly as-is.
- `core/phone.py`, `core/rate_limit.py`, `core/storage.py`, `core/translations.py`, `db/connection.py` — already fine, move only incidentally.
- No ORM adoption, no Alembic/migration-tool adoption, no JWT/auth-library unification — each is a separate, security- or risk-sensitive decision deserving its own review, not bundled into a reorganization pass.
- `_HANDLERS` dispatch-dict pattern — keep as-is, it already works.
- `admin/theme.py`'s inline CSS string, and the two dead-code paths (`config/loader.py`+`config.yaml`, `modules/booking/calendar.py`) — left untouched per decision; not part of this plan.
- `frontend/` internals — already at the target location, needs no restructuring here.
- Root-level docs (`README.md`, `DECISIONS.md`, `DEPLOYMENT.md`, `Spec.md`) and marketing/screenshot assets — stay at repo root; only updated where they contain now-stale paths (e.g. `DEPLOYMENT.md`'s references to root `Dockerfile`/`docker-publish.sh` usage), as a documentation-accuracy pass alongside Phase A, not a structural change.

## Verification

- Run the full `pytest` (testcontainers) suite at the end of every phase/PR, not just the moved files' tests — several existing tests cross domain boundaries (e.g. `test_multi_tenant.py`) and would catch a bad move.
- For pure-rename/re-export steps (e.g. Phase A, Phase 3a, Phase 2, Phase 7), verify via `grep` that no behavior changed: route path strings, `_HANDLERS` dict keys, and public function signatures should diff identically before/after.
- For Phase A specifically: `docker compose build` (both services) succeeds against the new `./backend` context; `docker-publish.sh --no-push` succeeds; confirm `.env`/`.env.example` resolution still works with compose's `env_file` path.
- For the `db/repository.py` shim removal, verify via `grep -r "import db.repository"` that no non-shim caller remains before deleting it.
- For config centralization, cross-check `core/config.py`'s `Settings` output against `tests/test_show_env_redaction.py`'s existing expectations.

## Status

- **Phase A — done.** Backend code moved into `backend/`; `docker-compose.yml`, `docker-publish.sh`, `railway.toml`, CI workflow, and docs updated to match. Verified: full test suite green, backend Docker image builds from the new `./backend` context.
- **Phase 0 — done.** `core/config.py` centralizes the static, load-once env vars via `pydantic-settings` (added as a dependency). `REDIS_URL`/`DATABASE_URL` deliberately left as direct `os.environ` reads (live re-check pattern, exercised by tests via `monkeypatch`). No cached singleton — `get_settings()` re-reads on each call, to avoid disturbing a pre-existing test-collection-order dependency on `WHATSAPP_VERIFY_TOKEN`. Verified: full test suite green, Docker build green.
- **Phase 1 — done.** `db/repository.py` (2880 ln) split into `db/models.py` (shared dataclasses `Appointment`/`Hospital`/`User`, exceptions, constants, row-mappers, reference/display-id generation) and 11 domain files under `db/repositories/` (hospitals, users, doctors, leave, slots, patients, patient_records, appointments, dashboard, faq, handoffs). `db/repository.py` is now a 33-line re-export shim — kept until `grep -r "import db.repository"` outside it returns nothing. Verified: full test suite green (605/611 — same 6 pre-existing timezone-dependent handoff-staleness failures as before this phase, unrelated), Docker build green.
- **Phase 2 — done.** `connectors.py` split into a package: `connectors/base.py` (the `Connector` ABC, `ConnectorNotImplementedError`, the shared `_UnimplementedTierConnector` stub base), `connectors/tier1.py`/`tier2.py`/`tier3.py` (one file per tier), `connectors/dispatch.py` (`get_connector_for_hospital` + the stateless per-tier singletons). `connectors/__init__.py` re-exports the full public surface so every existing `from connectors import X` call site is unchanged. Verified: full test suite green (605/611, same pre-existing failures), Docker build green.
- **Phase 3a/3c/3d — done** (3b, the physical split of `core/booking_flow.py` itself, deferred — see below). `flows.py` → `flows/router.py`, `core/flow_common.py` → `flows/common.py`, `faq_flow.py` → `flows/faq.py`, `core/patient_identity.py` → `flows/patient_identity.py` — all now live under the new `flows/` package. `flows/booking/__init__.py` is the Phase 3a public re-export surface for `core/booking_flow.py` (still in its original location, untouched) — `flows/router.py` now imports `start_booking_flow`/`start_cancel_flow`/`HANDLERS`/etc. as public names instead of reaching into `core.booking_flow`'s underscore-prefixed symbols directly. `flows/__init__.py` re-exports the package's public surface via a lazy `__getattr__` (PEP 562), not an eager `from flows.router import *` — the eager form created a real circular import (`core.booking_flow` → `flows.common` → triggers `flows/__init__.py` → `flows.router` → `flows.booking` → back to the still-initializing `core.booking_flow`), caught by the test suite (`ImportError: cannot import name '_HANDLERS' from partially initialized module`) and fixed by deferring the router import to first attribute access. Also found and fixed two inline `import faq_flow` / `from core.flow_common import ...` statements inside test function bodies that a file-level-only grep missed. Verified: full test suite green (605/611, same pre-existing failures), Docker build green.
- **Phase 3b — done.** `core/booking_flow.py` (1873 ln, 120 top-level definitions) physically split, via an AST-verified line-span extraction (same technique as Phase 1, this time checked programmatically against the file's own `ast.parse()` output rather than by hand, precisely to avoid a repeat of Phase 1's off-by-one boundary bugs) into `flows/booking/`: `state.py` (constants, step-history stack, row-id helpers — zero I/O), `messages.py` (WA message/menu builders shared across sub-flows), `book.py`/`cancel.py`/`reschedule.py` (per-sub-flow handlers, as planned) plus two more sub-flow files the plan's file list hadn't named because they didn't exist when it was written — `view_appointments.py` and `manage_patients.py` (both landed after the original plan draft, per "What changed" above) — and `dispatch.py` (`_HANDLERS` + `handle_incoming()`). `core/booking_flow.py` is deleted outright (not left as a shim) since the plan's target structure never listed it; `flows/booking/__init__.py` is the permanent public re-export surface, now pointing at the new files instead of the old single module. One genuine circular dependency was found and fixed: `messages.py`'s `_select_patient_and_continue` routes into `cancel.py`/`reschedule.py`/`manage_patients.py`/`view_appointments.py`, each of which imports back from `messages.py` — resolved with a **deferred (function-body) import** inside `_select_patient_and_continue` itself, the standard Python technique for this shape of cycle, keeping every other cross-file import at the normal module top level. Also updated 5 test files' `from core.booking_flow import ...` (including one inline import inside a test function body) to `from flows.booking import ...`. Verified: full test suite green on the first run post-split (605/611, same pre-existing failures — no new boundary bugs this time), Docker build green.
- **Phase 4 — done.** `core/main.py` split into `app.py` (composition root: FastAPI app, CORS/Session middleware, lifespan, `init_db()`, `include_router` calls — no routes decorated directly on `app` anymore) and `webhook/`: `routes.py` (landing page, `/health`, `/webhook` GET+POST — the inbound HTTP boundary), `dispatch.py` (`HISTORY`/`SESSIONS` singletons, the WA-client cache, Redis-backed message lock, `_process_message`), `cron_routes.py` (`/internal/send-reminders`, `/internal/top-up-slots`). `core/main.py` deleted outright, matching Phase 3b's precedent (no permanent shim for a file the target structure doesn't list) — the ASGI entrypoint is now `app:app`, updated in `backend/Dockerfile`'s `CMD`, `railway.toml`'s `startCommand`, and the README/DEPLOYMENT.md references that describe the current (not historical-incident) deployment state. 16 test files needed updating: 11 `from core.main import app` → `from app import app`, plus 5 inline `import core.main as m` statements deep in test bodies (missed by an initial file-level-only grep, same lesson as Phase 3 — caught by the second full test-suite run, not by static analysis). Verified: full test suite green (605/611, same pre-existing failures), Docker build green, **and** an actual container boot-to-`/health` smoke test against the real dev Postgres (`docker-compose.dev-db.yml`) — not just an image build — since this phase changes the literal ASGI entrypoint string every deploy path depends on.
- **Phase 5 — done.** `core/history.py` (296 ln, two unrelated stores in one file) split into `core/chat_history.py` (`InMemoryHistory`/`RedisHistory`, `get_history()`, `MAX_MESSAGES`) and `core/session_store.py` (`InMemorySessionStore`/`RedisSessionStore`, `get_session_store()`, `DEFAULT_STATE`, `SESSION_TIMEOUT_SECONDS`, plus the large block comment documenting the `language`/`active_patient_id` top-level-field design). `core/history.py` deleted outright, same precedent as `core/booking_flow.py`/`core/main.py` — no permanent shim, since the target structure never lists it. Updated `webhook/dispatch.py`'s two-name import, 12 test files' `from core.history import InMemorySessionStore`, `test_history.py`'s combined import (now split across both new modules), and `test_session_timeout.py`'s `import core.history as history_module` (used to monkeypatch `time.time()` inside the session-timeout logic — retargeted to `core.session_store`). Also updated ~10 comment-only `core/history.py` references scattered across `core/storage.py`, `core/config.py`, `core/rate_limit.py`, `flows/common.py`, `flows/router.py`, `db/repositories/dashboard.py`, and test docstrings, plus `DEPLOYMENT.md`'s `REDIS_URL` ownership table — none were functional, all were stale-reference risk. No bugs found; a clean line-based split (chat history and session state never shared any code, just the same file). Verified: full test suite green (605/611, same 6 pre-existing failures), run against a real Postgres via testcontainers.
- **Phase 7 done ahead of schedule, as a Phase 6 prerequisite.** The target layout names a package `portal/` (Phase 6, below) in the same directory as the existing top-level module `portal.py` -- a real Python naming collision, not just a style question, so `portal.py` had to move out of the way first. `portal.py` → `auth/session.py`, `user_auth.py` → `auth/google_oauth.py` (both pure moves, `admin/` untouched -- it was already domain-first, nothing to move). Updated imports in `auth/google_oauth.py`, `admin/onboarding_api.py`, `tests/conftest.py`, `app.py` (2 import lines + 2 comment references), plus doc-only `portal.py`/`user_auth.py` mentions inside both moved files' own docstrings. Verified alongside Phase 6 below (same test/build run).
- **Phase 6 — done (routes split; services extraction deferred).** `portal_api.py` (1205 ln, ~35 endpoints in one flat router) split into `portal/deps.py` (`_authenticate`/`_hospital_summary`/`_session_id`, moved as plain functions -- **not** converted to a FastAPI `Depends(get_current_hospital)`, a deliberate scope cut: the plan's own suggestion, but changing ~30 handler signatures to use dependency injection is a real behavior-shape change, not a pure move, and the standing instruction for this whole migration is restructure-only) and `portal/routes/{auth,dashboard,patients,documents,bookings,doctors,settings,handoffs}.py`, one `APIRouter()` per resource, mounted from `portal/routes/__init__.py` into the single router `app.py` includes. `_appointment_json` lives in `bookings.py` and is imported by `patients.py` (visit history) and `doctors.py` (today's appointments) -- the one cross-file dependency in an otherwise clean split. New-booking's two endpoints (context + create) went into `bookings.py` alongside cancel/reschedule rather than a separate file, since the plan's own resource list doesn't call out "new-booking" as distinct from bookings. The doctors-route registration-order comment (static paths like `csv-import` MUST be registered before the `{doctor_id}` catch-all) survives intact since all doctor routes stayed together in one file, same relative order as the original. `_validate_doctor_fields`/`_parse_offsets` stayed in `admin/onboarding.py` (imported by `portal/routes/doctors.py` and `settings.py`) -- the plan's `admin/validation.py` extraction is the deferred "services extraction, second pass" work, not done here. `portal_api.py` deleted outright, same no-shim precedent as Phases 3b/4/5. Updated `tests/test_patient_records.py` and `tests/test_portal_api.py`'s `monkeypatch.setattr(portal_api.WhatsAppClient, ...)` calls to import `WhatsAppClient` directly from `core.whatsapp` instead -- patching the class object itself still works identically regardless of which module imports it, so this was a safe, behavior-preserving fix, not a workaround. Also updated ~20 comment-only `portal_api.py`/`portal.py` references across `core/storage.py`, `admin/tenants_api.py`, `db/repositories/{patient_records,hospitals,dashboard}.py`, `flows/{patient_identity,router}.py`, `auth/google_oauth.py`, `admin/onboarding.py`, and test docstrings. Verified: full test suite green (605/611, same 6 pre-existing failures), Docker build green, **and** a container boot-to-`/health` smoke test plus a live `/api/portal/login` call (403 on a wrong password, not a routing/import error) against the real dev Postgres -- checking that the doctors router's static-before-catch-all registration order survived the split, not just that the app imports.
- **Phase 6's services-extraction second pass — done (`admin/validation.py` only; JSON-shaping helpers left in place).** `_validate_doctor_fields` and `_parse_offsets` moved out of `admin/onboarding.py` into the new `admin/validation.py`, along with the private helpers they alone depend on (`_split_time_range`, `_minutes_between`, `_WEEKDAY_ABBREVS`/`_WEEKDAY_SET`/`_TIME_RANGE_RE`) -- this directly fixes the private cross-import the plan called out (`portal/routes/doctors.py` and `portal/routes/settings.py` reaching into `admin/onboarding.py` for genuinely generic field validation, not onboarding-specific logic). `_build_departments`/`_build_faq_topics` stayed in `admin/onboarding.py` since nothing outside that file imports them (dead code left over from the removed HTML wizard, by inspection -- not touched, deleting unused code is a judgment call outside this migration's restructure-only scope); `_build_departments` now imports `_validate_doctor_fields` back from `admin/validation.py`. `check_admin_secret`/`ADMIN_SECRET`/`_VALID_TIERS`/`_mask_secret`/the two HTML entry-point pages all stayed too -- genuinely onboarding/tenant-admin-specific, not generic validation. Updated 5 import sites: `admin/onboarding_api.py`, `admin/tenants_api.py`, `portal/routes/doctors.py`, `portal/routes/settings.py`, `tests/test_doctor_scheduling.py`. The JSON-shaping-helper consolidation (`_patient_json`/`_appointment_json` into dedicated service files) mentioned alongside this in the plan was judged not worth doing separately from where they already sit (`patients.py`/`bookings.py` respectively, each already the one file that owns that shape) -- moving them again into a `*_service.py` would be reshuffling for its own sake, not fixing a real cross-import. Verified: full test suite green (605/611, same 6 pre-existing failures), Docker build green.

This completes every phase in the migration plan (A, 0–6 including the deferred pass). `backend/` and `frontend/` are now both self-contained, domain-first trees.

The 6 recurring test failures (`test_flows.py`'s handoff-silencing tests, `test_slot_blocking_soft_delete_and_refs.py`'s handoff-staleness tests) are a pre-existing bug unrelated to this restructuring: `db/repositories/handoffs.py`'s `has_open_handoff()`/`get_open_handoff()` compare `datetime.now()` (local system time) against Postgres's `now()::text` (UTC) — on a host whose local timezone is ahead of UTC (e.g. IST, UTC+5:30), the staleness threshold ends up later than a freshly-created row's `created_at`, so a brand-new handoff reads as already-stale. Confirmed present before any of these phases via `git diff` showing zero content change on the affected function during the Phase A move. Worth its own fix, out of scope for this restructuring.
