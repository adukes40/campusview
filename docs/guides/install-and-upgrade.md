# Install and upgrade

CampusView goes on one Ubuntu or Debian server. You run one script, `install.sh`. It asks a short list of questions, then installs PostgreSQL, the Superset web page, and the Django admin page. All three listen only on the server itself. One question decides how people reach the web pages: through an SSH tunnel only, or through nginx on port 80 (HTTP) or port 443 (HTTPS). See [How people reach CampusView](#how-people-reach-campusview).

This guide is for the person who runs the server. It stays generic. District settings that are not secrets live in the district repo, not in this one.

## Before you start

Use a server that meets [Server requirements](server-requirements.md). You need a login that can reach the server over SSH.

A minimal Debian install has no curl. As root, install it before you fetch the script.

```bash
apt-get update && apt-get install -y curl
```

On Ubuntu, if curl is missing, install it with sudo.

```bash
sudo apt-get install -y curl
```

Fetch `install.sh` from the same ref this server follows. The dev server follows `dev`.

```bash
curl -fsSLO https://raw.githubusercontent.com/adukes40/campusview/dev/install.sh
```

Production follows a release tag. For `v1.3.0`, fetch `https://raw.githubusercontent.com/adukes40/campusview/v1.3.0/install.sh`.

Debian often has no sudo. As root, run `bash install.sh`. Otherwise run `sudo bash install.sh`.

The installer always uses PostgreSQL 17 from postgresql.org. It does not ask which PostgreSQL to use.

## How to answer

Press Enter to accept the value shown in brackets. When you type a password, nothing appears on the screen. That is on purpose. If you type a password, you type it twice. If you press Enter on a password prompt on the first run, the installer makes a strong password for you. On a later run, Enter on a password that was already saved keeps the saved one.

A password needs at least 8 characters. It cannot contain a space, a single quote (`'`), a double quote (`"`), or a backslash (`\`). The install folder may use only letters, digits, `.`, `_`, `-`, and `/`. The admin email must be a plain address, like `name@school.org`. If you break a rule, the installer says so and asks again. With an answers file, it stops and names the setting, and it changes nothing. If a database command fails, the error it shows hides the password.

## Which account does what

| Account | Who uses it | Where you use it |
| --- | --- | --- |
| Linux account, question 1, for example `cvadmin` | The server. The apps run as this account, and it owns the program folder and the password file. | Signing in to the server over SSH. |
| `superset_user`, database | Superset, behind the scenes, for its own database `superset_meta` only. It cannot connect to `campusview_data`. | Nowhere. Only Superset uses it. |
| `django_user`, database | Django, behind the scenes, for its database `django_app`. | Nowhere. Only Django uses it. |
| `campusview_reader`, database, question 9 | Superset, to read report data. It can read the `reporting` schema of `campusview_data` and nothing else. It cannot change anything. | DBeaver, for safe browsing. Also the account to use when you add the report data connection in Superset. The installer does not create that connection. |
| `campusview_owner`, database, question 10 | The data loader in Step 1. It owns `campusview_data` and its schemas `raw`, `ref`, and `reporting`. | DBeaver, only when you need full access. Use it with care. It can change and delete data. |
| Superset secret key | Superset. It locks the connection details Superset saves. | Nowhere. It must never change after the first install, or Superset can no longer read what it saved. |
| Admin login, questions 12 to 14 | You. | Signing in to the Superset web page and the Django admin page. The username and password are the same for both. |

The three staff roles in Superset, system admin, district admin, and school admin, are not created by this installer. Those come in a later step. The admin login above is a Superset admin and a Django admin so you can sign in and check that the pages work.

All passwords and the key are saved in `/etc/campusview/campusview.env`. Read them with `sudo cat /etc/campusview/campusview.env`.

### The report database, campusview_data

| Schema | Owner | Who can read it |
| --- | --- | --- |
| `raw`, loaded data | `campusview_owner` | `campusview_owner` only |
| `ic`, the typed copy of each `raw` table. Not created yet; it comes with the typed-copy pull request | `campusview_owner` | `campusview_owner` only |
| `ref`, reference and lookup data | `campusview_owner` | `campusview_owner` only |
| `reporting`, views for reports | `campusview_owner` | `campusview_owner`, and `campusview_reader` with read only access. Anything the owner adds here later is readable by `campusview_reader` automatically. |
| `ops`, the load report table `load_batch` | `campusview_owner` | `campusview_owner` only. The installer does not create it. The loader creates it on its first run. |

The schemas start empty. `raw` fills up when you run the loader ([sftp-and-extracts.md](sftp-and-extracts.md)). Earlier installs called `ref` by the name `mapping`. A second run renames `mapping` to `ref` when `ref` does not exist yet. No other account can connect to `campusview_data`.

### Connect with DBeaver

- Host `127.0.0.1`. Port `5432`, or the port you chose. Database `campusview_data`.
- User `campusview_reader` for safe browsing. It sees the reporting views only, and they are empty until Step 1. Use `campusview_owner` only when you need full access.
- The password is the `CV_READER_DB_PASSWORD` line, or the `CV_OWNER_DB_PASSWORD` line, in `/etc/campusview/campusview.env`.
- The database only listens on the server itself. For either account, turn on DBeaver's SSH tunnel to the server. On the SSH tab, use the server address and your Linux login. Or run `ssh -L 5432:127.0.0.1:5432 you@server` first, then connect to `127.0.0.1` port `5432` on your computer.
- `django_app` and `superset_meta` belong to the apps. Do not edit them by hand.

## The questions, in order

Each group is shown under its heading, such as `--- Where CampusView goes ---`.

| # | Heading | Prompt on screen | Default in brackets | Secret? | Help text shown above it |
| --- | --- | --- | --- | --- | --- |
| 1 | Where CampusView goes | Linux account that runs CampusView | The account you ran sudo from. On Debian, that is `root`. | No | An existing login on this server. The apps run as this account, and it owns their files and the password file. |
| 2 | | Install folder | `/opt/campusview` | No | Where the programs go. It is created for you, owned by that account. Letters, digits, . _ - and / only. |
| 3 | | Branch or tag this server follows | `dev` | No | `dev` on the dev server. A release tag such as `v1.3.0` on production. No server uses `main`. |
| 4 | Network ports | Database (PostgreSQL) port | `5432` | No | Keep these unless something else on this server already uses them. |
| 5 | | Superset web page port | `8088` | No | |
| 6 | | Django admin page port | `8000` | No | |
| 7 | Behind-the-scenes database passwords | Password Superset uses for the database | Enter = make one for me | Yes | Superset and Django each sign in to the database with their own account. Only the apps use these. You never type them. Press Enter to have them made for you. |
| 8 | | Password Django uses for the database | Enter = make one for me | Yes | |
| 9 | Report data accounts (database campusview_data) | Password for campusview_reader | Enter = make one for me | Yes | Two database logins for the report data. Press Enter to have them made for you. This question also shows `campusview_reader: what Superset uses to read report data; also safe for DBeaver.` |
| 10 | | Password for campusview_owner | Enter = make one for me | Yes | `campusview_owner: full access to the data, used by the loader; use with care.` |
| 11 | Superset secret key | Superset secret key | Enter = make one for me | Yes | Locks (encrypts) the connection details Superset saves. Never change it after the first install, or Superset can no longer read them. Press Enter to have one made. |
| 12 | Your admin login | Admin username | `admin` | No | The username and password YOU sign in with, on both the Superset web page and the Django admin page. |
| 13 | | Admin email | `admin@example.invalid` when the username is `admin` | No | Not shown on screen. Type a real address. It must be a plain address, like `name@school.org`. |
| 14 | | Admin password | Enter = make one for me | Yes | |
| 15 | Starting up | Start CampusView automatically when the server boots (yes/no) | `yes` | No | Not shown on screen. `yes` sets up the services `cv-superset` and `cv-django`. With `no`, use `start.sh` and `stop.sh` in the install folder. Run them as root or as the CampusView account. As root they switch accounts with `runuser`. Otherwise they use `sudo`. If neither works, they say to run them as root or as that account. If systemd is not running, the installer says so and uses `start.sh` instead. |

After the questions, the installer shows a summary, then `Go ahead? [Y/n]`. Press Enter to accept `Y`. Answer `n` to quit, and the installer changes nothing.

## What the installer sets up

In order, the script does this work for you.

1. System packages.
2. Python 3.12, installed with `uv`, kept inside the install folder. Superset and Django both use it.
3. PostgreSQL 17 from the official PostgreSQL apt repo. The repo is added over https, with PostgreSQL's signing key. PostgreSQL is set to listen only on `127.0.0.1`.
4. The database accounts and the three databases `superset_meta`, `django_app`, and `campusview_data`. `campusview_owner` owns `campusview_data`.
5. The install folder, owned by the Linux account you named. The folder is a checkout of the branch or tag in `CV_REF`.
6. Apache Superset 6.1.0 in its own Python environment.
7. The password file `/etc/campusview/campusview.env`, then Superset's config, which reads secrets from the environment.
8. Superset's own database, the first admin user, and Superset's default setup.
9. Django 6.1.2 in its own Python environment, as a default project named `campusview_base`.
10. Django pointed at `django_app`. Django reads the database password from the environment.
11. `start.sh` and `stop.sh` in the install folder.
12. If you chose HTTP or HTTPS: nginx from the distro's own apt repo, with one site, `/etc/nginx/sites-available/campusview`. For HTTPS with a self-signed certificate, the certificate too. The installer removes nginx's own `default` site from `/etc/nginx/sites-enabled` and makes CampusView the default site on its port, If nginx on this server already serves other sites, check them after the install.
13. A check that the pages answer, described below.
14. If you answered `yes`, the services `cv-superset` and `cv-django` start at boot.

The installer does not add a Redis server, Celery, a Superset worker, Docker, a firewall, Let's Encrypt (certbot), example data, or theming. nginx is the optional web server from the decision in [../DECISIONS.md](../DECISIONS.md). It is installed only when you choose HTTP or HTTPS. No second proxy is added. The `redis` and `celery` Python libraries are installed only because Superset depends on them, and nothing runs them. It does not install or run the loader, and it does not set up SFTP. The loader runs from a checkout of this repo; see [sftp-and-extracts.md](sftp-and-extracts.md).

## Where the passwords live

- Every secret goes in `/etc/campusview/campusview.env`. The file holds the two app database passwords, the `campusview_reader` password, the `campusview_owner` password, the Superset secret key, and the admin password. It also stores the non-secret answers, such as the ports, the install folder, and the branch or tag in `CV_REF`.
- The file mode is 600, so only the Linux account that runs CampusView can read it. The folder `/etc/campusview` is mode 700 and owned by that same account.
- systemd loads the file when the services start. `start.sh` loads it when you start the apps without systemd. The Superset config and Django's `settings.py` read the values from the environment. The installer writes no password into either file.
- Django's own `SECRET_KEY` is the exception. Django generates it and it stays in `settings.py`, so that file is mode 600. Do not copy it into git.
- To see a saved password later, read the file on the server as root or as the account that runs CampusView. Never copy a password into either git repo.

## When it finishes

The installer checks three pages and the three databases. Superset's health page, the Superset sign-in page, and the Django admin sign-in page must each answer. The databases `superset_meta`, `django_app`, and `campusview_data` must exist. Then it prints `INSTALL OK`, the addresses, and a short DBeaver block with the same facts as above.

With HTTP or HTTPS, the done screen prints the two addresses to open, for example `https://10.0.0.25/` for Superset and `https://10.0.0.25/app/` for the Django admin page. Sign in with the admin username and password. With a self-signed certificate, the browser warns the first time. See below.

With the SSH tunnel choice, everything listens on `127.0.0.1` only. To open the pages from your computer, run this, then open `http://127.0.0.1:8088` and `http://127.0.0.1:8000/admin/`.

```bash
ssh -L 8088:127.0.0.1:8088 -L 8000:127.0.0.1:8000 you@server
```

Use the ports you chose if they are not `8088` and `8000`. Sign in with the admin username and password.

## How people reach CampusView

The wizard asks `How should people reach CampusView?` right after the ports.

| Choice | What you open | What listens on the network |
|---|---|---|
| 1) Only from this server (SSH tunnel) | `http://127.0.0.1:8088` and `http://127.0.0.1:8000/admin/` through an SSH tunnel | Nothing new. nginx is not installed. |
| 2) HTTP on port 80 | `http://NAME/` (Superset) and `http://NAME/app/` (Django admin) | nginx on port 80 |
| 3) HTTPS on port 443 (recommended, the default) | `https://NAME/` and `https://NAME/app/` | nginx on port 443, and on port 80 only to send people to https |

`NAME` is the answer to `Server name or IP address`. It defaults to the server's main IP address. Use a DNS name if people have one for the server.

In every mode, Superset, Django (gunicorn) and PostgreSQL keep listening on `127.0.0.1` only. nginx passes `/` to Superset and `/app/` to Django. DBeaver still connects through the SSH tunnel, exactly as above.

HTTP sends passwords across the network unencrypted. Use it only for testing with fake data. The one exception is Austin's on-prem dev server during early testing; it moves to HTTPS before production gets Google sign-on or real users. Production uses HTTPS.

### Certificates for HTTPS

- **Self-signed (the default).** The installer makes a certificate for the server name or IP, plus the server's hostname, valid for 10 years. Browsers warn that the connection isn't private. Choose Advanced, then Continue (or Proceed, or Accept the risk). The done screen prints the certificate's SHA-256 fingerprint so you can check it's this server.
- **Your own.** Give the full path to the certificate file (PEM, with any intermediate certificates) and to the private key file (PEM, no passphrase). The installer checks that both exist, that the key matches the certificate, and that the certificate hasn't expired. If any check fails, it stops before it changes anything. It copies both into `/etc/campusview/tls/`. When you renew the certificate, run the installer again with the new files.

The key is stored as `/etc/campusview/tls/campusview.key`, mode 600, owned by root, in a folder only root can open.

### Changing the choice later

Run the installer again. It shows `Saved: ...` and asks `Change how people reach CampusView? (yes/no) [no]`. Answer `yes` to choose again. With an answers file, set `CV_ACCESS` (and the other network settings listed under [Run it from an answers file](#run-it-from-an-answers-file)) in the file; those win over the saved ones. Switching to the SSH tunnel removes the CampusView nginx site, and stops nginx if it has no other sites.

No student data is needed for this check.

## Run the installer again


Run the same command. The saved answers show up as the defaults, including the install folder and the branch or tag. The two behind-the-scenes database password prompts say `Enter = keep the saved one`.

Questions 9 to 14 are not asked again. That is the two report data passwords, the secret key, and the admin login. Under the heading `Report data accounts, Superset secret key and your admin login` you see `Kept from the first install`, with the admin username, and `They are not asked again.`

Nothing is reset or duplicated. Existing admins are left unchanged. The databases and their data stay as they are. The database accounts, schemas, and permissions are checked and kept.

A second run has not been tested after a change to the install folder, the Linux account, or a port. Leave those as they were.

## Upgrade an older install

An earlier installer made `superset_user` the owner of `campusview_data`. Run the current `install.sh` on that server. It creates `campusview_owner` and `campusview_reader` with new passwords, saves those passwords in the password file, and hands `campusview_data` and everything in it to `campusview_owner`. Superset keeps working. The install folder you already chose is kept.

If the database still has a schema named `mapping`, and `ref` does not exist yet, the same run renames `mapping` to `ref`.

If you had already added a Superset data connection to `campusview_data` as `superset_user`, that connection stops working. Switch it to `campusview_reader`.

This older-layout upgrade was tested once, on Debian 12.

## Update the server

On the dev server, leave `CV_REF` as `dev` and run the update command.

```bash
sudo bash /opt/campusview/install.sh --update
```

On production, change the `CV_REF` line in `/etc/campusview/campusview.env` to the release tag. Keep the quotes. Leave every other line alone.

```bash
CV_REF='v1.3.0'
```

After you save that line, run the same update command. To go back to an older tag, run this.

```bash
sudo bash /opt/campusview/install.sh --update --allow-downgrade
```

A failed database update puts the previous checkout back and restarts it. The command does not change the password file, the SFTP drop, or the database data.

## Run it from an answers file

You can skip the questions.

```bash
sudo CV_NONINTERACTIVE=1 CV_ANSWERS=/path/answers.env ./install.sh
```

On Debian as root, leave off `sudo`. The answers-file run does not ask `Go ahead?`.

The file uses the same names as the saved password file.

- `CV_RUN_USER`
- `CV_INSTALL_DIR`, default `/opt/campusview`
- `CV_REF`, default `dev`. The dev server keeps `dev`. Production puts a release tag here, such as `v1.3.0`.
- `CV_PG_PORT`, `CV_SUPERSET_PORT`, `CV_DJANGO_PORT`
- `CV_SUPERSET_DB_PASSWORD`, `CV_DJANGO_DB_PASSWORD`, `CV_READER_DB_PASSWORD`, `CV_OWNER_DB_PASSWORD`, `CV_SECRET_KEY`
- `CV_ADMIN_USER`, `CV_ADMIN_EMAIL`, `CV_ADMIN_PASSWORD`
- `CV_SYSTEMD`, and `CV_SUPERSET_WORKERS`. The worker count is answers-file only. The default is 4.
- `CV_ACCESS`: `tunnel`, `http`, or `https` (default `https` on a new install). `CV_SERVER_NAME`: blank means the server's main IP address. `CV_TLS_CERT_SOURCE`: `selfsigned` (default) or `own`, with `CV_TLS_CERT_FILE` and `CV_TLS_KEY_FILE` for `own`.

`install.answers.example` in the repo root is a sample. Its secrets are blank. Leave any password out and the installer generates one. Do not use that sample on a real server until you set the Linux account and the admin email for that server. If the saved file `/etc/campusview/campusview.env` already exists, its values win over the answers file, except the network settings: a `CV_ACCESS`, `CV_SERVER_NAME` or `CV_TLS_*` value in the answers file replaces the saved one, so you can change modes. An install from before this question that runs again from an answers file without `CV_ACCESS` stays on the SSH tunnel.

## The testing install

The testing install is the builder's own computer, or a separate fake-data server later, loaded with Infinite Campus training-database extracts that Austin supplies. It is not part of this installer. It is never the dev server. Production and the dev server do not load those files, and they never get the sandbox database user.

## Uninstall

This installer does not remove CampusView. To stop the apps, run `stop.sh` in the install folder. Run it as root or as the CampusView account. As root it uses `runuser`. Otherwise it uses `sudo`. If neither works, it tells you to run it as root or as that account. If you answered `yes` to start at boot, stop the services `cv-superset` and `cv-django` instead.

Dropping the `campusview_data` database deletes the warehouse. The district repo is a separate checkout and is not removed.
