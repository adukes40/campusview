# Install and upgrade

Outline. CampusView is installed directly on one Ubuntu or Debian server, with no containers. The CampusView Engineer is building `install.sh`, one script with a step-by-step wizard that asks for every setting. Until it lands, the steps below are done by hand, following the base-install guide the Engineer tested. This guide stays generic. Exact prompts and commands land here when `install.sh` exists.

## Before you start

A server that meets [server-requirements.md](server-requirements.md), a release tag, a checkout of the district repo, and SSH access to the server. Secrets are typed into config files on the server only. Non-secret district settings live in the district repo.

## First install

What the base install sets up, in order:

1. System packages.
2. Python 3.12, installed with `uv`. Superset and Django both use it.
3. PostgreSQL 17 from the official PostgreSQL apt repo.
4. The database users and the three databases: `superset_meta`, `django_app`, and `campusview_data`.
5. The folder layout for CampusView.
6. Apache Superset 6.1.0 in its own Python environment, installed with Superset's 6.1.0 `requirements/base.txt` as pip constraints.
7. Superset's config file, which holds its secret key and its database address. It stays on the server.
8. Superset's own database, the first admin user, and the default roles.
9. Django 6.1.2 in its own Python environment, as a default `startproject campusview_base`.
10. Django pointed at the `django_app` database.
11. Start and stop scripts that run Superset and Django under gunicorn.
12. A check that everything is running (below).
13. Opening it from a laptop through an SSH tunnel.
14. Optional: starting at boot with systemd.

Not installed: Redis, Celery, a Superset worker or beat, a reverse proxy, example data, or theming. SFTP and the loader come in step 1.

`install.sh` will ask for each setting these steps need, such as database passwords, the first admin account, and the district time zone, and will do the steps for you.

## Check that it came up

- PostgreSQL answers on 127.0.0.1:5432.
- Superset answers on 127.0.0.1:8088, and its health page says OK.
- Django answers on 127.0.0.1:8000.
- From a laptop, open an SSH tunnel to port 8088 and sign in to Superset as the first admin.

No student data is needed for this check.

## Upgrade

How production moves from one tag to the next. The server pulls a tag, never a branch. Database migrations run. The district repo and the server's config files are left as they are. What a successful upgrade looks like. Filled in when releases exist.

## Upgrade test

What CI already proved: a clean install of this tag, and an upgrade from the previous tag. What the operator still does on the real server, and what to do if migrations fail (leave the previous tag running; do not repair by editing the district repo).

## The testing install

How to bring up the same tag with fake data, including the sandbox database user. A clear statement that the fake-data command must be refused on production.

## Uninstall

How to stop Superset and Django with the stop script, and remove the systemd services if they were added. A warning that dropping the `campusview_data` database deletes the warehouse, and that the district repo is a separate checkout and is not removed.
