# Invariants

Rules that must not be broken by a later change. If a pull request needs to break one, it stops and Austin decides. [PLAN.md](PLAN.md) is the source of those rules.

## Metric logic lives only in reporting views

What counts as present, absent, chronic, open, processed, or expiring is defined in a PostgreSQL view in the `reporting` schema, and that view's SQL is in this repo. Superset may filter those views and may sum, count, average, or divide columns the view already computed. It may not re-code a local attendance or behavior value.

A new number on a dashboard gets a view, then a hand-checked test, and only then a chart.

## Test data lives only outside production

Production loads district extracts. Tests, fixtures, and the testing install use Infinite Campus training-database extracts that Austin supplies. That database is completely fictional, so it counts as fake data (Austin, relayed by CampusView Engineer, 2026-11-03). Those files never go in the public repo; they stay on the builder's computer. Real student rows, real names, and real extracts never go into the product repo, a test, a log message, or a commit.

The testing install is the builder's own computer, or a separate fake-data server if Austin sets one up later (Austin, relayed by CampusView Engineer, 2026-11-03). It is never the dev server. It is the only place the sandbox database user and the training files exist.

## The dev server is treated like production

The dev server follows the `dev` branch and holds real district data, so Austin can see how a change will look (Austin, relayed by CampusView Engineer, 2026-11-03). For data and access it follows the production rules: no sandbox database user, no training files, and no agent access.

## Access lives in Superset roles and row-level security

Superset's roles and row-level security on `school_id` are the only access control in v1. A dataset without a `school_id` column is not published. Staff charts read reporting views, never raw tables. A native filter is never a permission.

## Production pins a release tag

The production server runs a release tag such as `v1.3.0`, cut from `main` (CampusView Engineer's reading of Austin's reply, 2026-11-03). The dev server follows the `dev` branch. No server pulls `main`, and production never pulls a branch. Work reaches `main` only after CI passes and Austin has checked it on the dev server. After each merge to `main`, the CampusView Engineer reminds Austin to cut a tag.

## District config lives in the district repo

Settings, code mappings, branding, and exported dashboards belong to `adukes40/campusview-district`. The product repo stays generic. An upgrade replaces the application and runs migrations. It does not overwrite the district repo.

Secrets are not in either repo. They live only on the server, outside git, in `/etc/campusview/campusview.env`: mode 600, owned by the account that runs CampusView, in a folder with mode 700. systemd (`EnvironmentFile=`) or `start.sh` loads the file. `superset_config.py` and Django's `settings.py` read secrets from the environment and never contain a password. The only exception is Django's own generated `SECRET_KEY`, which stays in `settings.py`, so `settings.py` is mode 600.

## No student data and no org-specific values in the product repo

The product repo has no student information, no real staff names or emails, no school names from a real district, no local code lists, no logos, and no keys. Examples in docs use placeholders. No screenshots go in the public repo (Austin, relayed by CampusView Engineer, 2026-11-03). The district's identity stays in the district repo and on the server. Exception: the Infinite Campus start year, the extract cutoff date, and the homeroom attendance rule stay in the product docs (Austin, relayed by CampusView Engineer, 2026-11-03).

## Every release is upgrade-tested

Before a tag is cut, the release is installed on a clean machine and used to upgrade a machine that was on the previous tag. Neither check needs data files, so both belong in CI once releases exist. A release that has not passed both does not get a tag. The upgrade must leave district config in place.

## Also do not break

These follow from the same plan and are just as binding.

- **Default deny.** No role, or no school, means no rows.
- **Keep every listed column.** Every column the data contract lists is kept, and nothing is dropped. Nothing Austin pulls in is banned, including SSN, medical, email, or notes columns. An unknown or misspelled header fails the file with a clear report. A new column or table is added through the contract's change process. Production tables will be built on them. See [DECISIONS.md](DECISIONS.md), 2026-11-03.
- **Files are the only ingest.** There is no direct connection to the student information system.
- **No Celery and no Redis in v1.** Loads run as a timed job on the server. The `celery` and `redis` Python libraries come with Superset but nothing runs them.
- **Only nginx faces the network.** PostgreSQL and gunicorn for Superset and Django listen on 127.0.0.1 only. PostgreSQL uses `listen_addresses = '127.0.0.1'`, not `localhost`, which also opens `[::1]`. When nginx is chosen in the installer, it is the only thing listening on the network. PostgreSQL is never exposed; DBeaver uses an SSH tunnel. Plain HTTP sends logins unencrypted, so it is only for a test machine that is on-prem and not on the internet, such as Austin's test VM (Austin, relayed by CampusView Engineer, 2026-11-03). Real student data needs HTTPS.
- **Agents do not edit exported dashboards.** Those files live in the district repo and stay as the system admin exported them.
- **Parked work stays parked.** New ideas are written into the parking lot in [FEATURES.md](../FEATURES.md). Only Austin promotes one into a step. That includes the custom Django pages and the view and export log, which are parked.
