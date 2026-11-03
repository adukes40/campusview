# Invariants

Rules that must not be broken by a later change. If a pull request needs to break one, it stops and Austin decides. [PLAN.md](PLAN.md) is the source of those rules.

## Metric logic lives only in reporting views

What counts as present, absent, chronic, open, processed, or expiring is defined in a PostgreSQL view in the `reporting` schema, and that view's SQL is in this repo. Superset may filter those views and may sum, count, average, or divide columns the view already computed. It may not re-code a local attendance or behavior value.

A new number on a dashboard gets a view, then a hand-checked test, and only then a chart.

## Test data lives only outside production

Production loads district extracts. Tests, fixtures, and the testing install use Infinite Campus training-database extracts that Austin supplies (fake people, per Austin). Those files stay outside the repo until Austin answers whether the Infinite Campus vendor agreement allows them there. Real student rows, real names, and real extracts never go into the product repo, a test, a log message, or a commit.

The testing install runs the same release tag as production. It is the only place the sandbox database user exists.

## Access lives in Superset roles and row-level security

Superset's roles and row-level security on `school_id` are the only access control in v1. A dataset without a `school_id` column is not published. Staff charts read reporting views, never raw tables. A native filter is never a permission.

## Production pulls tags only

The live server runs a release tag such as `v1.3.0`. It does not pull `main` and it does not pull a branch. Work reaches `main` only after CI passes. A tag is cut from that.

## District config lives in the district repo

Settings, code mappings, branding, and exported dashboards belong to `adukes40/campusview-district`. The product repo stays generic. An upgrade replaces the application and runs migrations. It does not overwrite the district repo.

Secrets are not in either repo. They live only on the server, outside git, in `/etc/campusview/campusview.env`: mode 600, owned by the account that runs CampusView, in a folder with mode 700. systemd (`EnvironmentFile=`) or `start.sh` loads the file. `superset_config.py` and Django's `settings.py` read secrets from the environment and never contain a password. The only exception is Django's own generated `SECRET_KEY`, which stays in `settings.py`, so `settings.py` is mode 600.

## No student data and no org-specific values in the product repo

The product repo has no student information, no real staff names or emails, no school names from a real district, no local code lists, no logos, and no keys. Examples in docs use placeholders. The district's identity stays in the district repo and on the server.

## Every release is upgrade-tested

CI installs the release on a clean machine and upgrades a machine that was on the previous release. A release that has not passed both does not get a tag. The upgrade must leave district config in place.

## Also do not break

These follow from the same plan and are just as binding.

- **Default deny.** No role, or no school, means no rows.
- **Keep every column.** The loader keeps every column the district's extract sends. No column is dropped or banned. Production tables will be built on them. See [DECISIONS.md](DECISIONS.md), 2026-11-03.
- **Files are the only ingest.** There is no direct connection to the student information system.
- **No Celery and no Redis in v1.** Loads run as a timed job on the server. The `celery` and `redis` Python libraries come with Superset but nothing runs them.
- **Only nginx faces the network.** PostgreSQL and gunicorn for Superset and Django listen on 127.0.0.1 only. PostgreSQL uses `listen_addresses = '127.0.0.1'`, not `localhost`, which also opens `[::1]`. When nginx is chosen in the installer, it is the only thing listening on the network. PostgreSQL is never exposed; DBeaver uses an SSH tunnel. Plain HTTP sends logins unencrypted, so it is only for test machines with fake data. Real student data needs HTTPS.
- **Agents do not edit exported dashboards.** Those files live in the district repo and stay as the system admin exported them.
- **Parked work stays parked.** New ideas are written into the parking lot in [FEATURES.md](../FEATURES.md). Only Austin promotes one into a step. That includes the custom Django pages and the view and export log, which are parked.
