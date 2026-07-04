# Haley365 Client Portal

This portal shares a design system with the Haley365 marketing site (haley365.com) —
dark navy/blue theme, Archivo + IBM Plex type. Read this before touching `frontend/`
so new work matches the existing look instead of reinventing it.

## Stack

- `frontend/`: Vite + React + React Router + Tailwind v3 (**not** Next.js, despite
  what the top-level README's architecture diagram says — that diagram describes an
  earlier target architecture that was never actually built).
- `backend/`: FastAPI, run via Mangum on Lambda in production; run directly with
  `uvicorn app.main:app` locally/on the EC2 instance.

## Design tokens (`frontend/tailwind.config.js`)

- Colors: `page` (`#0c111e`, app bg) · `chrome` (`#0a0f1a`, header/tab bg) ·
  `panel` (`#0e1424`, card bg) · `accent` (`#2f6bff`) · `brand-light` · `icon-blue`
- Text: `ink-primary` / `ink-secondary` / `ink-muted` / `ink-faint`
- Status tones: `tone-ok` / `tone-warn` / `tone-crit` / `tone-info` / `tone-purple` /
  `tone-muted` — see `frontend/src/lib/tone.ts` for the `Tone` type and
  `toneForState()` (maps ticket/incident status strings to a tone)
- Fonts: `font-display` (Archivo, headings) · `font-sans` (IBM Plex Sans, default) ·
  `font-mono` (IBM Plex Mono, numbers/eyebrows)

## Shared components — reuse these, don't hardcode new styles

- `Logo`, `Icon` (self-hosted Material Symbols Rounded font — see
  `frontend/public/fonts/`, loaded via `@font-face` in `src/styles/index.css`)
- `Badge` — status pill, tone-mapped via `toneForState()`
- `KpiCard` — tone-colored top border, icon, big mono value, muted sub-line
- `DataTable` — dark-themed table with loading/empty states built in
- `.kpi-card` / `.section-card` / `.pill` / `.tab-btn` CSS classes in
  `frontend/src/styles/index.css`
- `Layout` — the app shell (header + tab nav); add new routes' nav entries here,
  not a one-off header per page

## Gotchas learned the hard way

- **Tailwind opacity shorthand silently no-ops on non-standard values.**
  `bg-white/7`, `border-white/12`, `bg-accent/15` etc. generate *no CSS at all* —
  Tailwind's default opacity scale only includes 0/5/10/20/25/30/40/50/60/70/75/
  80/90/95/100. For any other value use bracket syntax: `bg-white/[0.07]`. This
  broke hairline borders and translucent backgrounds across the whole app until
  caught by inspecting computed styles, not just eyeballing a screenshot.
- **Verify API field names against a real consumer before trusting an interface.**
  The ScoutDNS summary endpoint returns `allowed_requests` / `blocked_requests` /
  `threat_count` (see `DnsPage.tsx`), not `total_queries` / `blocked_queries` /
  `block_rate`. When wiring a new metric, grep for an existing page that already
  consumes that endpoint instead of guessing field names — a mismatch fails
  silently (fields just come back `undefined`) rather than erroring.
- **Production deploy path.** On the EC2 instance, the checkout nginx serves from
  and the `msp-portal` systemd service runs from is `/opt/msp-portal` — a
  *separate* clone from `~/msp-client-portal`. `deploy.sh`'s `REPO_DIR` must point
  at `/opt/msp-portal`. Deploy with `./deploy.sh` (it hardcodes the target path
  internally, so it doesn't matter which clone you run it from).
- **Design handoffs** from Claude Design arrive as a zip at the repo root (e.g.
  `Claude Code project msp portal.zip`) containing a `README.md` (the spec), a
  `.jsx` scaffold, and a standalone `.html` reference. Extract and read all three
  before implementing — the JSX is a dependency-free scaffold to convert to the
  project's actual conventions (Tailwind classes, shared components above), not
  something to ship verbatim.

## Scope note

Only the Dashboard (`/`) had a pixel-fidelity design handoff as of this writing.
AWS / Tickets / Huntress / ScoutDNS / Office 365 were re-themed to match using the
shared tokens/components above so the app doesn't look half-migrated, but their
layouts are original, not from a handoff. If a handoff arrives for one of them,
implement it directly rather than guessing at spacing/copy.
