# CampusView

CampusView is a self-hosted reporting platform for K-12 districts. Each night it reads CSV extracts from the student information system, checks them, and loads them into PostgreSQL. Staff open plain Apache Superset dashboards for attendance, behavior, and 504/IEP numbers. Superset's roles and row-level security limit each person to the schools they cover.

Nothing in this repository is specific to one district. Names, schools, local codes, branding, and exported dashboards belong in that district's own repo. Production pins a release tag cut from `main`. The dev server follows the `dev` branch.

This is step 0: documentation and the base install. The base install is PostgreSQL 17, Apache Superset 6.1.0, and a default Django 6.1.2 project, all on Python 3.12 and installed directly on Ubuntu or Debian, with no containers, no Redis, and no Celery. The `install.sh` setup wizard is built and tested on Debian 12, Ubuntu 24.04, and Ubuntu 22.04, and is waiting for Austin's review. SFTP and the loader are not built yet. [FEATURES.md](FEATURES.md) lists the later steps. New ideas go to the parking lot there; only Austin promotes them.

## Read these

| Document | What it answers |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | The approved v1 plan. If another doc disagrees, the plan wins. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How a file becomes a dashboard, and how the installed pieces fit together. |
| [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) | The CSV layouts, and how an Infinite Campus extract maps onto them. |
| [docs/METRICS.md](docs/METRICS.md) | What each dashboard number means, and the choices still open for Austin. |
| [docs/ACCESS.md](docs/ACCESS.md) | Superset roles, row-level security by school, and the permissions check. |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Choices already made, and the alternatives that were set aside. |
| [docs/INVARIANTS.md](docs/INVARIANTS.md) | Rules later changes must not break. |
| [FEATURES.md](FEATURES.md) | The build, step by step, plus the parking lot. |

Operator guides (outlines until the matching step is built) are in [docs/guides/](docs/guides/): server requirements, install and upgrade, Google sign-in, accounts and roles, SFTP and extracts, Superset dashboards, and backups.

Agents working in this repo follow [.cursor/skills/campusview-house-rules/SKILL.md](.cursor/skills/campusview-house-rules/SKILL.md).
