# Backups and restore

Outline. Filled in as the base install and the loader are built. This guide does not name a district's storage account.

## What must be backed up

- The three PostgreSQL databases: `superset_meta` (Superset's users, roles, row-level security, charts, and dashboards), `django_app` (Django's default tables), and `campusview_data` (the warehouse).
- The secrets file, `/etc/campusview/campusview.env` (the database passwords and Superset's secret key), and Django's `settings.py` (it holds Django's own secret key). Store their backup as carefully as the secrets themselves. Superset's secret key must match the restored `superset_meta` database, or Superset can't read the connection passwords saved in it.
- The other server config files, `superset_config.py` and the systemd units, if they were added. They hold no secrets.
- The SFTP drop and any local archive of loaded files, once step 1 exists.
- The district repo, which already has its own git history for mappings, branding, and dashboard exports.

## What a backup must not do

It must not copy secrets or student files into the product repo. It must not commit a database dump to either git repo.

## How often

A nightly database backup, plus a backup after an upgrade and before a restore drill. How that lines up with the nightly load so a backup is not taken in the middle of a load.

## Restore

The order: stop Superset and Django, restore the three databases, confirm the secrets file and the config files are the ones that match, start the same release tag, and sign in as system admin to check a school-limited user. District config is restored from its repo, not from the database.

## A restore drill

What "tested" means: restore onto the testing install or a spare machine, confirm a known fake-data snapshot, and confirm production data was not used on a machine that shares files with development.
