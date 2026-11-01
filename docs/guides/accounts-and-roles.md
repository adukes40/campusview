# Accounts, roles, and school assignments

Outline only. Step 5 fills this in, when the access list and the Superset sync exist. The rules themselves are in [ACCESS.md](../ACCESS.md).

## Creating a user

What the system admin enters: the person's Google email, a display name, and one role. Why the email must be the Google account they will use. That there is no self-signup.

## The three starter roles

What system admin, district admin, and school admin can do, in the words from the access doc. How to rename a role, and how adding a new role starts from no capabilities until they are turned on.

## Assigning schools

How a school admin is given one or more school ids, and how those ids are the same `school_id` values as in the extract. That district admin and system admin see every school, including one that appears in a later load, without a new grant row.

What the admin sees if the Superset sync fails: the grant is not saved, and the previous grants stay in force.

## Checking your own access

How a school admin confirms they see one school and not another. How a person with no schools sees empty pages rather than an error full of data.

## Removing access

Deactivate a user, remove a school, or remove a role. What happens to their next page load and to their Superset login. Preferences do not keep access alive after a grant is removed.

## Preferences versus permissions

Where a user sets a default school, theme, saved filters, and their own card order. A reminder that none of those grant a school.
