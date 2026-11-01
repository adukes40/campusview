# Server requirements

Outline only. Step 2 fills this in, when the containers exist. Nothing here is a sizing promise or an install command yet.

## Hardware

What a single-server install needs: CPU, memory, and disk, including room for the database volume, the SFTP drop, and a local archive of loaded files. How to think about growth when history is set to two school years.

## Operating system

The supported Linux setup for Docker. Which time-sync requirement matters, because "today" and the 30-day window use the district time zone.

## Software the installer expects

Docker and the compose plugin. What the installer will add by itself when they are missing, and what the operator must already have (a way to reach the machine, a DNS name, a TLS certificate path).

## Network

Which port the reverse proxy listens on. That PostgreSQL, Redis, and the internal app ports are not opened on the host. That the browser needs to reach both the Django pages and the Superset embed path through that proxy.

## Disk layout

Where the database volume, the SFTP drop, the loaded-file archive, the secret env file, and the mounted district-config directory live. A reminder that none of those belong in the product git repo.

## Accounts on the machine

The unprivileged user that runs the containers. The separate upload user that can write the SFTP drop and cannot read the database.

## What this guide will not cover

District-specific host names, real account names, or a cloud vendor's account numbers. Those stay on the server and in the district repo.
