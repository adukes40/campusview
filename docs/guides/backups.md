# Backups and restore

Outline only. Step 2 fills in the volume layout when the containers exist. Step 8 notes the nightly load and the history purge so backup timing is clear. This guide does not name a district's storage account.

## What must be backed up

The PostgreSQL volume (warehouse, app tables, and audit log). The server env file that holds secrets. The SFTP drop and any local archive of loaded files. The district repo, which already has its own git history for mappings, branding, and dashboard exports.

## What a backup must not do

It must not copy secrets or student files into the product repo. It must not commit a database dump to either git repo.

## How often

A nightly database backup, plus a backup after an upgrade and before a restore drill. How that lines up with the nightly load so a backup is not taken in the middle of a transaction.

## Restore

The order: stop the app, restore the database volume, confirm the secret file and the district-config mount are the ones that match, start the same release tag, and sign in as system admin to check a school-limited user. District config is restored from its repo, not from the database.

## Audit log

The log is in the database backup. A restore brings it back. Ordinary loads and the history purge do not delete it.

## A restore drill

What "tested" means: restore onto the testing install or a spare machine, confirm a known fake-data snapshot, and confirm production media was not used on a machine that shares files with development.
