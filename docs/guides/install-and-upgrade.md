# Install and upgrade

Outline. CampusView is installed directly on one Ubuntu or Debian server, with no containers. The CampusView Engineer built `install.sh`, one script with a step-by-step wizard that asks for every setting and does every step below. It passed clean installs and re-runs on Debian 12, Ubuntu 24.04, and Ubuntu 22.04, and Austin is reviewing it now. Until he approves it, the steps below are done by hand, following the base-install guide the Engineer tested. They do the same thing the script does. This guide stays generic. Exact prompts land here once `install.sh` is approved.

## Before you start

A server that meets [server-requirements.md](server-requirements.md), a release tag, a checkout of the district repo, and SSH access to the server. Secrets go in one file on the server, `/etc/campusview/campusview.env`, and nowhere else (see Where secrets live, below). Non-secret district settings live in the district repo.

## First install

What the base install sets up, in order:

1. System packages.
2. Python 3.12, installed with `uv`. Superset and Django both use it. Clean installs were verified on Python 3.12.16.
3. PostgreSQL 17 from the official PostgreSQL apt repo (PGDG). The repo is added directly over https, with PostgreSQL's signing key saved in a keyring and named in the repo's sources entry. The `apt.postgresql.org.sh` helper isn't used, because it failed in testing on Ubuntu 22.04 (it adds the repo over plain http). PostgreSQL is then set to listen only on 127.0.0.1 (`listen_addresses = '127.0.0.1'` in `/etc/postgresql/17/main/postgresql.conf`, then a restart). The default, `localhost`, also opens it on the IPv6 address `[::1]`.
4. The database users and the three databases: `superset_meta`, `django_app`, and `campusview_data`.
5. The folder layout for CampusView.
6. Apache Superset 6.1.0 in its own Python environment, installed with Superset's 6.1.0 `requirements/base.txt` as pip constraints. `venv/bin/pip show apache_superset` should report `Version: 6.1.0`.
7. The secrets file, `/etc/campusview/campusview.env`, which holds the database passwords and Superset's secret key. Then Superset's config file, `superset_config.py`, which reads those values from the environment and holds no secrets itself.
8. Superset's own database, the first admin user, and the default roles. The secrets file is loaded into the shell first.
9. Django 6.1.2 in its own Python environment, as a default `startproject campusview_base`.
10. Django pointed at the `django_app` database. `settings.py` reads the database user and password from the environment, and the file is locked with `chmod 600`.
11. Start and stop scripts that run Superset and Django under gunicorn. `start.sh` loads the secrets file before starting either app.
12. A check that everything is running (below).
13. Opening it from a laptop through an SSH tunnel.
14. Optional: starting at boot with systemd. Each service loads the secrets file with `EnvironmentFile=/etc/campusview/campusview.env`.

Not installed: a Redis server, Celery, a Superset worker or beat, a reverse proxy, example data, or theming. The `redis` and `celery` Python libraries are installed only because Superset depends on them, and nothing runs them. SFTP and the loader come in step 1.

`install.sh` asks for each setting these steps need, such as the database passwords and the first admin account, and does the steps for you. It suggests random passwords you can accept. Settings it doesn't cover yet, such as the district time zone, come with later steps.

## Where secrets live

- All secrets go in one file, `/etc/campusview/campusview.env`: the two database passwords and Superset's secret key. `install.sh` also stores the first admin's password there, along with its non-secret answers such as the ports and the install folder.
- The file is mode 600 and owned by the account that runs CampusView. Its folder, `/etc/campusview`, is mode 700.
- The file is loaded by systemd (`EnvironmentFile=`) or by `start.sh`. `superset_config.py` and Django's `settings.py` read the values from the environment. No password is written into either file.
- The one exception is Django's own `SECRET_KEY`. `startproject` generates it and it stays in `settings.py`, so `settings.py` is locked to mode 600.
- To see the saved passwords later, the operator reads the file on the server, as root or as the account that runs CampusView. Never copy them into either git repo.

## Open items

- `campusview_data` is owned by the Superset database user for now. Step 1 plans a separate owner user for the loader and a read-only user that Superset uses to read the reporting views (see [../ARCHITECTURE.md](../ARCHITECTURE.md)).

## Check that it came up

- PostgreSQL answers on 127.0.0.1:5432, and nothing listens on `[::1]` or on the network.
- Superset answers on 127.0.0.1:8088, and its health page says OK.
- Django answers on 127.0.0.1:8000, and its `/admin/login/` page loads.
- From a laptop, open an SSH tunnel to port 8088 and sign in to Superset as the first admin.

No student data is needed for this check.

## Upgrade

How production moves from one tag to the next. The server pulls a tag, never a branch. Database migrations run. The district repo, the secrets file, and the server's config files are left as they are. What a successful upgrade looks like. Filled in when releases exist.

## Upgrade test

What CI already proved: a clean install of this tag, and an upgrade from the previous tag. What the operator still does on the real server, and what to do if migrations fail (leave the previous tag running; do not repair by editing the district repo).

## The testing install

How to bring up the same tag with fake data, including the sandbox database user. A clear statement that the fake-data command must be refused on production.

## Uninstall

How to stop Superset and Django with the stop script, and remove the systemd services if they were added. A warning that dropping the `campusview_data` database deletes the warehouse, and that the district repo is a separate checkout and is not removed.
