# Server requirements

Outline. Nothing here is a sizing promise yet. The CampusView Engineer fills in tested numbers as `install.sh` is tested.

## Operating system

Ubuntu 22.04 or 24.04, or Debian 12. All three passed a clean install and a re-run of `install.sh` in testing. CampusView installs directly on the server. Docker is not used. The server clock must stay in sync, because "today" and the 30-day window use the district time zone.

## Hardware

What a single-server install needs: CPU, memory, and disk, including room for the three PostgreSQL databases, the SFTP drop (step 1), and a local archive of loaded files. How to think about growth when history is set to two school years.

## Software

The installer adds these itself:

- Python 3.12, through `uv`, for both Superset and Django (verified on 3.12.16).
- PostgreSQL 17, from the official PostgreSQL apt repo (PGDG), added directly over https with its signing key.
- Apache Superset 6.1.0 and Django 6.1.2, each in its own Python environment, run by gunicorn.

Not needed: Docker, a Redis server, or Celery. The `redis` and `celery` Python libraries come in only as Superset dependencies. Nothing runs them.

The operator must already have SSH access to the machine and a user account that will run CampusView.

## Network

Everything listens on the server only:

| Service | Address |
| --- | --- |
| PostgreSQL | 127.0.0.1:5432 (`listen_addresses = '127.0.0.1'`; not `localhost`, which also opens `[::1]`) |
| Superset | 127.0.0.1:8088 |
| Django | 127.0.0.1:8000 |

With the local-only choice, no port is opened to the network. To use Superset from a laptop, open an SSH tunnel.

The installer has an optional nginx step. Pressing Enter picks HTTPS with a self-signed certificate. When chosen, nginx is the only thing on the network: HTTP on port 80, or HTTPS on port 443 with 80 redirecting to 443. PostgreSQL and the two apps stay on 127.0.0.1. Plain HTTP is for test machines with fake data, plus Austin's accepted exception for the on-prem dev server during early testing. Production uses HTTPS. See [../DECISIONS.md](../DECISIONS.md).

## Disk layout

The installer puts the programs in `/opt/campusview` unless you choose another folder. That folder holds the two Python environments, and `uv` with Python 3.12 in `.uv`. The loader runs from a checkout of the product repo with that `uv` and Python; the installer does not create the checkout. Passwords and the other saved answers go in `/etc/campusview/campusview.env`. The file mode is 600, and the folder `/etc/campusview` is mode 700. PostgreSQL keeps its data under `/var/lib/postgresql`. The SFTP drop, the loaded-file archive, and the district repo checkout are not created by this installer. None of these belong in the product git repo.

## Accounts on the machine

The installer asks for an existing Linux login. It does not create one. The apps run as that login, and that login owns the program folder and the password file. On Debian the login is often root. In step 1, a separate upload user can write the SFTP drop and cannot read the database.

## What this guide will not cover

District-specific host names, real account names, or a cloud vendor's account numbers. Those stay on the server and in the district repo.
