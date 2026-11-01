# SFTP and extracts

Outline only. Step 3 fills this in, when the loader and the Infinite Campus mapping exist. Column layouts stay in [DATA_CONTRACT.md](../DATA_CONTRACT.md). This guide is the operator's version.

## The drop folder

Where files land, which account can upload, and the fact that this account cannot read the database. That uploaded files stay on the server and are never committed to either git repo.

## What a nightly drop contains

The standard file names, the rule that this is a full snapshot of the years to keep, and which files must contain rows. What a header-only incident file means (no incidents, and the previous incidents are replaced).

## Code-mapping files

Where they live (the district repo, not the SFTP drop). Who edits them when the district adds an attendance code. That a code in the extract with no map row fails the load and leaves yesterday's data in place.

## Infinite Campus

How to schedule the extracts this district confirmed in the TO CONFIRM list, which columns to leave out (narratives and highly sensitive identifiers), and what the mapping step does before the loader runs. Field-level notes stay in the data contract so this guide does not drift from it.

## When a load fails

Where the system admin looks (the load history screen and the loader logs). What they will see: file name, row number, and rule, not the cell value. That the dashboards keep showing the last good snapshot.

## Writing a mapping for another student information system

The contract another system must meet: produce these standard files, with these keys, and do not connect CampusView to that system. v1 does not ship that mapping. The steps here will be: list the source files, map each CampusView column to a source field, roll daily attendance up to one row per student per date, omit narratives and sensitive identifiers, and run the same loader. Promote a real second mapping out of the parking lot before building it.

## History

How the "years to keep" setting purges older school years on a successful load, and why the extract must include every year that should survive.
