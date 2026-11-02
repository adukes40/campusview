# Decisions

Dated log of decisions already made. The plan of record is [PLAN.md](PLAN.md). Newest decisions are at the top. When a newer entry replaces an older one, the older entry stays here, marked **Superseded**, so the history is readable.

Open metric questions are not listed here. They are the Decisions for Austin list in [METRICS.md](METRICS.md). Open extract questions are the TO CONFIRM list in [DATA_CONTRACT.md](DATA_CONTRACT.md). Both lists are deferred for now and do not block step 0.

## 2026-11-02 — Standardize on Python 3.12 for Superset and Django

**What:** Superset 6.1.0 and Django 6.1.2 both run on Python 3.12, installed and managed with `uv`. One Python version for the whole stack. Each still has its own Python environment.

**Why:** Superset 6.1.0 supports Python 3.10 through 3.12. Django 6.1 needs Python 3.12 or newer. 3.12 is the one version both accept, so the server needs only one.

**Who:** Austin's decision, relayed by the CampusView Engineer.

**Status:** The clean-install check on 3.12 is pending.

**Alternatives:** Superset on Python 3.11 with Django on Python 3.13 in a separate environment. Set aside: two Python versions to install and keep patched.

## 2026-11-02 — No Redis or Celery in v1

**What:** The v1 install has no Redis server, no Celery, and no Superset worker or beat process. The `celery` and `redis` Python libraries are installed only because Superset's package list pulls them in. Nothing starts or uses them.

**Why:** Austin wants the bare-bones install first. Plain Superset runs without them. Fewer moving parts means less to install, watch, and fix.

**What this gives up for now:** Superset features that need a worker or a cache server: async queries, scheduled alerts and reports, and a shared results cache. They are in the [parking lot](../FEATURES.md#parking-lot).

**Alternatives:** Running Redis plus a Superset worker and beat from the start, as the 2026-11-01 draft did. Set aside until the base install shows a need.

## 2026-11-02 — CampusView Engineer owns engineering

**What:** The CampusView Engineer agent builds and tests the install and the code, starting with the `install.sh` setup wizard. The docs follow what the Engineer builds and tests.

**Why:** Austin asked for one owner for engineering work so two agents don't build the same thing.

## 2026-11-01 — v1 is plain Apache Superset, with no Django customizations

**What:** Staff use plain Apache Superset: its own dashboards, charts, native filters, theme settings, roles, and row-level security. There are no custom Django pages in v1. The custom filter bar, clickable cards, modal tables with export and print, student profile pages, card admin screens, per-user preferences, and the custom view log are deferred. They come back only if using the base install shows a real need.

For each reporting page, the metric logic is a PostgreSQL view whose SQL is in this repo, and the dashboard is built in Superset. Django is installed as a default project (`startproject campusview_base`) on its own database and has no part in v1 features. Later it may be, at most, a thin front door.

**Why:** A small team should own as little custom AI-written code as possible, because custom code is what breaks and has to be maintained. Superset's roles, row-level security, and no-code dashboards are already well tested by many other users.

**Alternatives:** Django-owned pages with embedded Superset charts and guest tokens, as approved earlier the same day. Set aside for now; the deferred pieces are in the [parking lot](../FEATURES.md#parking-lot).

**Supersedes:** "Django owns the pages", the Superset-only rejection inside "Keep Superset, rather than hand-built charts", the Django-to-Superset sync and one shared query path in "Also decided", and "On-premises, in containers" (the install is now native on Ubuntu or Debian).

## 2026-11-01 — Keep Superset, rather than Metabase

**What:** Charts run in Apache Superset.

**Why:** Staff must be limited to their own schools, and the install cannot add a license fee. Superset can do row-level security on a school id without a paid tier. The platform stays on-premises.

**Alternatives:** Metabase. Rejected because row-level security there is a paid feature.

## 2026-11-01 — Keep Superset, rather than hand-built charts

**What:** The system admin builds charts in Superset. Dashboards are exported as files into the district repo.

**Why:** A new chart should not require a code release. The admin can change a chart and export it again.

**Alternatives:** Hand-built charts inside Django. Rejected because every chart would become application code.

**Partly superseded (2026-11-01, plain Superset):** This entry first said Django embeds the charts and that a Superset-only screen was rejected. The plain Superset decision reverses that: Superset is now the whole screen for v1.

## 2026-11-01 — Django owns the pages (Superseded)

**Superseded by** "v1 is plain Apache Superset" above. Kept for history.

**What it said:** Django renders the pages staff open: the filter bar, the KPI cards, the modal tables, export, print, student profiles, preferences, admin screens, and all page styling. Superset charts are embedded.

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

**What:** The nightly load is a simple timed job on the server. It does not use Celery. (The first draft said a Django management command. Since Django has no role in v1, the exact form of the job is chosen in the loader step.)

**Why:** The load is one job: read a folder, check the files, write one transaction. A queue does not make that simpler.

**Alternatives:** A Celery task for the load. Rejected because the load would depend on a queue and a worker. As of 2026-11-02 there is no Celery in v1 at all.

## 2026-11-01 — Also decided

These were approved in the same plan. Each is the rule the build follows. Rows changed by the plain Superset decision are marked.

| Decision | Why | Alternative set aside |
| --- | --- | --- |
| Infinite Campus is the only mapping built and tested in v1. Docs explain how to write another. | One real extract is enough to prove the contract. | Building several SIS mappings up front. |
| Google sign-in now. *Open since 2026-11-01: plain Superset does not do this out of the box. See the open questions in [PLAN.md](PLAN.md).* | The district can use accounts it already has. | ClassLink, which is parked. Local passwords as the main sign-in. |
| History defaults to the current school year plus one prior year, then purges. | Attendance needs a last-year comparison. Unbounded history is unnecessary for v1. | Keeping every year, or keeping only the current year. |
| All metric logic lives in PostgreSQL reporting views. Charts only filter and aggregate those views. | A number is defined once. | Computing metrics in Python or inside each chart. |
| Materialize a view only after a query is proven slow. | Ordinary views stay correct for "today" without a refresh job. | Materializing everything at the start. |
| Default deny. SQL Lab and chart building only for system admin. *Changed 2026-11-01: roles and school limits now live in Superset (roles plus row-level security). The Django access list and its sync are deferred.* | Staff see only their schools. | Editing access in two places. |
| *Deferred 2026-11-01:* profile views and named exports go to an append-only log. | Named student data needs a record of who looked. | — |
| A permissions test covers every role on every place data can be reached. *Now that means Superset.* | A school boundary that is only checked by hand will be skipped. | Manual checking before each release. |
| Fake data only, from one deterministic generator. The testing install uses the same release as production. | Tests need stable answers, and real student rows must never enter the product repo. | Hand-written spreadsheets of realistic students. |
| The testing install is also the AI sandbox: read raw, write views only in a scratch schema, ship finished views as tested SQL in the repo. | Try queries without touching production. | Letting an assistant write views on the production database. |
| Named working lists have no race column. Equity is a rate per 100 students, totals only. | Staff need equity rates without a named list sorted by race. | A race column on the open-referrals list. Small-group hiding, which is parked. |
| *Deferred 2026-11-01:* card layout as an admin setting, and per-user preferences. | — | Drag-and-drop layout, which is parked. |
| One pull request per build step, merged when CI is green. Docs for a step land in that step's pull request. | The steps in the plan stay reviewable. | Mixing several steps, or documenting them later. |
| New ideas go to the parking lot in FEATURES.md. Only Austin moves one into a step. | A mid-build idea should not change the scope of the pull request that is open. | Building the idea in the current step. |
| Agents do not edit exported Superset dashboards. Those files live in the district repo. | A chart the admin exported should stay as they exported it. | Letting an agent "clean up" a dashboard file. |
