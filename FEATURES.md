# Features

v1, in the order [PLAN.md](docs/PLAN.md) builds it. One pull request per step. A step is done when its "done when" line is true, CI is green, the data tests pass on the builder's computer, Austin has checked it on the dev server, and the docs that step touches are updated in the same pull request.

Ideas that show up while a step is open go in [Parking lot](#parking-lot). They are not built in the open step. Only Austin moves an item from the parking lot into a step.

## Step 0 — Documentation and the base install (built and merged)

- The plan, architecture, data contract, metric definitions, access model, decisions, invariants, this list, guide outlines, and the house-rules skill.
- The bare-bones base install, all at defaults: PostgreSQL 17 with the `superset_meta`, `django_app`, and `campusview_data` databases; plain Apache Superset 6.1.0 on Python 3.12 under gunicorn on 127.0.0.1:8088; a default Django 6.1.2 project on Python 3.12 under gunicorn on 127.0.0.1:8000. No Redis, no Celery, no example data, no theming.
- Optional nginx in `install.sh`: local only through an SSH tunnel, HTTP on port 80, or HTTPS on port 443 with a self-signed or supplied certificate (the default). A re-run shows the saved choice and asks whether to change it. Superset at `/`, Django at `/app/`. Decided 2026-11-02 (see [docs/DECISIONS.md](docs/DECISIONS.md)); built and merged in PR #5.
- `install.sh`: one script with a step-by-step wizard that asks for every setting, tested on clean Ubuntu and Debian machines.

Done when Austin approves the docs, and `install.sh` brings up the base install on a clean machine.

## Step 1 — Getting data in

- The SFTP drop folder.
- The code-mapping tables from [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md), and the raw schema in `campusview_data`.
- The loader: check every file, reject a bad file, load all or nothing. An unknown or misspelled header fails the file, and the failed load is recorded in `ops.load_batch` with the files that failed and the reason, plus the line number when PostgreSQL rejects a row.
- The typed, checked copy of each raw table. It keeps the Infinite Campus table and column names, with real dates and numbers, in schema `ic`. Bad keys and unknown codes are warnings on the load report, and loading continues. Built in PR #14 (merge commit e06c651), except the checks listed under "Not yet" below.
- Test files from Infinite Campus training-database extracts that Austin supplies, kept on the builder's computer, never in the repo. No fake-data generator.
- The guide on how to write a mapping for another student information system. The mapping itself is not built. How another system fits, now that the Infinite Campus names are kept, is not decided.
- Release plumbing, moved into current work by Austin (Austin, relayed by CampusView Engineer, 2026-11-03):
  - The district folder on each server, and a setting for it (proposed `/opt/campusview-district`).
  - The mappings layout in the district repo. The ten code-mapping files sit at the checkout root, and the loader reads that directory.
  - A product checkout on each server, with a setting for the branch or tag it follows: `dev` on the dev server, a tag on production.
  - An update command: pull the product ref and the district repo (fast-forward only), run migrations, restart, and leave the env file and the SFTP drop alone.
  - A `dev` branch and basic CI on GitHub. CI runs only the tests that need no data.
- Moved into step 1 (Austin, relayed by CampusView Engineer, 2026-11-03 7:04 PM ET): "Move the nightly timer and old-data cleanup into Step 1."
  - The loader on a nightly timer. Proposed by CampusView Engineer: a systemd timer that `install.sh` installs, run as `CV_RUN_USER` with the loader connecting as `campusview_owner`, nightly at 02:00 in the district time zone with `Persistent=true`, loading from the drop folder PR #20 settles. Existing servers get it through one full `install.sh` run. Only when `CV_SYSTEMD=yes`; what a `start.sh` server gets is to confirm.
  - The cleanup of old extract files in the SFTP drop (Austin, relayed by CampusView Engineer, 2026-11-03 7:30 PM ET). The warehouse keeps data dated on or after the district cutoff date, set in the district repo, and is not purged by school year. `ops.load_batch` keeps every row. It keeps 7 nights of drop files, then deletes older ones (Austin, relayed by CampusView Engineer, 2026-11-03 7:33 PM ET). Whether 7 is a fixed product value or a district setting is to confirm.

So far: the CSV loader for the Infinite Campus extracts (PR #10, commit 2f21b49), the `dev` branch, basic GitHub CI (`.github/workflows/ci.yml`), and the product checkout with its branch or tag setting (`CV_REF`) and the update command (`install.sh --update`, PR #12, commit d5b6890), the typed copy in schema `ic` (PR #14, merge commit e06c651), and the ten code-mapping tables in schema `ref` (PR #17, merge commit 856bf34). The mappings layout is the ten files at the district repo root. The loader takes the district path as an argument. CI runs the loader tests. The loader tests that need a database skip there. The update command pulls `/opt/campusview-district` only when that folder is already a git checkout. It does not create or clone it. Not yet: SFTP, the impossible referral-flag check, creating the district folder or a setting for it, the nightly timer, and the drop cleanup. The loader runs by hand today.

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
- Pick up district settings after a pull — logged 2026-11-03, raised by CampusView Keeper from the PR #9 scoping. Reload or restart so new branding and settings take effect after the district repo is pulled. Later because: mappings are read on every load, and branding and settings do not exist yet. Earliest step: when branding or district settings are built.
- Installer clones the district repo with a deploy key — logged 2026-11-03, raised by CampusView Keeper from the PR #9 scoping. The installer makes the read-only deploy key and clones the district repo. Later because: the manual steps in the repos guide work today. Earliest step: after step 1's district folder and update command.
- Secret scan in CI — logged 2026-11-03, raised by CampusView Keeper from the PR #9 scoping. A CI check that fails a push carrying a password, key, or token, in the product repo and the district repo. Later because: basic CI comes first, in step 1. Earliest step: after step 1's basic CI.
- Load-report warnings that say which cards an empty file blanks — logged 2026-11-03, raised by Austin. For example: "behavior_type is empty, so behavior labels will be blank." Later because: off-step for Step 1; useful once the typed copy and dashboards exist; Austin can promote it.
- Hover info on each report explaining how its data is calculated — logged 2026-11-03, raised by Austin (1:17 PM ET). A small info icon on each report or card; hovering shows how the numbers are calculated, and it can draw on [docs/METRICS.md](docs/METRICS.md). In his words: "that doesn't need to be in this version. One that can be after we get our first full dashboard up and running." Later because: Austin wants it after the first full dashboard is up and running.
- Deploy the reporting views with each load — logged 2026-11-03, raised by CampusView Engineer. The loader, as `campusview_owner` and inside the load transaction, drops the `reporting` views, rebuilds `ic`, recreates the views from one `reporting.sql` in the product checkout, and grants `SELECT` to `campusview_reader`. It answers three gaps: `install.sh --update` never runs the warehouse block, `loader/typed.py` drops `ic` tables without `CASCADE` so a view on `ic` would fail the next load, and objects the installer creates as the PostgreSQL superuser are not covered by the reader's default grant. Later because: no reporting view exists until step 2, and the docs say only that a view "arrives through a release", not what creates it. Earliest step: step 2, before the first view.
- Redis and Celery, with a Superset worker and beat: async queries, scheduled alerts and reports, and caching — deferred 2026-11-02: bare-bones install first; revisit only if base install shows real need.

Held from the first approved plan:

- Emailed scheduled reports (would need the Redis and Celery item above)
- Google sign-in (SSO) — logged 2026-11-03, raised by Austin (relayed by CampusView Engineer). Staff sign in to Superset with their district Google accounts. Later because: Austin confirmed it is a future item, not in the plan; v1 uses Superset's own login. Earliest step: after the v1 steps, once real users are coming. Before it is turned on, the dev server moves to HTTPS. Outline: [docs/guides/google-oauth.md](docs/guides/google-oauth.md).
- ClassLink sign-in
- Caseload-based access
- Small-group hiding for totals-only roles
- Mappings for other student information systems (the how-to doc is in v1; the mappings are not)
- Drag-and-drop card layout
- Trend lines and change-from-last-year on cards
