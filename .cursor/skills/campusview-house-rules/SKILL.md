---
name: campusview-house-rules
description: >-
  House rules for every change in the CampusView repository. Covers the
  stack, security, fake data, the parking lot, one pull request per step,
  CI, hand-checked metric tests, and updating docs with the code. Use
  before any CampusView work.
---

# CampusView house rules

Follow these on every task in this repository. [docs/PLAN.md](../../../docs/PLAN.md) is the source of truth. If a doc disagrees with the plan, the plan wins. [docs/INVARIANTS.md](../../../docs/INVARIANTS.md) lists the rules that must not break.

Step 0 is documentation. Do not add application code in a documentation step. Do not start the next build step until Austin has approved the current one.

## Stack

- PostgreSQL holds the warehouse. All metric logic lives in `reporting` views. Django and Superset only filter and aggregate those views.
- Django owns the pages: the filter bar, KPI cards, modals, export, print, profiles, preferences, admin screens, and page styling.
- Apache Superset supplies embedded charts, with guest tokens. Its built-in theme is enough. Keep custom chart CSS minimal.
- Celery and Redis exist only because Superset needs them. The nightly load is a timed Django management command. Do not move the load onto Celery.
- Files on SFTP are the only ingest. Do not add a direct connection to a student information system.
- The product repo stays generic. District settings, code mappings, branding, and exported dashboards belong in the private district repo. Production pulls release tags, never raw `main`.

## Security

- Fake data only, outside production. No real names, emails, student information, school names from a real district, keys, or district-specific values in code, tests, fixtures, logs, docs, or commits. Examples use obvious placeholders such as `STU-001` and `School A`.
- Production must refuse the fake-data generator. The testing install uses the same release tag and the generator.
- Secrets come only from the environment or Docker secrets. Never from source, argv, a fixture, or either git repo.
- Default deny. No role, or no school, means no rows. Every route requires a signed-in user except the sign-in page, the OAuth callback, and static files.
- An unknown Google account is not enrolled automatically.
- One shared query path applies school limits for cards, modals, exports, profiles, and guest tokens. Do not query around it.
- Superset roles and school filters are written only by the sync. Do not hand-edit them. Do not publish a dataset that has no `school_id`.
- Security headers on the proxy. CSRF protection on Django forms and on the guest-token endpoint. Containers run as non-root, with no extra privileges.
- Profile views and Django exports of named rows write the append-only audit log. The log is insert-only. Do not log cell values, secrets, or full row dumps. A loader error names the file, the row number, and the rule.
- Named working lists have no race column. Equity output has group totals only.

## YAGNI and KISS

Build the step that is open. Do not add a framework, a queue, a second chart library, or a config switch for a future idea. Prefer a straightforward Django view and a SQL view over a new abstraction. Role names are data, not code branches.

## Parking lot

A new idea, including one that appears mid-build, is written into the Parking lot section of [FEATURES.md](../../../FEATURES.md). It is not implemented in the current pull request. Only Austin promotes a parked item into a step. Agents do not edit exported Superset dashboards in the district repo.

## How work lands

- One pull request per plan step. Do not mix two steps.
- CI must pass before the step is done. From step 2 on, CI includes a fresh install and an upgrade from the previous release.
- Every metric has a test with a hand-checked answer on fake data. The test reads the reporting view. It does not reimplement the formula.
- Definition choices still listed under Decisions for Austin in [docs/METRICS.md](../../../docs/METRICS.md) are open. Do not treat them as approved until Austin answers them. If Austin approves that document without changing an item, the item's working proposal becomes the definition.
- Update the docs in the same pull request as the code. A step is not done while its guides are still stubs for behavior the step just added.
