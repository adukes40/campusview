# Features

v1, in the order [PLAN.md](docs/PLAN.md) builds it. One pull request per step. A step is done when its "done when" line is true, CI is green, the data tests pass on the builder's computer and the test VM, and the docs that step touches are updated in the same pull request.

Ideas that show up while a step is open go in [Parking lot](#parking-lot). They are not built in the open step. Only Austin moves an item from the parking lot into a step.

## Step 0 — Documentation and the base install (built and merged)

- The plan, architecture, data contract, metric definitions, access model, decisions, invariants, this list, guide outlines, and the house-rules skill.
- The bare-bones base install, all at defaults: PostgreSQL 17 with the `superset_meta`, `django_app`, and `campusview_data` databases; plain Apache Superset 6.1.0 on Python 3.12 under gunicorn on 127.0.0.1:8088; a default Django 6.1.2 project on Python 3.12 under gunicorn on 127.0.0.1:8000. No Redis, no Celery, no example data, no theming.
- Optional nginx in `install.sh`: local only through an SSH tunnel, HTTP on port 80, or HTTPS on port 443 with a self-signed or supplied certificate (the default). A re-run shows the saved choice and asks whether to change it. Superset at `/`, Django at `/app/`. Decided 2026-11-02 (see [docs/DECISIONS.md](docs/DECISIONS.md)); built and merged in PR #5.
- `install.sh`: one script with a step-by-step wizard that asks for every setting, tested on clean Ubuntu and Debian machines.

Done when Austin approves the docs, and `install.sh` brings up the base install on a clean machine.

## Step 1 — Getting data in

- The SFTP drop folder.
- Standard files and mapping tables from [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md), and the raw schema in `campusview_data`.
- The loader: check every file, reject a bad file, load all or nothing. An unknown or misspelled header fails the file, and the failed load is recorded with the file, row, and rule.
- The Infinite Campus mapping onto those files.
- Test files from Infinite Campus training-database extracts that Austin supplies, kept on the builder's computer, never in the repo. No fake-data generator.
- The guide on how to write a mapping for another student information system. The mapping itself is not built.

Done when a bad file leaves the previous data in place, and a good file set replaces the snapshot in one transaction.

## Step 2 — First view and first dashboard

- The first dashboard is an Overview, modeled on screenshots of Austin's current overview page (Austin, relayed by CampusView Engineer, 2026-11-03).
- The reporting views it needs from [docs/METRICS.md](docs/METRICS.md), as SQL in this repo, each with a hand-checked test on the training extracts.
- The three starter roles in Superset, with row-level security on `school_id`.
- The Overview dashboard in Superset on those views, with native filters.
- Checked in a browser as a school admin, a district admin, and a system admin.

Done when each role sees exactly its schools on that dashboard, and each view's numbers match the hand-checked answer.

## Later steps

Order to be set by Austin.

- The rest of the reporting views in [docs/METRICS.md](docs/METRICS.md), each with a hand-checked test.
- The Attendance and Behavior dashboards in Superset, with native filters for school year, school, grade, and gender.
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
- Jump box for Infinite Campus — logged 2026-11-03 (Austin, relayed by CampusView Engineer, 2026-11-03); Austin asked for it to be logged, not built. Later, a jump box would be the only host allowed to query the Infinite Campus database. CampusView sends it scripts, it queries Infinite Campus and returns files, the files are copied to the CampusView server, and the import runs there. Until then, delivery is SFTP.
- Email alert on failed import — logged 2026-11-03, raised by Austin (Austin, relayed by CampusView Engineer, 2026-11-03); Austin asked for it, so he can promote it. Optional email to Austin through the server's existing SMTP relay, using Python `smtplib`, configured in the env file, with no new daemon (as CampusView Engineer proposed). It says what failed, why, and whether to check the server or the extract. Later because: no plan step includes alerts; step 1 records failures but does not notify anyone. Earliest step: step 1, once the loader records failures; most useful with the nightly timer.
- Redis and Celery, with a Superset worker and beat: async queries, scheduled alerts and reports, and caching — deferred 2026-11-02: bare-bones install first; revisit only if base install shows real need.

Held from the first approved plan:

- Emailed scheduled reports (would need the Redis and Celery item above)
- ClassLink sign-in
- Caseload-based access
- Small-group hiding for totals-only roles
- Mappings for other student information systems (the how-to doc is in v1; the mappings are not)
- Drag-and-drop card layout
- Trend lines and change-from-last-year on cards
