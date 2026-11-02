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

Step 0 is documentation and the base install. Do not add application code in a documentation pull request. Do not start the next build step until Austin has approved the current one.

## Stack

- v1 is plain Apache Superset: native filters, dashboards, charts, theme settings, roles, and row-level security. No custom Django pages, filter bar, cards, modals, profiles, or view log. Those are parked.
- PostgreSQL 17 holds three databases: `superset_meta`, `django_app`, and `campusview_data` (the warehouse). All metric logic lives in `reporting` views whose SQL is in this repo. Superset only filters and aggregates those views.
- PostgreSQL 17 comes from the PGDG apt repo, added directly over https with its signing key, not with `apt.postgresql.org.sh`.
- Superset 6.1.0 and Django 6.1.2 both run on Python 3.12 (verified on 3.12.16), managed with `uv`, each in its own Python environment, under gunicorn on 127.0.0.1 (Superset on 8088, Django on 8000). Superset is installed with its 6.1.0 `requirements/base.txt` as pip constraints.
- Django is a default `startproject campusview_base` with no v1 role. Do not build on it unless Austin promotes a parked item.
- No Redis, no Celery, no Superset worker or beat. The `celery` and `redis` libraries come with Superset; do not start or rely on them. The nightly load is a timed job on the server, not Celery.
- Native install on Ubuntu or Debian. No containers. The CampusView Engineer owns the `install.sh` wizard and all engineering.
- Files on SFTP are the only ingest. Do not add a direct connection to a student information system.
- The product repo stays generic. District settings, code mappings, branding, and exported dashboards belong in the private district repo. Production pulls release tags, never raw `main`.

## Security

- Fake data only, outside production. No real names, emails, student information, school names from a real district, keys, or district-specific values in code, tests, fixtures, logs, docs, or commits. Examples use obvious placeholders such as `STU-001` and `School A`.
- Production must refuse the fake-data generator. The testing install uses the same release tag and the generator.
- Secrets live only in `/etc/campusview/campusview.env` on the server (mode 600, owned by the account that runs CampusView, folder mode 700), loaded by systemd `EnvironmentFile=` or `start.sh`. `superset_config.py` and `settings.py` read them from the environment. Only Django's own generated `SECRET_KEY` stays in `settings.py`, which is mode 600. Never in source, argv, a fixture, or either git repo.
- Default deny. No role, or no school, means no rows. Superset self-signup stays off.
- Access lives in Superset roles and row-level security on `school_id`. Do not publish a dataset that has no `school_id`. A native filter is never a permission.
- Services listen on 127.0.0.1 only. PostgreSQL uses `listen_addresses = '127.0.0.1'`, not `localhost` (that also opens `[::1]`). There is no reverse proxy or TLS yet; reach the server through an SSH tunnel. Do not open a port to the network without Austin's decision.
- Do not log cell values, secrets, or full row dumps. A loader error names the file, the row number, and the rule.
- Named working lists have no race column. Equity output has group totals only.

## YAGNI and KISS

Build the step that is open. Do not add a framework, a queue, a second chart library, custom pages, or a config switch for a future idea. Prefer a SQL view and a plain Superset chart over a new abstraction. Role names are not code branches.

## Parking lot

A new idea, including one that appears mid-build, is written into the Parking lot section of [FEATURES.md](../../../FEATURES.md). It is not implemented in the current pull request. Only Austin promotes a parked item into a step. Agents do not edit exported Superset dashboards in the district repo.

## How work lands

- One pull request per plan step. Do not mix two steps.
- CI must pass before the step is done. Once releases exist, CI includes a fresh install and an upgrade from the previous release.
- Every metric has a test with a hand-checked answer on fake data. The test reads the reporting view. It does not reimplement the formula.
- Definition choices still listed under Decisions for Austin in [docs/METRICS.md](../../../docs/METRICS.md) are open. Do not treat them as approved until Austin answers them. If Austin approves that document without changing an item, the item's working proposal becomes the definition.
- Update the docs in the same pull request as the code. A step is not done while its guides are still stubs for behavior the step just added.
