# SIH26102 Frontend — React + Vite + Tailwind

A ledger/audit-styled frontend for the MPLADS Risk Intelligence platform, built against the
already-tested backend APIs (auth, projects/risk, alerts, imports, cases).

## What's built

| Screen | Route | Built against |
|---|---|---|
| Login | `/login` | `POST /auth/login`, `GET /auth/me` |
| Executive Dashboard | `/dashboard` | `GET /alerts` (KPI counts derived client-side) |
| Risk Queue | `/queue` | `GET /alerts?min_level=...` |
| **Project Risk Profile** (centerpiece) | `/projects/:id` | `GET /projects/{id}/risk` |
| Map Intelligence | `/map` | `GET /projects` (extended with lat/lon + risk, see below) |
| Import Console | `/import` | `POST /imports/upload`, `GET /imports/{id}/preview`, `POST /imports/{id}/confirm` |
| Case Workspace | `/cases`, `/cases/:id` | `GET/POST /cases`, `PATCH /cases/{id}/status`, `GET /cases/{id}/brief` |

## Design system
"Official ledger, not a SaaS dashboard." Deep navy-indigo (`--color-ink`) on warm paper
(`--color-paper`), Newsreader serif for headings, IBM Plex Sans for UI text, IBM Plex Mono for
scores/codes/dates. Risk levels (Low/Medium/High/Critical) use color functionally -- see
`src/index.css` `@theme` block for all tokens, and `src/components/RiskBadge.jsx` for the one
place risk-level color mapping lives (change it there, not per-page).

## One backend change made while building this
`GET /projects` originally didn't return coordinates or risk scores, which the Map page and
queue views both need. Extended `ProjectListItem` (in the backend's `app/schemas/risk.py`) and
the `/projects` route (`app/api/v1/projects.py`) to include `latitude`, `longitude`, `risk_level`,
and `final_score` -- fetched via one extra query (latest score per project), not N+1. Already
tested against real seeded data: coordinates and risk levels come through correctly. If you're
running an older copy of the backend zip, re-download it -- this fix is included.

## Setup

```
npm install
npm run dev
```

Runs on `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://127.0.0.1:8000` (see `vite.config.js`), so **the backend must be running on port 8000**
before you start the frontend -- no CORS config needed for local dev because of the proxy.

Backend startup reminder (from the backend's own README):
```
cd ../backend
python3 -m uvicorn app.main:app --reload
```

Login with any of the 5 seeded test accounts, e.g. `admin@sih26102.gov.in` / `Admin@123`.

## Build for production
```
npm run build
```
Outputs to `dist/`. Confirmed this completes with zero errors (one harmless "chunk size" warning
about bundle size -- fine for a hackathon demo, not worth code-splitting under deadline pressure).

## Known gaps / next steps
- **Not visually screenshot-tested** in this environment (Playwright's browser binary couldn't
  download under this sandbox's network restrictions, and a later attempt to run the dev server
  hit an environment hang unrelated to the code). The build compiles cleanly and every screen is
  wired to real, already-tested backend endpoints, but give it an actual look in your own browser
  before trusting it for a live demo -- sizing, spacing, and Leaflet map rendering specifically
  haven't been eyeballed by anyone yet.
- Executive Dashboard KPIs are computed client-side from `/alerts` (there's no dedicated
  `/analytics/summary` endpoint yet). Fine for current scale; revisit if the alert list grows large.
- No pagination UI yet on Risk Queue or Cases list (backend supports `limit`/`offset` params on
  `/projects` already; `/alerts` and `/cases` would need the same added if lists grow past ~200).
- Map page assumes projects have `latitude`/`longitude`; projects missing coordinates (VAL-008)
  are silently excluded from the map rather than shown with a placeholder -- intentional for now,
  but worth a "N projects have no location data" note if this becomes a common case.
- No toast/notification system -- mutations (recompute, status change, comment) rely on inline
  success/error states only. Fine for a demo, would want proper feedback for real use.
