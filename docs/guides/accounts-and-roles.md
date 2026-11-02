# Accounts, roles, and school assignments

Outline. Step 2 fills this in, when the first dashboard and the three roles are set up in Superset. The rules themselves are in [ACCESS.md](../ACCESS.md). All of this is done in Superset's own security screens.

## Creating a user

What the system admin enters in Superset: the person's email, a name, and their role. That self-signup is off.

## The three starter roles

What system admin, district admin, and school admin can do, in the words from the access doc. How to rename a role, and how a new role starts with no permissions until they are turned on.

## Assigning schools

How a school admin is limited with a Superset row-level security rule on `school_id`, using the same `school_id` values as in the extract. That district admin and system admin have no school rule, so they see every school, including one that appears in a later load.

**Open question:** how school assignments are kept matching real staff assignments over time (staff who move or leave, a new school in the extract). Superset applies row-level security per role, so per-school limits likely need a role per school or per person. Not decided. See [ACCESS.md](../ACCESS.md).

## Checking your own access

How a school admin confirms they see one school and not another. How a person with no schools sees empty charts rather than another school's data.

## Removing access

Deactivate a user, change their school rule, or remove a role in Superset. What happens to their next query.

## Filters versus permissions

A native filter set to one school only narrows the view. It never grants a school.
