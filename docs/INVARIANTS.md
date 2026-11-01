# Invariants

Rules that must not be broken by a later change. If a pull request needs to break one, it stops and Austin decides. [PLAN.md](PLAN.md) is the source of those rules.

## Metric logic lives only in reporting views

What counts as present, absent, chronic, open, processed, or expiring is defined in a PostgreSQL view in the `reporting` schema. Django and Superset may filter those views and may sum, count, average, or divide columns the view already computed. They may not re-code a local attendance or behavior value.

A new number on a dashboard gets a view, then a hand-checked test, and only then a card or a chart.

## Fake data lives only outside production

Production loads district extracts. It does not run the fake-data generator. Tests, examples, fixtures, and the testing install use the generator. Real student rows, real names, and real extracts never go into the product repo, a test, a log message, or a commit.

The testing install runs the same release tag as production. It is the only place the sandbox database user exists.

## Superset access changes only through the sync

Django holds the access list. The sync writes Superset users, roles, and school filters. Nobody edits those by hand, and no deploy depends on a hand edit. A dataset without a `school_id` column is not published. Staff charts read reporting views.

Embedded charts get a guest token built from that same access list. The token cannot grant a school the user does not have.

## Production pulls tags only

The live server runs a release tag such as `v1.3.0`. It does not pull `main` and it does not pull a branch. Work reaches `main` only after CI passes. A tag is cut from that.

## District config lives in the district repo

Settings, code mappings, branding, and exported dashboards belong to `adukes40/campusview-district`. The product repo stays generic. An upgrade replaces the application and runs migrations. It does not overwrite the district repo or the mounted config.

Secrets are not in the district repo. They live in the server environment or in Docker secrets.

## No student data and no org-specific values in the product repo

The product repo has no student information, no real staff names or emails, no school names from a real district, no local code lists, no logos, and no keys. Examples in docs use placeholders. The district's identity stays in the district repo and on the server.

## Every release is upgrade-tested

CI installs the release on a clean machine and upgrades a machine that was on the previous release. A release that has not passed both does not get a tag. The upgrade must leave district config in place.

## Also do not break

These follow from the same plan and are just as binding.

- **Default deny.** No role, or no school, means no rows.
- **One query path.** Cards, modals, exports, profiles, and guest tokens apply school limits in one place.
- **Files are the only ingest.** There is no direct connection to the student information system.
- **The audit log is append-only.** Profile views and Django exports of named rows are inserted. Rows are not updated or deleted. The history purge does not touch the log.
- **Loads do not use Celery.** The nightly job is a timed Django management command.
- **Agents do not edit exported dashboards.** Those files live in the district repo and stay as the system admin exported them.
- **Parked work stays parked.** New ideas are written into the parking lot in [FEATURES.md](../FEATURES.md). Only Austin promotes one into a step.
