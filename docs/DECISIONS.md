# Decisions

Dated log of decisions already made. The plan of record is [PLAN.md](PLAN.md). Newest decisions are at the top. When a newer entry replaces an older one, the older entry stays here, marked **Superseded**, so the history is readable.

Open metric questions are not listed here. They are the Decisions for Austin list in [METRICS.md](METRICS.md). Open extract questions are the TO CONFIRM list in [DATA_CONTRACT.md](DATA_CONTRACT.md). Both lists are deferred for now and do not block step 0.

## 2026-11-03 — First dashboard is an Overview

**What:** Step 2's first Superset dashboard is an Overview, modeled on screenshots of Austin's current overview page. Attendance and Behavior dashboards come later.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

## 2026-11-03 — Fixed contract, with a change process still to write

**What:** CSV file names, header names, and date formats stay fixed. Adding a new column or table to the contract needs a documented process. That process is not written yet. See "Changing the contract" in [DATA_CONTRACT.md](DATA_CONTRACT.md).

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

## 2026-11-03 — 504 status from program participation

**What:** 504 status comes from Infinite Campus `program_participation`, using the 504 program. Column details are set when the file arrives.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

## 2026-11-03 — Daily attendance is the homeroom mark

**What:** A student counts present for the day when marked present in homeroom, even if they leave during homeroom. Tardies come from Infinite Campus's overnight attendance calculation; CampusView does not recompute them. See [METRICS.md](METRICS.md).

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

## 2026-11-03 — Years kept, the Day table, and SFTP for now

**What:** Infinite Campus started in the 2025-26 school year. Keep 2025-26 and 2026-27, which matches the default history of the current year plus one prior year. Extracts are capped to dates on or after 2025-07-01. Austin will upload the Infinite Campus Day table as the calendar source; column details are set when the file arrives. Delivery is SFTP for now. A later jump box that queries Infinite Campus is logged in the [parking lot](../FEATURES.md#parking-lot), not built.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

## 2026-11-03 — Test with IC training data and keep every column

**What:** Two changes.

- **No fake-data generator.** Tests, fixtures, and the testing install use Infinite Campus (IC) training-database extracts that Austin supplies. The first sample is 23 CSV files, each with at most 1,000 rows; that cap came from the DB Hub plugin Austin used to pull them, not from the extract. They are kept outside the repo until Austin answers whether the IC vendor agreement allows them in a public repo.
- **Keep every table and column.** The loader keeps every table and column Austin's extract sends, including a state student id (`stateID`), birthdate, staff names (`referralName`), and a school's address, phone, and principal. The data contract no longer bans or drops those columns.

**Why:** Austin's words: "You don't need to build a fake data generator, because I can just get you whatever you need from the training database... I'd rather use actual data from the training database... do not drop any columns that I'm bringing in, please... in my production build, I will have that information in there because there will be tables and stuff that are built off of it."

**Who:** Austin's decision, relayed by the CampusView Engineer. Austin says the training database holds fake people.

**Status:** Proposed (relayed by CampusView Engineer; Austin confirms by merging this PR).

**Student ids in views:** Student ids, including the state id, do not need to be excluded from reporting views, though charts usually won't show them (Austin, relayed by CampusView Engineer, 2026-11-03).

**Open:** Whether the IC vendor agreement allows training-database files in the public repo. Until then they stay outside it. Whether birthdate may appear in reporting views.

**Replaces:** "Fake data only, from one deterministic generator" in the 2026-11-01 list below, and the data contract's ban on highly sensitive identifiers.

## 2026-11-02 — Two warehouse accounts, and the schema name `ref`

**What:** The installer creates two accounts for the report database, `campusview_data`:

- **`campusview_owner`** owns the database and its schemas `raw`, `ref`, and `reporting`. The loader writes as this account in step 1.
- **`campusview_reader`** can log in and connect, and can read the `reporting` schema only. Tables and views added there later are readable automatically. It cannot see `raw` or `ref`, cannot write, and cannot create anything. Superset's data connection should use it. The installer does not create that connection.

`superset_user` now owns only `superset_meta`, and cannot connect to `campusview_data`. `django_user` owns `django_app`. The passwords are in `/etc/campusview/campusview.env`.

The middle schema is named `ref`. Upgrades rename an existing `mapping` schema to `ref` automatically.

**Why:** Superset should read finished report views, not raw loaded data. A separate owner for the loader keeps writing rights away from Superset. "Mapping" already names the step that turns vendor files into CampusView's standard files, so a schema with the same name would be confusing.

**Who:** Austin asked for the read-only account, through the CampusView Engineer's scope check. The docs keeper chose the name `ref`.

**Status:** Built and merged in the installer (PR #3).

**Alternatives:** Keep `superset_user` as the owner of `campusview_data` until step 1. Set aside: Superset would have more than read access to student data. Keep the name `mapping`. Set aside: it clashes with the transform step.

**Resolves:** Open question 5, "Warehouse database users", in [PLAN.md](PLAN.md).

## 2026-11-02 — Offer nginx with HTTP or HTTPS

**What:** `install.sh` gets an optional nginx step. nginx is a web server that sits in front of the apps and is the one thing staff connect to. The wizard offers three choices:

- **Local only.** Today's behavior. Nothing listens on the network. You reach the pages through an SSH tunnel.
- **HTTP on port 80.** Plain, unencrypted web traffic.
- **HTTPS on port 443.** Encrypted, with a self-signed certificate or one you supply. Port 80 only redirects to 443.

nginx comes from the distro's own apt repo. Superset is at `/` and Django is at `/app/`. gunicorn (Superset on 127.0.0.1:8088, Django on 127.0.0.1:8000) and PostgreSQL stay on 127.0.0.1. PostgreSQL is never exposed, and DBeaver keeps using an SSH tunnel. nginx is the only thing listening on the network. Nothing else is added: no Redis, no Docker.

A re-run shows the saved choice and asks whether to change it. The default is HTTPS on port 443 with a self-signed certificate, so pressing Enter gives a server reachable by its address. Austin accepted that default when he merged PR #5 on 2026-11-02.

**Why:** Austin wants to open CampusView by the server's address from his own computer, without an SSH tunnel. His words: "build the install to allow http or https, I will reset the ct, and rerun the new installer once you have it complete."

**Who:** Austin's decision, relayed by the CampusView Engineer.

**Tradeoff:** Plain HTTP sends logins and passwords unencrypted across the network. Austin accepted that for test machines because all data there is fake ("all data would be fake"). HTTP is for test machines with fake data only. Real student data needs HTTPS.

**Status:** Built. The installer step merged to `main` in PR #5.

**Alternatives:** Local only with an SSH tunnel for everyone. Still available as one of the three choices. Deferring the proxy until later. Set aside because Austin wants network access on his test machine now.

**Resolves:** Open question 4, "Reaching it from the network", in [PLAN.md](PLAN.md).

## 2026-11-02 — Standardize on Python 3.12 for Superset and Django

**What:** Superset 6.1.0 and Django 6.1.2 both run on Python 3.12, installed and managed with `uv`. One Python version for the whole stack. Each still has its own Python environment.

**Why:** Superset 6.1.0 supports Python 3.10 through 3.12. Django 6.1 needs Python 3.12 or newer. 3.12 is the one version both accept, so the server needs only one.

**Who:** Austin's decision, relayed by the CampusView Engineer.

**Status:** Verified. Clean installs on Debian 12, Ubuntu 24.04, and Ubuntu 22.04 ran on Python 3.12.16.

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
| *Proposed to change 2026-11-03: no generator; tests use Infinite Campus training extracts. See the entry at the top.* Fake data only, from one deterministic generator. The testing install uses the same release as production. | Tests need stable answers, and real student rows must never enter the product repo. | Hand-written spreadsheets of realistic students. |
| The testing install is also the AI sandbox: read raw, write views only in a scratch schema, ship finished views as tested SQL in the repo. | Try queries without touching production. | Letting an assistant write views on the production database. |
| Named working lists have no race column. Equity is a rate per 100 students, totals only. | Staff need equity rates without a named list sorted by race. | A race column on the open-referrals list. Small-group hiding, which is parked. |
| *Deferred 2026-11-01:* card layout as an admin setting, and per-user preferences. | — | Drag-and-drop layout, which is parked. |
| One pull request per build step, merged when CI is green. Docs for a step land in that step's pull request. | The steps in the plan stay reviewable. | Mixing several steps, or documenting them later. |
| New ideas go to the parking lot in FEATURES.md. Only Austin moves one into a step. | A mid-build idea should not change the scope of the pull request that is open. | Building the idea in the current step. |
| Agents do not edit exported Superset dashboards. Those files live in the district repo. | A chart the admin exported should stay as they exported it. | Letting an agent "clean up" a dashboard file. |
