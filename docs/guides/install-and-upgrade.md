# Install and upgrade

Outline only. Step 2 fills this in, together with the installer script. This guide stays generic. Prompts and commands land here when they exist.

## Before you start

What you need from the server-requirements guide, a release tag, and a checkout of the district repo. Where secrets will be typed (the server env file) and where non-secret settings will be stored (the district repo).

## First install

What the one installer script does: install Docker if it is missing, ask for settings, write secrets to the server, start the containers, run migrations, and create the first system admin. The settings it asks for, in plain language: public URL, Google OAuth client id and secret, database passwords, district time zone, how many school years to keep, and the path of the SFTP drop.

## Check that it came up

How to tell the proxy, Django, and Superset are running, and how to sign in once as the first system admin. No student data is required for this check.

## Upgrade

How production moves from one tag to the next. The server pulls a tag, never a branch. Migrations run. The district repo and the secret file are left as they are. What a successful upgrade looks like.

## Upgrade test

What CI already proved: a clean install of this tag, and an upgrade from the previous tag. What the operator still does on the real server, and what to do if migrations fail (leave the previous tag running; do not repair by editing the district repo).

## The testing install

How to bring up the same tag with fake data, including the sandbox database user. A clear statement that this command must be refused on production.

## Uninstall

How to stop containers. A warning that deleting the database volume deletes the warehouse, and that the district repo is a separate checkout and is not removed with the containers.
