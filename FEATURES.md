# Features

v1, in the order [PLAN.md](docs/PLAN.md) builds it. One pull request per step. A step is done when its "done when" line is true, CI is green, and the docs that step touches are updated in the same pull request.

Ideas that show up while a step is open go in [Parking lot](#parking-lot). They are not built in the open step. Only Austin moves an item from the parking lot into a step.

## Step 0 — Documentation and the base install (in progress)

- The plan, architecture, data contract, metric definitions, access model, decisions, invariants, this list, guide outlines, and the house-rules skill.
- The bare-bones base install, all at defaults: PostgreSQL 17 with the `superset_meta`, `django_app`, and `campusview_data` databases; plain Apache Superset 6.1.0 on Python 3.12 under gunicorn on 127.0.0.1:8088; a default Django 6.1.2 project on Python 3.12 under gunicorn on 127.0.0.1:8000. No Redis, no Celery, no example data, no theming.
- Optional nginx in `install.sh`: local only (the default), HTTP on port 80, or HTTPS on port 443. Superset at `/`, Django at `/app/`. Decided 2026-11-02 (see [docs/DECISIONS.md](docs/DECISIONS.md)); the installer step is in progress.
- `install.sh`: one script with a step-by-step wizard that asks for every setting, tested on clean Ubuntu and Debian machines.

Done when Austin approves the docs, and `install.sh` brings up the base install on a clean machine.

## Step 1 — Getting data in

- The SFTP drop folder.
- Standard files and mapping tables from [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md), and the raw schema in `campusview_data`.
- The loader: check every file, reject a bad file, load all or nothing.
- The Infinite Campus mapping onto those files.
- The deterministic fake-data generator: 1 high school, 1 middle school, 2 elementary schools, about 25 to 40 students each, one school year of days, a scatter of referrals, a few 504s and IEPs with some expiring soon. Scaling the school count is a one-line change. Production refuses to run the generator.
- The guide on how to write a mapping for another student information system. The mapping itself is not built.

Done when a bad file leaves the previous data in place, and a good file set replaces the snapshot in one transaction.

## Step 2 — First view and first dashboard

- The first reporting view from [docs/METRICS.md](docs/METRICS.md), as SQL in this repo, with a hand-checked test on fake data.
- The three starter roles in Superset, with row-level security on `school_id`.
- The first Superset dashboard on that view, with native filters.
- Checked in a browser as a school admin, a district admin, and a system admin.

Done when each role sees exactly its schools on that dashboard, and the view's numbers match the hand-checked answer.

## Later steps

Order to be set by Austin.

- The rest of the reporting views in [docs/METRICS.md](docs/METRICS.md), each with a hand-checked test.
- The Overview, Attendance, and Behavior dashboards in Superset, with native filters for school year, school, grade, and gender.
- The loader on a nightly timer, with the history purge. History kept is a setting, default the current school year plus one prior year.
- An adversarial review that tries to break school limits, the loader's all-or-nothing rule, and the "no real student data" rule. Each fix includes a test.

## Parking lot

Not in v1 unless Austin promotes one.

- Custom Django pages for Overview, Attendance, and Behavior — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Custom Django filter bar shared by cards and charts — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Clickable KPI cards — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Modal tables of the rows behind a card, with CSV export and print — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Student profile pages (attendance, behavior, and plan info for one student) — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Custom append-only view and export log — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Card admin screens (which cards, order, on or off) — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Per-user preferences (default school, theme, saved filters, card order) — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Django access list with a sync to Superset roles and school filters — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Embedded Superset charts in Django pages, with guest tokens — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- One shared Django query path for cards, modals, exports, and profiles — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Django as a thin front door to Superset — deferred 2026-11-01: plain Superset first; revisit only if base install shows real need.
- Redis and Celery, with a Superset worker and beat: async queries, scheduled alerts and reports, and caching — deferred 2026-11-02: bare-bones install first; revisit only if base install shows real need.

Held from the first approved plan:

- Emailed scheduled reports (would need the Redis and Celery item above)
- ClassLink sign-in
- Caseload-based access
- Small-group hiding for totals-only roles
- Mappings for other student information systems (the how-to doc is in v1; the mappings are not)
- Drag-and-drop card layout
- Trend lines and change-from-last-year on cards
