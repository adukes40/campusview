# CampusView

CampusView is a self-hosted reporting platform for K-12 districts. Each night it reads CSV extracts from the student information system, checks them, and loads them into PostgreSQL. Staff open Django pages for attendance, behavior, and 504/IEP dashboards. Charts drawn by Apache Superset are embedded in those pages. A person sees only the schools they cover.

Nothing in this repository is specific to one district. Names, schools, local codes, branding, and exported dashboards belong in that district's own repo. The live server runs a release tag, not an unreleased branch.

This is step 0: documentation and architecture. The application is not built yet. [FEATURES.md](FEATURES.md) lists the later steps. New ideas go to the parking lot there; only Austin promotes them.

## Read these

| Document | What it answers |
| --- | --- |
| [docs/PLAN.md](docs/PLAN.md) | The approved v1 plan. If another doc disagrees, the plan wins. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How a file becomes a page, and how the containers fit together. |
| [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md) | The CSV layouts, and how an Infinite Campus extract maps onto them. |
| [docs/METRICS.md](docs/METRICS.md) | What each dashboard number means, and the choices still open for Austin. |
| [docs/ACCESS.md](docs/ACCESS.md) | Roles, school grants, and the permissions test. |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Choices already made, and the alternatives that were set aside. |
| [docs/INVARIANTS.md](docs/INVARIANTS.md) | Rules later changes must not break. |
| [FEATURES.md](FEATURES.md) | The build, step by step, plus the parking lot. |

Operator guides (outlines until the matching step is built) are in [docs/guides/](docs/guides/): server requirements, install and upgrade, Google sign-in, accounts and roles, SFTP and extracts, Superset dashboards, and backups.

Agents working in this repo follow [.cursor/skills/campusview-house-rules/SKILL.md](.cursor/skills/campusview-house-rules/SKILL.md).
