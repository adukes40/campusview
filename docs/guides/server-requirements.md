# Server requirements

Outline. Nothing here is a sizing promise yet. The CampusView Engineer fills in tested numbers as `install.sh` is tested.

## Operating system

Ubuntu 22.04 or 24.04, or Debian 12. CampusView installs directly on the server. Docker is not used. The server clock must stay in sync, because "today" and the 30-day window use the district time zone.

## Hardware

What a single-server install needs: CPU, memory, and disk, including room for the three PostgreSQL databases, the SFTP drop (step 1), and a local archive of loaded files. How to think about growth when history is set to two school years.

## Software

The installer adds these itself:

- Python 3.12, through `uv`, for both Superset and Django.
- PostgreSQL 17, from the official PostgreSQL apt repo.
- Apache Superset 6.1.0 and Django 6.1.2, each in its own Python environment, run by gunicorn.

Not needed: Docker, Redis, Celery, or a reverse proxy.

The operator must already have SSH access to the machine and a user account that will run CampusView.

## Network

Everything listens on the server only:

| Service | Address |
| --- | --- |
| PostgreSQL | 127.0.0.1:5432 |
| Superset | 127.0.0.1:8088 |
| Django | 127.0.0.1:8000 |

No port is opened to the network. To use Superset from a laptop, open an SSH tunnel. Letting staff reach Superset over the network needs a reverse proxy with TLS. When to add one is an open question in [../PLAN.md](../PLAN.md).

## Disk layout

Where the PostgreSQL data, the CampusView folder with the two Python environments, the config files that hold secrets, the SFTP drop, the loaded-file archive, and the district repo checkout live. A reminder that none of those belong in the product git repo.

## Accounts on the machine

The unprivileged user that runs CampusView. In step 1, a separate upload user that can write the SFTP drop and cannot read the database.

## What this guide will not cover

District-specific host names, real account names, or a cloud vendor's account numbers. Those stay on the server and in the district repo.
