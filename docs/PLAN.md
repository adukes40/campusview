# CampusView v1 plan

Approved by Austin on November 1, 2026. This is the source of truth for v1. The other documents explain how to build it. If they disagree with this plan, this plan wins.

## What it is

CampusView is a self-hosted, district-agnostic K-12 reporting platform. It loads student-information-system extracts every night, turns them into attendance, behavior, and 504/IEP reporting, and shows dashboards to district and school staff. Each person sees only the schools they cover.

Nothing organization-specific belongs in the code. The installer supplies names, schools, code values, branding, and years.

- The first student information system is Infinite Campus, via CSV extracts dropped on SFTP. Another system is supported by writing a mapping to CampusView's own standard file layouts: students, enrollments, attendance, incidents and referrals, 504/IEP plans, schools, and calendar. v1 builds and tests only the Infinite Campus mapping, plus docs on how to write another mapping.
- The district may not allow a direct connection to the student information system. Files are the only way data comes in.
- Loads run nightly. How much history to keep is a setting. The default is the current school year plus one prior year. Older data is purged on load.
- Sign-in is Google OAuth for now. ClassLink is parked.
- The install is on-premises, in containers, with no license costs.
- No student data in code, tests, examples, or commits. Fake data only.

## Data flow

SIS extracts (CSV on SFTP) go to an SIS mapping, then to a validated loader. The loader checks every file before loading. Each table loads all or nothing. The loader writes a raw schema: the standard layouts, with explicit columns, and without free-text narratives or highly sensitive identifiers.

Reporting views in PostgreSQL sit on top of the raw schema. All metric logic lives in those views. The views use installer-supplied code-mapping tables. Every view can be filtered by school and school year. No view filters itself.

Both Superset charts and Django pages read those views.

## Stack

- **PostgreSQL** is the warehouse. It holds the raw schema and the reporting schema. A view is materialized only after a query is proven slow.
- **Django** owns the pages staff open. That includes one filter bar, clickable KPI cards that open a modal with the filtered rows (export CSV and print), student profile pages, the single access list, the view and export audit log, admin screens, per-user preferences (default school, theme, saved filters, card order), and card config (which cards, their order, and on or off). All page styling lives in Django.
- **Apache Superset** charts are built by the system admin and embedded in Django pages with Superset's embedded SDK and guest tokens. The charts obey the same filter bar and the same per-person school limits. Charts match the page through Superset's built-in theme, with minimal custom CSS. Dashboards are exported to the district repo as files.
- **Celery and Redis** are present only because Superset needs them. The nightly load is a simple timed Django management command.
- **The installer** is one script. It installs Docker if Docker is missing, asks for settings, starts everything, and runs upgrades.

## Access control

Roles have installer-defined defaults. They can be renamed and extended. Nothing about role names is fixed in code.

- **System admin:** everything. This is the only role that builds dashboards and manages users and settings.
- **District admin:** views all schools and changes nothing.
- **School admin:** views only the assigned school IDs.

Rules:

1. Default deny. No role, or no school, means no rows.
2. Django holds the one access list. A sync job writes Superset roles and row-level filters on school ID. Superset is never hand-edited for access.
3. Django pages, modals, exports, and profiles use one shared query path. That path applies the same school rules everywhere.
4. SQL Lab and chart building are off for every role except system admin.
5. Opening a student profile, or exporting named rows, is written to an append-only log.
6. A permissions test checks every role against every place data can be reached. It runs in CI.

## Repos and releases

- **Product repo** `adukes40/campusview`: generic code only. Build branches merge to `main` when CI passes. Releases are tags such as `v1.3.0`. The live server pulls tags and never pulls raw `main`.
- **Private district repo** `adukes40/campusview-district`: that district's settings, code mappings, branding, and exported dashboards. Upgrades never overwrite it. It holds no secrets.
- **Testing install:** the same release, loaded with fake data. It also serves as an AI query sandbox. The AI gets its own database user that can read raw tables and build views in a scratch schema only. Finished views become migrations with hand-checked tests and ship through releases. They are never copy-pasted to production.

## Build order

One pull request per step. Merge when CI is green.

| Step | Work | Done when |
| --- | --- | --- |
| 0 | Docs: standard file layouts, metric definitions, access model, house rules, and the architecture, decisions, invariants, metrics, and plan documents | Austin approves |
| 1 | Proof tests: one Django card that opens a modal table; one embedded Superset chart that obeys the same filter bar and school limits; Google sign-in | Each one works on fake data, or a fallback is chosen |
| 2 | Skeleton and installer: containers, migrations, sign-in, default deny, CI, and the fake-data generator | CI does a fresh install and an upgrade from the previous release |
| 3 | Loader, raw schema, and the Infinite Campus mapping | Bad files are rejected, and each load is all or nothing |
| 4 | Code mappings and reporting views | Every metric matches a hand-checked answer on fake data |
| 5 | Access list, sync to Superset, and the permissions test | Each role sees exactly its schools, before any dashboard |
| 6 | Card system and the Overview, Attendance, and Behavior dashboards | Checked in a browser as each role. Cards reorder from admin screens |
| 7 | Modal tables with export and print, student profiles, and the view log | Exports match the filtered screen exactly |
| 8 | Nightly schedule and history purge | The schedule and the purge both run |
| 9 | Adversarial review and fixes | Each fix has a test |

## Dashboard design

- v1 KPI cards are plain Django cards: a value, plus a click-through to a modal with the filtered rows, export, and print. Trend lines, and change-from-last-year on cards, are parked.
- Card layout is set in admin screens: which cards, their order, and on or off. It is saved with the district settings. Drag-and-drop is parked.
- A new card is built by writing the query in the sandbox, turning it into a tested view, and then turning the card on.
- The absence card names the school day it counts.
- Top behavior types are horizontal bars, largest first.
- The open referrals list is color-coded by days open. Named working lists have no race column.
- Equity is rates per 100 students per group, totals only.
- Attendance shows a monthly trend against last year, and the chronic absenteeism rate by grade.
- Behavior shows a heatmap of location by time of day.
- Overview metrics for v1: year-to-date attendance rate, absent on the last school day, referrals not yet processed, average days to resolve or action, active 504s and IEPs with counts of those expiring in 30 days, top 10 referred students, top 10 behavior types, and the open referrals list.
- Behavior page: trends by month, grade, location, and time; consequences; repeat referrals; equity.
- Attendance page: rates and trends, chronic absenteeism, unexcused absences, and tardies.
- Clicking a student opens a profile with attendance, behavior, and plan info.
- Filters: school year, school, grade, and gender.

## Fake data

One small seeded generator, and it is deterministic. It builds 1 high school, 1 middle school, and 2 elementary schools, about 25 to 40 fake students each, one school year of attendance days, a scatter of referrals, and a few 504s and IEPs with some expiring soon. Tests and the testing install use it. Making more schools is a one-line change. Do not spend effort hand-writing data.

## Guarding against unwanted changes

- Dashboards are exported from Superset into the district repo. AI agents never edit those exports.
- Every metric has a test with a hand-checked answer.
- Every release is tested as an upgrade from the previous release.
- New ideas go to the FEATURES.md parking lot. Only Austin promotes them into the build.

## Docs built as we go

A step is not done until its docs are. The guides are: server requirements; install and upgrade; Google Cloud project, OAuth client, and sign-in setup; accounts, roles, and school assignments; SFTP and extract setup, plus writing a mapping for another SIS; building and exporting dashboards in Superset; backups and restore.

## Parked for later

Emailed scheduled reports. ClassLink sign-in. Caseload-based access. Small-group hiding for totals-only roles. Mappings for other student information systems. Drag-and-drop card layout. Trend lines and change-from-last-year on cards.
