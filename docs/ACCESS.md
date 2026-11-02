# Access

Who can see which students, and how that rule is enforced. In v1, access lives entirely in Apache Superset: its roles and its row-level security. Row-level security is a rule Superset adds to every query, so a chart only returns rows for the schools that rule allows. This document is the rule book.

Default deny is the starting point. A person with no role sees no rows. A person with a role and no schools sees no rows. Missing data is an empty result, never someone else's school.

## Roles

The install sets up three Superset roles. A district may rename them, or add a role by copying one of these. Nothing in CampusView depends on the English name.

| Capability | System admin | District admin | School admin |
| --- | --- | --- | --- |
| See data | All schools, including a school added later | All schools, including a school added later | Only the schools in their row-level security rule |
| Manage Superset users, roles, and row-level security | Yes | No | No |
| Build charts and dashboards, use SQL Lab | Yes | No | No |
| Open dashboards | Yes | Yes | Yes, inside their schools |
| Superset's own CSV download | Yes | No | No, until decision 24 says otherwise |

A new role with no permissions sees nothing and changes nothing. That is the safe default when someone adds a role and forgets the checkboxes.

"All schools" means the role has no school rule, so a new school shows up with no extra step. A school admin may have more than one school. Taking a school away is a change to that person's row-level security rule in Superset, and it applies to their next query.

Native filters never grant access. A school picked in a filter can only narrow what row-level security already allows.

## How school limits work in Superset

- System admin and district admin roles have no row-level security rule on school.
- A school admin gets a rule of the form `school_id IN (...)` listing their schools.
- Superset applies row-level security per role. So a school admin's rule has to live on a role that only they (or only people with the same schools) hold, such as one role per school or one role per person.
- A person with the school admin role and no school rule must see nothing. How that is set up in Superset is checked in step 2.
- Every Superset dataset is a reporting view from [METRICS.md](METRICS.md), and every one has `school_id`. A dataset without `school_id` is not published.

**Open question: how school assignments get maintained.** The first draft kept the list of who has which schools in Django and synced it to Superset. That sync is parked. Without it, someone has to keep Superset's roles and school rules matching real staff assignments, including when staff change schools or leave, and when a new school appears in the extract. Who does that and how is not decided. See [PLAN.md](PLAN.md).

## Sign-in

The base install uses Superset's own user accounts, created by the system admin. There is no open registration: self-signup stays off.

**Open question: Google sign-in.** The approved plan said staff sign in with Google. Superset can be set up for Google sign-in through its config file, but that is not in the base install, and whether and when to turn it on is not decided. See [guides/google-oauth.md](guides/google-oauth.md).

Deactivating a user in Superset stops their sign-in.

## View and export log

**Deferred.** The first draft had an append-only log of profile views and exports of named rows from Django pages. Those pages are parked, so the log is parked with them (see [FEATURES.md](../FEATURES.md#parking-lot)). Whether downloads inside Superset need to be logged is decision 24 in [METRICS.md](METRICS.md).

## Database users

| Database user | Allowed | Not allowed |
| --- | --- | --- |
| Superset (settings) | Owns `superset_meta`, Superset's own settings and users. | Student data. |
| Superset (warehouse) | `SELECT` on reporting views in `campusview_data`. | Raw tables, mapping tables, load history. |
| Django | Owns `django_app`, Django's default tables. | `campusview_data`. Django has no v1 role. |
| Loader (step 1) | Write raw, mapping tables, and load history in `campusview_data`. | Superset's and Django's databases. |
| Sandbox (testing install only) | `SELECT` on raw and reporting. Create objects in the scratch schema. | Production. The production database does not have this user. |

**To fix when the warehouse is set up:** the base install currently makes the Superset database user the owner of `campusview_data`. That gives Superset more than `SELECT` on reporting. Step 1 should give the loader its own owner user and connect Superset to the warehouse with a separate read-only user.

SQL Lab for the system admin uses the Superset warehouse user, so it can see reporting views and cannot see raw tables. Exploring raw data is a testing-sandbox task.

## Permissions check

Step 2 checks this table by hand in a browser, on fake data, as each role. School admin cases are run twice: once for one of their schools, and once trying a school that is not theirs. The second try must return no rows.

"Own schools" means only that person's schools. "All schools" means every school in the snapshot. "Nothing" means no student rows and no totals.

| Data path | Signed out | Signed in, no role or no schools | School admin | District admin | System admin |
| --- | --- | --- | --- | --- | --- |
| Sign-in page | Allowed | Allowed | Allowed | Allowed | Allowed |
| Dashboard charts | Redirect to sign-in | Nothing | Own schools | All schools | All schools |
| School native filter set to a school not theirs | Redirect | Nothing | Nothing from that school | Not applicable | Not applicable |
| SQL Lab | No | No | No | No | Yes, reporting views only |
| Chart and dashboard editing | No | No | No | No | Yes |
| Superset's own CSV download | No | No | No | No | Yes, until decision 24 says otherwise |
| Raw tables through Superset | No | No | No | No | No |
| Users, roles, and row-level security screens | Redirect | Forbidden | Forbidden | Forbidden | Allowed |
| Equity chart | Redirect | Nothing | Own schools, group totals, no names | All schools, group totals, no names | All schools, group totals, no names |

The equity path is called out because that view is the only one built from race or ethnicity, and the check confirms that the result has no student id and no name.

The check also covers the database grants: the Superset warehouse user's `SELECT` on a raw table fails.
