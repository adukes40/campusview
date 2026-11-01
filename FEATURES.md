# Features

v1, in the order [PLAN.md](docs/PLAN.md) builds it. One pull request per step. A step is done when its "done when" line is true, CI is green, and the docs that step touches are updated in the same pull request.

Ideas that show up while a step is open go in [Parking lot](#parking-lot). They are not built in the open step. Only Austin moves an item from the parking lot into a step.

## Step 0 — Documentation

The plan, architecture, data contract, metric definitions, access model, decisions, invariants, this list, guide outlines, and the house-rules skill.

Done when Austin approves. No application code in this step.

## Step 1 — Proof tests

- One Django KPI card that opens a modal table.
- One embedded Superset chart that follows the same filter bar and the same school limits.
- Google sign-in.

Done when each of those works on fake data, or a written fallback is chosen for the one that cannot.

## Step 2 — Skeleton and installer

- Containers from [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): proxy, Django, loader, PostgreSQL, Redis, Superset, Superset worker, Superset beat.
- Migrations for app tables, the audit log, and an empty warehouse.
- Google sign-in and default deny on every route.
- CI that does a fresh install and an upgrade from the previous release.
- The deterministic fake-data generator: 1 high school, 1 middle school, 2 elementary schools, about 25 to 40 students each, one school year of days, a scatter of referrals, a few 504s and IEPs with some expiring soon. Scaling the school count is a one-line change. Production refuses to run the generator.

Done when CI completes both the fresh install and the upgrade.

## Step 3 — Loader and Infinite Campus

- Standard files and mapping tables from [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md).
- The loader: check every file, reject a bad file, load all or nothing.
- The Infinite Campus mapping onto those files.
- The guide on how to write a mapping for another student information system. The mapping itself is not built.

Done when a bad file leaves the previous data in place, and a good file set replaces the snapshot in one transaction.

## Step 4 — Code mappings and reporting views

- Every view in [docs/METRICS.md](docs/METRICS.md).
- Metric logic only in those views.
- A hand-checked test, on fake data, for every metric.

Done when every metric matches its hand-checked answer.

## Step 5 — Access

- The access list, school grants, and the three starter roles.
- Sync to Superset roles and school filters.
- Guest tokens for embeds.
- The permissions matrix in [docs/ACCESS.md](docs/ACCESS.md), running in CI.

Done when each role sees exactly its schools, before any dashboard is built.

## Step 6 — Cards and dashboards

- Overview, Attendance, and Behavior, with one shared filter bar: school year, school, grade, gender.
- The six overview cards: year-to-date attendance rate, absent on the last school day (the card names the day), referrals not yet processed, average days to resolve or action, active 504s with the expiring-in-30-days count, active IEPs with the same.
- Embedded charts: top 10 referred students, top 10 behavior types as horizontal bars, open referrals colored by days open and without a race column, behavior trends by month, grade, location, and time, the location-by-time heatmap, consequences, repeat referrals, equity as rates per 100 with totals only, monthly attendance versus last year, chronic absenteeism by grade, unexcused absences, and tardies.
- Admin screens for which cards exist, their order, and on or off.
- Checked in a browser as a school admin, a district admin, and a system admin.

Done when those pages match the filters and the school grants, and card order changes from the admin screens.

## Step 7 — Modals, profiles, and the log

- Clicking a card opens a modal of the filtered rows, with CSV export and print.
- The export matches the filtered screen: same view, same filters, same columns.
- Clicking a student opens a profile with attendance, behavior, and plan info.
- Opening a profile or exporting named rows writes the append-only log.

Done when an export matches the screen and the log records both actions.

## Step 8 — Nightly schedule and history purge

- The loader runs on a nightly timer as a Django management command.
- History kept is a setting, default the current school year plus one prior year.
- Older raw data is purged on load. The audit log is not purged.

Done when a scheduled run loads a good drop and purges an older year.

## Step 9 — Adversarial review

A review that tries to break school limits, the audit log, the loader's all-or-nothing rule, and the "no real student data" rule. Each fix includes a test.

Done when each fix is merged with its test.

## Parking lot

Held from the approved plan. Not in v1 unless Austin promotes one.

- Emailed scheduled reports
- ClassLink sign-in
- Caseload-based access
- Small-group hiding for totals-only roles
- Mappings for other student information systems (the how-to doc is in v1; the mappings are not)
- Drag-and-drop card layout
- Trend lines and change-from-last-year on cards
