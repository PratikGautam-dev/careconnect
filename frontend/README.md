# DAAP CareConnect — Frontend

The Next.js app for [DAAP CareConnect](../README.md): the public landing page, the guided hospital-onboarding wizard, the hospital-staff booking portal, and the platform-admin tenant pages. Talks to the FastAPI backend (`../core/main.py` and friends) entirely over JSON — `portal_api.py` for the staff portal, `admin/onboarding_api.py` for onboarding, `admin/tenants_api.py` for platform admin.

Built with Next.js 16 (App Router) / React 19 / TypeScript / Tailwind v4.

## Getting started

From the repo root, get the backend running first (see the [root README](../README.md#quick-start)) — the frontend expects it at `http://localhost:8000` by default. Then:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Point at a different backend by setting `NEXT_PUBLIC_API_BASE_URL` (see `.env.local`).

## Pages

| Route | What it is |
|---|---|
| `/` | Public landing page |
| `/admin/onboard-hospital` | Guided multi-step wizard for onboarding a new hospital (WhatsApp setup, departments/doctors, feature selection) |
| `/admin/tenants`, `/admin/edit-tenant/[id]` | Platform-admin tenant list/edit, gated by `TENANTS_ADMIN_SECRET` — separate credential from onboarding's `ADMIN_SECRET` |
| `/portal/login` | Hospital-staff login |
| `/portal/dashboard` | Stat tiles, weekly trend, department breakdown, recent activity |
| `/portal/appointments` | List + cancel (with an optional patient-facing message) |
| `/portal/doctors` | Add/manage doctors and departments — schedule, breaks, quotas, leave, CSV bulk import |
| `/portal/patients`, `/portal/patients/[id]` | Patient directory + record (visit history, notes, document upload sent straight to the patient's WhatsApp chat) |
| `/portal/messages` | The human-handoff inbox — reply to a patient who escalated from the bot |
| `/portal/new-booking` | Staff-created bookings, through the exact same connector path a WhatsApp patient's booking uses |
| `/portal/settings` | Self-serve bot customization: menu labels, closing message, business hours, default language, session timeout |

## Design system

`src/app/globals.css` defines the token set (brand/clay color scales, an 8px spacing scale under its own Tailwind namespace, typography, shadows) — extend it there rather than hardcoding one-off values. Shared primitives live in `src/components/ui/` (`Button`, `Card`, `Badge`, `Input`/`Field`, `Checkbox`, step rails). Icons via `lucide-react`; charts (dashboard) via `recharts`.

## Testing

`playwright` is available for end-to-end smoke testing against a running dev server — there's no fixed test suite here yet; the backend's `pytest` suite (repo root) is what CI runs. See the root README's [Testing](../README.md#testing) section.

## Building for production

```bash
npm run build
npm start
```

Deploys to [Vercel](https://vercel.com/) — see the root README's [Deploy](../README.md#deploy) section for the required environment variables (`NEXT_PUBLIC_API_BASE_URL` here, `FRONTEND_ORIGIN` on the backend).
