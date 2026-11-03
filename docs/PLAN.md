# CampusView v1 plan

This is the source of truth for v1. Austin approved the first version on November 1, 2026. Later that day he changed it to plain Apache Superset with no Django customizations, and he confirmed that on November 2, 2026. The other documents explain how to build it. If they disagree with this plan, this plan wins. The reasons for each change are in [DECISIONS.md](DECISIONS.md).

## What it is

CampusView is a self-hosted, district-agnostic K-12 reporting platform. It loads student-information-system extracts every night, turns them into attendance, behavior, and 504/IEP reporting, and shows dashboards to district and school staff. Each person sees only the schools they cover.

Nothing organization-specific belongs in the code. Names, schools, code values, branding, and years are supplied at install time or kept in the district repo.

- The first student information system is Infinite Campus, via CSV extracts dropped on SFTP. Another system is supported by writing a mapping to CampusView's own standard file layouts: students, enrollments, attendance, incidents and referrals, 504/IEP plans, schools, and calendar. v1 builds and tests only the Infinite Campus mapping, plus docs on how to write another mapping.
- The district may not allow a direct connection to the student information system. Files are the only way data comes in.
- Loads run nightly. How much history to keep is a setting. The default is the current school year plus one prior year. Older data is purged on load.
- The install is on-premises, installed directly on an Ubuntu or Debian server (no containers), with no license costs.
- No student data in code, tests, examples, or commits. Fake data only. The Infinite Campus training database is completely fictional, so it counts as fake data and needs no PII or PHI removal (Austin, relayed by CampusView Engineer, 2026-11-03). Its files never go in the public repo.

## The screen staff use: plain Superset

Staff open Apache Superset dashboards. v1 uses only what Superset already has: dashboards, charts, native filters, theme settings, roles, and row-level security. There are no custom Django pages.

The custom pieces from the first draft are deferred, not cancelled: the custom filter bar, clickable cards that open a modal table with export and print, student profile pages, card admin screens, per-user preferences, and the custom view log. Each comes back only if using the base install shows a real need. They are listed in the [parking lot](../FEATURES.md#parking-lot).

Why: a small team should own as little custom AI-written code as possible. Superset's roles, row-level security, and no-code dashboards are already battle-tested.

## Data flow

SIS extracts (CSV on SFTP) go to an SIS mapping, then to a validated loader. The loader checks every file before loading. Each load is all or nothing. The loader writes a raw schema: every table and column the contract lists. Nothing is dropped, and an unknown header fails the file with a clear report.

Reporting views in PostgreSQL sit on top of the raw schema. All metric logic lives in those views, and the SQL for every view is kept in this repo. The views use code-mapping tables from the district repo. Every view can be filtered by school and school year. No view filters itself.

Superset dashboards read those views. For each reporting page: first the PostgreSQL view, then the Superset dashboard on top of it.

SFTP is not built yet. The loader reads a folder of Infinite Campus CSV files into `raw`.

## Stack

The base install, all at default settings:

| Piece | Version and setup | Listens on |
| --- | --- | --- |
| PostgreSQL | 17, from the official PostgreSQL apt repo (PGDG, added over https with its signing key), listening on 127.0.0.1 only. Three databases: `superset_meta` (Superset's own settings), `django_app` (Django's own tables), `campusview_data` (the warehouse) | 127.0.0.1:5432 |
| Apache Superset | 6.1.0 on Python 3.12 (managed with `uv`; verified on 3.12.16), under gunicorn. Installed with Superset's own tested package list (`requirements/base.txt` from the 6.1.0 release) as pip constraints | 127.0.0.1:8088 |
| Django | 6.1.2 on the same Python 3.12, in its own Python environment, under gunicorn. A default `startproject campusview_base` on the `django_app` database | 127.0.0.1:8000 |

- **PostgreSQL** is the warehouse. It holds the raw schema and the reporting schema. A view is materialized only after a query is proven slow.
- **Apache Superset** is the screen staff use. The system admin builds the charts and dashboards. Dashboards are exported to the district repo as files.
- **Django** has no role in v1 features. It is installed as a default project so it is ready if a thin front door is needed later.
- **No Redis and no Celery.** There is no Redis server, no Celery, and no Superset worker or beat process. The `celery` and `redis` Python libraries are present only because Superset's package list installs them.
- **nginx, optional.** The installer can add nginx from the distro's apt repo as the one network entry point. The wizard offers local only through an SSH tunnel, HTTP on port 80, or HTTPS on port 443 with a self-signed or supplied certificate. A re-run shows the saved choice and asks whether to change it. Superset is at `/` and Django at `/app/`. The pieces above stay on 127.0.0.1 either way. HTTPS with a self-signed certificate is the default. This is part of step 0's base install and is in the installer on `main`. See [DECISIONS.md](DECISIONS.md), 2026-11-02, "Offer nginx with HTTP or HTTPS".
- **No SFTP, no example data, and no theming** in the base install yet.
- **The installer** is one script, `install.sh`, with a step-by-step wizard that asks for every setting it needs. The CampusView Engineer built it, and it passed clean installs and re-runs on Debian 12, Ubuntu 24.04, and Ubuntu 22.04. It is merged to `main`.
- **Secrets** go in one server file, `/etc/campusview/campusview.env` (mode 600, owned by the account that runs CampusView). systemd or `start.sh` loads it, and the Superset and Django config files read secrets from the environment.

## Access control

Three starter roles. They are Superset roles, managed in Superset.

- **System admin:** everything. This is the only role that builds dashboards, uses SQL Lab, and manages users and settings.
- **District admin:** views all schools and changes nothing.
- **School admin:** views only the assigned school IDs.

Rules:

1. Default deny. No role, or no school, means no rows.
2. School limits use Superset's row-level security on `school_id`.
3. SQL Lab and chart building are off for every role except system admin.
4. A permissions test checks every role against every place data can be reached in Superset.

The Django access list, the Django-to-Superset sync, guest tokens, and the shared Django query path are deferred along with the Django pages. Details are in [ACCESS.md](ACCESS.md).

## Repos and releases

- **Product repo** `adukes40/campusview`: generic code and SQL only. Changes go to the `dev` branch (`main` plus the new changes) and merge to `main` when CI passes and Austin has checked them on the dev server. Releases are tags such as `v1.3.0`, cut from `main`. Production pins a tag (CampusView Engineer's reading of Austin's reply, 2026-11-03). The dev server follows `dev`. No server pulls `main`.
- **Private district repo** `adukes40/campusview-district`: that district's settings, code mappings, branding, and exported dashboards. Upgrades never overwrite it. It holds no secrets.
- **Dev server:** follows `dev` and holds real district data, so Austin sees how a change will look (Austin, relayed by CampusView Engineer, 2026-11-03). It follows production rules for data and access: no sandbox user, no training files, no agent access.
- **Testing install:** the builder's own computer, or a separate fake-data server later, loaded with Infinite Campus training-database extracts that Austin supplies. Never the dev server. It also serves as an AI query sandbox. The AI gets its own database user that can read raw tables and build views in a scratch schema only. Finished views become SQL in the repo with hand-checked tests and ship through releases. They are never copy-pasted to production.

## Build order

One pull request per step. Merge when CI is green, the data tests pass on the builder's computer, and Austin has checked the change on the dev server. CI on GitHub runs only the tests that need no data files (Austin, relayed by CampusView Engineer, 2026-11-03). CI is built in step 1; until it exists, "CI is green" cannot be checked, and the builder runs the same no-data tests on its own computer.

| Step | Work | Done when |
| --- | --- | --- |
| 0 | Docs, plus the bare-bones base install: PostgreSQL 17, plain Superset 6.1.0, default Django 6.1.2, and the `install.sh` wizard. **Built and merged.** | Austin approves the docs, and `install.sh` brings up the base install on a clean Ubuntu or Debian machine |
| 1 | Getting data in: the SFTP drop, the raw schema, the validated loader, and the Infinite Campus mapping. Test files are Infinite Campus training-database extracts that Austin supplies, kept on the builder's computer. Also the release plumbing Austin moved into current work (Austin, relayed by CampusView Engineer, 2026-11-03): the district folder on each server and the mappings layout in the district repo; a product checkout on each server with a setting for the branch or tag it follows; an update command; and a `dev` branch with basic CI | Bad files are rejected with a clear report, each load is all or nothing, every column the contract lists is kept, a good drop built from the training extracts loads, the dev server follows `dev` and updates with the update command, and CI runs the no-data tests |
| 2 | The first reporting views in PostgreSQL and the first Superset dashboard on them: an Overview, modeled on screenshots of Austin's current overview page (Austin, relayed by CampusView Engineer, 2026-11-03), with the three roles and school row-level security set up and checked | Each role sees exactly its schools on that dashboard, and each view's numbers match a hand-checked answer on the training extracts |

Later steps, in an order Austin will set: the rest of the reporting views and the Attendance and Behavior dashboards; the nightly schedule and the history purge; and an adversarial review with fixes. Each new number gets a view and a hand-checked test before it gets a chart.

## Dashboard design

These are the numbers and charts v1 aims for. In plain Superset, a "card" is a big-number chart and a list is a table chart.

- Overview: year-to-date attendance rate, absent on the last school day (the chart names the day), referrals not yet processed, average days to resolve or action, active 504s and IEPs with counts of those expiring in 30 days, top 10 referred students, top 10 behavior types, and the open referrals list.
- Behavior: trends by month, grade, location, and time; a heatmap of location by time of day; consequences; repeat referrals; equity.
- Attendance: rates and a monthly trend against last year; chronic absenteeism rate by grade; unexcused absences; tardies.
- Top behavior types are horizontal bars, largest first.
- The open referrals list is color-coded by days open. Named working lists have no race column.
- Equity is rates per 100 students per group, totals only.
- Filters are Superset native filters: school year, school, grade, and gender.

## Test data

There is no fake-data generator. Tests and the testing install use Infinite Campus training-database extracts that Austin supplies. The training database is completely fictional, so it counts as fake data (Austin, relayed by CampusView Engineer, 2026-11-03). The files never go in the public repo. They are only for building. They stay on the builder's computer, and Austin can pull them again. Austin supplies whatever files a test needs.

Workflow: build and test on the builder's computer, push to `dev`, Austin checks the dev server, merges `dev` into `main`, and a tag is cut for production. See [DECISIONS.md](DECISIONS.md), "Release flow". CI on GitHub cannot use the training files, so it runs only the tests that need no data files. Tests that need data, including every hand-checked metric answer, run on the builder's computer, or a fake-data server if one is set up. They never run on the dev server, which holds real data.

The loader keeps every column the contract lists. The first sample was 23 CSV files with at most 1,000 rows each; that cap came from the DB Hub plugin Austin used to pull them, not from the extract. See [DECISIONS.md](DECISIONS.md), 2026-11-03.

## Guarding against unwanted changes

- Dashboards are exported from Superset into the district repo. AI agents never edit those exports.
- Every metric has a test with a hand-checked answer, run on the builder's computer.
- Every release is tested as an upgrade from the previous release.
- New ideas go to the FEATURES.md parking lot. Only Austin promotes them into the build.

## Docs built as we go

A step is not done until its docs are. The guides are: server requirements; install and upgrade; sign-in setup; accounts, roles, and school assignments; SFTP and extract setup, plus writing a mapping for another SIS; building and exporting dashboards in Superset; backups and restore.

## Open questions

Not answered yet. Nobody should guess these; Austin decides.

1. **School assignments.** Without the Django-to-Superset sync, how does each school admin's list of schools get kept up to date in Superset's roles and row-level security? By hand in Superset, or some other way?
2. **Google sign-in.** *Answered (Austin, relayed by CampusView Engineer, 2026-11-03): a future item, not in the plan. Parked in [FEATURES.md](../FEATURES.md#parking-lot). When it arrives, the dev server moves to HTTPS first.* The first draft had Google sign-in through Django. Plain Superset uses its own login.
3. **Downloads and a view log.** With the Django exports and the custom view log deferred, should staff be able to download rows from Superset, and is any record of who looked at named rows needed in v1? (This is decision 24 in [METRICS.md](METRICS.md).)
4. **Reaching it from the network.** *Decided 2026-11-02.* The installer offers three choices: local only through an SSH tunnel, HTTP on port 80, or HTTPS on port 443 with a self-signed or supplied certificate (the default). See "Offer nginx with HTTP or HTTPS" in [DECISIONS.md](DECISIONS.md).
5. **Warehouse database users.** *Resolved 2026-11-02.* The installer creates `campusview_owner` (owns `campusview_data` and its schemas; the loader writes as it) and `campusview_reader` (reads `reporting` only; Superset's data connection should use it). `superset_user` no longer touches `campusview_data`. See [ACCESS.md](ACCESS.md) and [DECISIONS.md](DECISIONS.md).

The 25 Decisions for Austin in [METRICS.md](METRICS.md) and the 18 TO CONFIRM extract questions in [DATA_CONTRACT.md](DATA_CONTRACT.md) are kept, but they are **deferred**: they do not block step 0 or the base install.

## Parked for later

Everything in the [parking lot](../FEATURES.md#parking-lot): the deferred Django pages and screens, Redis and Celery (async queries, alerts and reports, caching), emailed scheduled reports, Google sign-in, ClassLink sign-in, caseload-based access, small-group hiding for totals-only roles, mappings for other student information systems, drag-and-drop card layout, and trend lines and change-from-last-year on cards.
