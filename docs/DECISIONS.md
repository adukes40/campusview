# Decisions

Dated log of decisions already made in [PLAN.md](PLAN.md), which Austin approved on November 1, 2026. Open metric questions are not listed here. They are the Decisions for Austin list in [METRICS.md](METRICS.md). Open extract questions are the TO CONFIRM list in [DATA_CONTRACT.md](DATA_CONTRACT.md).

## 2026-11-01 — Keep Superset, rather than Metabase

**What:** Charts run in Apache Superset.

**Why:** Staff must be limited to their own schools, and the install cannot add a license fee. Superset can do row-level security on a school id without a paid tier. The platform stays on-premises.

**Alternatives:** Metabase. Rejected because row-level security there is a paid feature.

## 2026-11-01 — Keep Superset, rather than hand-built charts

**What:** The system admin builds charts in Superset. Django embeds them. Dashboards are exported as files into the district repo.

**Why:** A new chart should not require a code release. The admin can change a chart and export it again.

**Alternatives:** Hand-built charts inside Django. Rejected because every chart would become application code. A Superset-only screen was also shown and rejected: its number cards are not clickable, an export of a card does not honor the filters, and the look depends on custom CSS that can break when Superset is upgraded.

## 2026-11-01 — Django owns the pages

**What:** Django renders the pages staff open. That is the filter bar, the KPI cards, the modal tables, export, print, student profiles, preferences, admin screens, and all page styling.

**Why:** Those interactions are the product, and they need one shared place to apply school limits and to write the audit log. Superset's built-in theme is enough for the embedded charts, with minimal custom CSS.

**Alternatives:** Letting Superset own the whole screen. Rejected for the reasons in the previous decision. Letting each page query the database on its own. Rejected because the school rule would be copied in more than one place.

## 2026-11-01 — Files are the only ingest

**What:** Data arrives as CSV extracts on SFTP. A mapping step turns the vendor files into CampusView's standard layouts. The loader validates every file and loads all or nothing.

**Why:** The district may not allow a direct connection to the student information system. Files work for Infinite Campus now and for another system later, with a new mapping and no change to the warehouse.

**Alternatives:** A live connection to the vendor database, or a vendor API. Rejected because the district may not permit them, and because v1 would then depend on one vendor's connection.

## 2026-11-01 — Tag-based releases

**What:** Work merges to `main` only when CI passes. A release is a tag such as `v1.3.0`. The live server pulls tags and does not pull raw `main`.

**Why:** Production should move only when a release has been cut, and CI has already installed that release. Day-to-day branch state stays off the server.

**Alternatives:** Deploying `main` directly. Rejected because a merge would reach the server before anyone had called it a release.

## 2026-11-01 — A separate district repo

**What:** Generic code lives in `adukes40/campusview`. Settings, code mappings, branding, and exported dashboards live in the private repo `adukes40/campusview-district`. Upgrades never overwrite the district repo. That repo holds no secrets.

**Why:** Nothing about one district belongs in the product. An upgrade that replaced district files would wipe local codes and dashboards. Secrets belong on the server, not in a repo.

**Alternatives:** A config folder inside the product repo, or district settings stored only on the server with no history. Rejected because the product repo would stop being generic, or because mappings and dashboards would have no history and no review.

## 2026-11-01 — No Celery for loads

**What:** The nightly load is a timed Django management command. Celery and Redis run only because Superset needs them.

**Why:** The load is one job: read a folder, check the files, write one transaction. A queue does not make that simpler. Keeping the load off Celery means a Superset worker problem cannot block or double-run the night's file.

**Alternatives:** A Celery task for the load, sharing Superset's Redis. Rejected because the load would depend on the charting stack.

## 2026-11-01 — Also decided

These were approved in the same plan. Each is the rule the build follows.

| Decision | Why | Alternative set aside |
| --- | --- | --- |
| Infinite Campus is the only mapping built and tested in v1. Docs explain how to write another. | One real extract is enough to prove the contract. | Building several SIS mappings up front. |
| Google sign-in now. | The district can use accounts it already has. | ClassLink, which is parked. Local passwords as the main sign-in. |
| History defaults to the current school year plus one prior year, then purges. | Attendance needs a last-year comparison. Unbounded history is unnecessary for v1. | Keeping every year, or keeping only the current year. |
| All metric logic lives in PostgreSQL reporting views. Pages and charts only filter and aggregate those views. | A number is defined once, and both Django and Superset show that number. | Computing metrics in Python or inside each chart. |
| Materialize a view only after a query is proven slow. | Ordinary views stay correct for "today" without a refresh job. | Materializing everything at the start. |
| One access list in Django, default deny, synced to Superset. SQL Lab and chart building only for system admin. | Two hand-maintained access lists will drift. | Editing Superset permissions by hand. |
| Profile views and named exports go to an append-only log. | Named student data needs a record of who looked. | A log that can be edited, or no log. |
| A permissions test in CI covers every role on every data path. | A school boundary that is only checked by hand will be skipped. | Manual checking before each release. |
| Fake data only, from one deterministic generator. The testing install uses the same release as production. | Tests need stable answers, and real student rows must never enter the product repo. | Hand-written spreadsheets of realistic students. |
| The testing install is also the AI sandbox: read raw, write views only in a scratch schema, ship finished views as tested migrations. | Try queries without touching production, and without pasting SQL into a server. | Letting an assistant write views on the production database. |
| Named working lists have no race column. Equity is a rate per 100 students, totals only. | Staff need equity rates without a named list sorted by race. | A race column on the open-referrals list. Small-group hiding, which is parked. |
| Card layout is an admin setting: which cards, order, on or off. Per user: default school, theme, saved filters, card order. | The district decides the standard layout. Each person can still arrange their own view. | Drag-and-drop layout, which is parked. |
| One pull request per build step, merged when CI is green. Docs for a step land in that step's pull request. | The steps in the plan stay reviewable. | Mixing several steps, or documenting them later. |
| New ideas go to the parking lot in FEATURES.md. Only Austin moves one into a step. | A mid-build idea should not change the scope of the pull request that is open. | Building the idea in the current step. |
| Agents do not edit exported Superset dashboards. Those files live in the district repo. | A chart the admin exported should stay as they exported it. | Letting an agent "clean up" a dashboard file. |
