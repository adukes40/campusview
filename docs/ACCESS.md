# Access

Who can see which students, and how that rule is enforced in every place data can leak. The mechanics of the sync and the guest token are in [ARCHITECTURE.md](ARCHITECTURE.md). This document is the rule book.

Default deny is the starting point. A person with no role sees no rows. A person with a role and no schools sees no rows. A request for a school they do not have returns no rows. Missing data is an empty result, never someone else's school.

## Roles

Role names are data. The installer seeds three roles. A district may rename them or add a role by copying one of these capability sets. Code does not branch on the English name.

| Capability | System admin | District admin | School admin |
| --- | --- | --- | --- |
| See data | All schools, including a school added later | All schools, including a school added later | Only the school ids granted to that user |
| Change users, roles, grants, settings, card config | Yes | No | No |
| Build Superset charts and use SQL Lab | Yes | No | No |
| Open dashboards, modals, exports, profiles | Yes | Yes | Yes, inside the grant |
| Read the audit log | Yes | No | No |

A new role with an empty capability set sees nothing and changes nothing. That is the safe default when someone adds a role and forgets the checkboxes.

School grants are per user. A school admin may hold more than one school id. "All schools" is a capability on the role, not a row that must be updated when a school opens. Granting a school id to a district admin does not matter; the all-schools capability already covers it. Taking away schools from a school admin takes effect on the next page load for Django and for embedded charts, and on the next successful sync for a direct Superset login.

Preferences never grant access. A default school, a saved filter, or a card order can only narrow what the grant already allows. A saved school the user no longer has is ignored.

## What Django stores

The access list is Django's. Superset is a copy.

- A user: email from Google, display name, one role, active or not.
- A role: name plus the capabilities above.
- A school grant: user, `school_id`. Used for roles that do not have all schools.
- An audit event, append-only.

Sign-in is Google OAuth. The Google account must match an active user the system admin already created. An unknown Google account gets no session and no rows. There is no open registration.

Every route requires a session, except the sign-in page, the OAuth callback, and static files. A failed session check redirects to sign-in. It does not render an empty dashboard.

## Sync to Superset

Superset access is written only by the sync. Nobody edits Superset roles or row-level filters by hand. A hand edit would be overwritten, and it is a bug if a deploy depends on one.

The sync:

- Matches Superset users to CampusView users by email.
- Gives all-schools roles a viewer role with no school predicate.
- Gives everyone else a personal role whose filter is their school ids.
- Gives a user with zero schools a filter that matches nothing.
- Publishes only the reporting views in [METRICS.md](METRICS.md). Each of those views has `school_id`. The sync refuses to publish a dataset that lacks `school_id`.
- Turns SQL Lab, chart editing, and Superset CSV download off for every role except system admin.
- Runs when a grant is saved. If Superset rejects the update, the grant save fails and the old grant stays.
- Runs again after each successful load, and on a slow timer, to repair drift.

Deactivating a user removes their Superset session rights on the next sync. Django rejects the sign-in as soon as the user is inactive.

## One query path

Pages, modals, CSV export, student profiles, and the guest-token builder call one function. That function applies the user's schools and then the filter bar. There is no second helper that skips the school rule.

CSV export runs that function with the filters on the screen and writes the audit log. The file matches those filters. Print prints the modal already on screen, which was filled by the same function.

Embedded charts get a guest token whose school clause is built by the same scope rules. The token is short-lived. The browser cannot add a school to it. Year, grade, and gender travel as filters. They are not permissions.

A student profile also checks that the student has a primary enrollment in a granted school for the selected year. An id typed into the address bar, for a student outside the grant, returns nothing.

## Audit log

The log is append-only. The application database user can insert and read. Update and delete are revoked in the database, not only hidden in the screen.

An event is written when:

- Someone opens a student profile, including a profile that returns nothing because the student is outside the grant.
- Someone exports named rows from a Django modal.

The event records when, which user, which role, the action, the student id or the export, the school scope, the filter values, the row count, and the page. It does not store the exported file itself.

System admin reads the log in the app. District admin and school admin do not. Whether the system admin's own download inside Superset is logged is open: see decision 24 in [METRICS.md](METRICS.md). Django exports and profile views are logged for the system admin too.

The history purge does not delete audit rows. They are not student-information-system history.

## Database users

| Database user | Allowed | Not allowed |
| --- | --- | --- |
| Django web | `SELECT` on reporting views. Read and write app tables. Insert and select on the audit log. | Raw tables. Update or delete on the audit log. |
| Loader | Write raw, mapping tables, and load history. | Grants, users, audit updates. |
| Superset | `SELECT` on reporting views. | Raw tables, app tables, audit. |
| Sandbox (testing install only) | `SELECT` on raw and reporting. Create objects in the scratch schema. | Production. The production database does not have this user. |

SQL Lab for the system admin uses the Superset database user, so it can see reporting views and cannot see raw tables. Exploring raw data is a testing-sandbox task.

## Permissions-test matrix

CI runs this matrix. A failure is a broken build. School-admin cases are run twice: once for a granted school, and once asking for a school that was not granted. The second ask must return no rows on every data path.

"Own schools" means only the granted school ids. "All schools" means every school in the snapshot. "Nothing" means no student rows and no aggregates.

| Data path | Signed out | Signed in, no role or no schools | School admin | District admin | System admin |
| --- | --- | --- | --- | --- | --- |
| Sign-in page | Allowed | Allowed | Allowed | Allowed | Allowed |
| Dashboard card numbers | Redirect to sign-in | Nothing | Own schools | All schools | All schools |
| Card modal rows | Redirect | Nothing | Own schools, no race column | All schools, no race column | All schools, no race column |
| CSV export of a modal | Redirect | Nothing | Own schools, and an audit row | All schools, and an audit row | All schools, and an audit row |
| Print of a modal | Redirect | Nothing | Same rows as the modal | Same rows as the modal | Same rows as the modal |
| Student profile in scope | Redirect | Nothing | Own schools, and an audit row | All schools, and an audit row | All schools, and an audit row |
| Student profile outside the grant, by typed id | Redirect | Nothing | Nothing, and an audit row | Not applicable (all schools) | Not applicable (all schools) |
| Filter or saved preference naming an ungranted school | Redirect | Nothing | Nothing from that school | Not applicable | Not applicable |
| Embedded Superset chart | No token | No token, empty state | Own schools inside the guest token | All schools | All schools |
| Direct Superset login | No account | Account with a match-nothing filter | Own schools via the synced filter | All schools | All schools |
| SQL Lab | No | No | No | No | Yes, reporting views only |
| Chart and dashboard editing | No | No | No | No | Yes |
| Superset's own CSV download | No | No | No | No | Yes, until decision 24 says otherwise |
| Raw tables through Superset | No | No | No | No | No |
| User, grant, and card admin screens | Redirect | Forbidden | Forbidden | Forbidden | Allowed |
| Audit log screen | Redirect | Forbidden | Forbidden | Forbidden | Allowed |
| Equity chart | Redirect | Nothing | Own schools, group totals, no names | All schools, group totals, no names | All schools, group totals, no names |

The equity path is called out because that view is the only one built from race or ethnicity, and the test checks that the result has no student id and no name.

The test also checks the database grants: the Superset user's `SELECT` on a raw table fails, and the Django user's `UPDATE` on the audit table fails.

Step 5 builds this test, before the dashboards exist, so a later chart cannot become the first place a school boundary is tried.
