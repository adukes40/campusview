#!/usr/bin/env bash
# CampusView bare-bones installer: PostgreSQL + Superset 6.1.0 + Django 6.1.2 (both on Python 3.12).
# Debian 12 / Ubuntu 22.04 / Ubuntu 24.04. PostgreSQL 17 comes from postgresql.org's apt repo. Default folder /opt/campusview. Run as root: `sudo ./install.sh` (Debian as root: `./install.sh`).
#
# Interactive:      sudo ./install.sh                       (a short wizard asks the questions)
# Non-interactive:  sudo CV_NONINTERACTIVE=1 CV_ANSWERS=/path/answers.env ./install.sh
#
# All answers, including the secrets, are saved to /etc/campusview/campusview.env, mode 0600, readable only by
# the Linux account that runs CampusView (root on a default Debian install).
# Secrets are never printed and never put on a command line. Re-running reuses the saved values.
set -Eeuo pipefail
trap 'echo "ERROR: line $LINENO: $BASH_COMMAND" >&2' ERR
[ "$(id -u)" -eq 0 ] || { echo "Please run as root: sudo $0" >&2; exit 1; }

ENVF=/etc/campusview/campusview.env
SUPERSET_VER=6.1.0; DJANGO_VER=6.1.2; PY=3.12   # one Python for both apps

# ---------- answers: answers file, then saved values from a previous run (saved values win) ----------
: "${CV_ANSWERS:=}"; : "${CV_NONINTERACTIVE:=0}"
if [ -n "$CV_ANSWERS" ]; then [ -f "$CV_ANSWERS" ] || { echo "answers file $CV_ANSWERS not found" >&2; exit 1; }; . "$CV_ANSWERS"; fi
RERUN=no; if [ -f "$ENVF" ]; then . "$ENVF"; RERUN=yes; fi
: "${CV_RUN_USER:=${SUDO_USER:-root}}"
: "${CV_INSTALL_DIR:=/opt/campusview}"; : "${CV_PG_PORT:=5432}"; : "${CV_SUPERSET_PORT:=8088}"; : "${CV_DJANGO_PORT:=8000}"
: "${CV_SUPERSET_WORKERS:=4}"; : "${CV_SUPERSET_DB_USER:=superset_user}"; : "${CV_DJANGO_DB_USER:=django_user}"
: "${CV_SUPERSET_DB_PASSWORD:=}"; : "${CV_DJANGO_DB_PASSWORD:=}"; : "${CV_SECRET_KEY:=}"
: "${CV_OWNER_DB_PASSWORD:=}"; : "${CV_READER_DB_PASSWORD:=}"   # campusview_owner / campusview_reader (campusview_data)
: "${CV_ADMIN_USER:=admin}"; : "${CV_ADMIN_EMAIL:=}"; : "${CV_ADMIN_PASSWORD:=}"
HAS_SYSTEMD=no; [ -d /run/systemd/system ] && HAS_SYSTEMD=yes
: "${CV_SYSTEMD:=$HAS_SYSTEMD}"

# value rules (shared by the wizard and the answers file)
RE_PORT='^[0-9]{2,5}$'; RE_YN='^(yes|no)$'; RE_NAME='^[A-Za-z0-9_.@+-]+$'
RE_SECRET='^[^'"'"'\[:space:]]{8,}$'   # 8+ chars, no spaces, no ' or \

say(){ printf '\n==> %s\n' "$*"; }
section(){ printf '\n--- %s ---\n' "$1"; }   # wizard section heading
die(){ echo "FATAL: $*" >&2; exit 1; }

ask(){ # ask VAR REGEX "Prompt" ["help line"] [secret]
  local var=$1 re=$2 prompt=$3 help=${4:-} secret=${5:-} ans again
  [ "$CV_NONINTERACTIVE" = 1 ] && return 0
  [ -n "$help" ] && printf '\n  %s\n' "$help"
  while :; do
    if [ -n "$secret" ]; then
      local hint="Enter = make one for me"; [ -n "${!var}" ] && hint="Enter = keep the saved one"
      read -r -s -p "  $prompt [$hint]: " ans; echo
      [ -z "$ans" ] && return 0
      [[ $ans =~ $re ]] || { echo "  Use at least 8 characters, with no spaces, quotes or backslashes."; continue; }
      read -r -s -p "  Type it again: " again; echo
      [ "$ans" = "$again" ] || { echo "  Those didn't match. Try again."; continue; }
    else
      read -r -p "  $prompt [${!var}]: " ans; ans=${ans:-${!var}}
      [[ $ans =~ $re ]] || { echo "  \"$ans\" isn't a valid answer here."; continue; }
    fi
    printf -v "$var" '%s' "$ans"; return 0
  done
}

. /etc/os-release
case "$ID:$VERSION_ID" in debian:12|ubuntu:22.04|ubuntu:24.04) ;; *) echo "WARNING: untested OS $PRETTY_NAME";; esac
if [ "$CV_NONINTERACTIVE" != 1 ]; then
  [ -t 0 ] || die "no terminal for the wizard; use CV_NONINTERACTIVE=1 CV_ANSWERS=answers.env"
  cat <<B
==============================================================
 CampusView installer   ($PRETTY_NAME)
 Installs PostgreSQL, Superset $SUPERSET_VER and Django $DJANGO_VER.
 Press Enter to accept the value in [brackets].
 Passwords you type are not shown on screen.
==============================================================
B
  [ $RERUN = yes ] && echo " Found saved settings from an earlier install; they are the defaults."
  section "Where CampusView goes"
  ask CV_RUN_USER "$RE_NAME" "Linux account that runs CampusView" "An existing login on this server. The apps run as this account, and it owns their files and the password file."
  until getent passwd "$CV_RUN_USER" >/dev/null; do echo "  There is no Linux user called $CV_RUN_USER."; ask CV_RUN_USER "$RE_NAME" "Linux account that runs CampusView"; done
  ask CV_INSTALL_DIR '^/' "Install folder" "Where the programs go. It is created for you, owned by that account."
  section "Network ports"
  ask CV_PG_PORT "$RE_PORT" "Database (PostgreSQL) port" "Keep these unless something else on this server already uses them."
  ask CV_SUPERSET_PORT "$RE_PORT" "Superset web page port"
  ask CV_DJANGO_PORT "$RE_PORT" "Django admin page port"
  section "Behind-the-scenes database passwords"
  printf '\n  Superset and Django each sign in to the database with their own account.\n  Only the apps use these. You never type them. Press Enter to have them made for you.\n'
  ask CV_SUPERSET_DB_PASSWORD "$RE_SECRET" "Password Superset uses for the database" "" secret
  ask CV_DJANGO_DB_PASSWORD "$RE_SECRET" "Password Django uses for the database" "" secret
  if [ $RERUN = no ]; then   # changing these after the first install would break logins or saved data
    section "Report data accounts (database campusview_data)"
    printf '\n  Two database logins for the report data. Press Enter to have them made for you.\n'
    ask CV_READER_DB_PASSWORD "$RE_SECRET" "Password for campusview_reader" "campusview_reader: what Superset uses to read report data; also safe for DBeaver." secret
    ask CV_OWNER_DB_PASSWORD "$RE_SECRET" "Password for campusview_owner" "campusview_owner: full access to the data, used by the loader; use with care." secret
    section "Superset secret key"
    printf '\n  Locks (encrypts) the connection details Superset saves. Never change it after\n  the first install, or Superset can no longer read them. Press Enter to have one made.\n'
    ask CV_SECRET_KEY "$RE_SECRET" "Superset secret key" "" secret
    section "Your admin login"
    printf '\n  The username and password YOU sign in with, on both the Superset web page\n  and the Django admin page.\n'
    ask CV_ADMIN_USER "$RE_NAME" "Admin username"
    [ -z "$CV_ADMIN_EMAIL" ] && CV_ADMIN_EMAIL="$CV_ADMIN_USER@example.invalid"
    ask CV_ADMIN_EMAIL '^[^[:space:]]+@[^[:space:]]+$' "Admin email"
    ask CV_ADMIN_PASSWORD "$RE_SECRET" "Admin password" "" secret
  else
    section "Report data accounts, Superset secret key and your admin login"
    printf '\n  Kept from the first install (admin username: %s). They are not asked again.\n' "$CV_ADMIN_USER"
  fi
  section "Starting up"
  ask CV_SYSTEMD "$RE_YN" "Start CampusView automatically when the server boots (yes/no)"
fi

# ---------- validate, fill in generated secrets ----------
chk(){ [[ ${!1} =~ $2 ]] || die "$1 has an invalid value"; }
[ -z "$CV_SUPERSET_DB_PASSWORD" ] && CV_SUPERSET_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_DJANGO_DB_PASSWORD" ] && CV_DJANGO_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_OWNER_DB_PASSWORD" ] && CV_OWNER_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_READER_DB_PASSWORD" ] && CV_READER_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_SECRET_KEY" ] && CV_SECRET_KEY=$(openssl rand -base64 42)
[ -z "$CV_ADMIN_PASSWORD" ] && CV_ADMIN_PASSWORD=$(openssl rand -hex 10)
[ -z "$CV_ADMIN_EMAIL" ] && CV_ADMIN_EMAIL="$CV_ADMIN_USER@example.invalid"
chk CV_INSTALL_DIR '^/'; chk CV_SYSTEMD "$RE_YN"
for v in CV_PG_PORT CV_SUPERSET_PORT CV_DJANGO_PORT; do chk $v "$RE_PORT"; done
for v in CV_RUN_USER CV_ADMIN_USER CV_SUPERSET_DB_USER CV_DJANGO_DB_USER; do chk $v "$RE_NAME"; done
for v in CV_SUPERSET_DB_PASSWORD CV_DJANGO_DB_PASSWORD CV_OWNER_DB_PASSWORD CV_READER_DB_PASSWORD CV_SECRET_KEY CV_ADMIN_PASSWORD; do chk $v "$RE_SECRET"; done
getent passwd "$CV_RUN_USER" >/dev/null || die "Linux user $CV_RUN_USER does not exist"
[ "$CV_SYSTEMD" = yes ] && [ "$HAS_SYSTEMD" = no ] && { echo "systemd is not running here; using start.sh instead."; CV_SYSTEMD=no; }

if [ "$CV_NONINTERACTIVE" != 1 ]; then
  cat <<S

  Ready to install:
    Folder:        $CV_INSTALL_DIR   (apps run as $CV_RUN_USER)
    PostgreSQL:    17, port $CV_PG_PORT
    Superset:      http://127.0.0.1:$CV_SUPERSET_PORT
    Django admin:  http://127.0.0.1:$CV_DJANGO_PORT/admin/
    Admin login:   $CV_ADMIN_USER ($CV_ADMIN_EMAIL)
    Start at boot: $CV_SYSTEMD
    Passwords:     saved to $ENVF (only $CV_RUN_USER can read it)
S
  read -r -p "  Go ahead? [Y/n]: " ans; case ${ans:-y} in [Yy]*) ;; *) echo "Nothing was changed."; exit 0;; esac
fi

# ---------- save answers + secrets (0600, owned by the account that runs CampusView) ----------
mkdir -p -m 700 /etc/campusview; chown "$CV_RUN_USER": /etc/campusview
( umask 077; tmp=$(mktemp /etc/campusview/.env.XXXXXX)
  for v in CV_INSTALL_DIR CV_RUN_USER CV_PG_PORT CV_SUPERSET_PORT CV_DJANGO_PORT CV_SUPERSET_WORKERS \
           CV_SUPERSET_DB_USER CV_DJANGO_DB_USER CV_ADMIN_USER CV_ADMIN_EMAIL CV_SYSTEMD \
           CV_SUPERSET_DB_PASSWORD CV_DJANGO_DB_PASSWORD CV_OWNER_DB_PASSWORD CV_READER_DB_PASSWORD \
           CV_SECRET_KEY CV_ADMIN_PASSWORD; do
    printf "%s='%s'\n" "$v" "${!v}"; done > "$tmp"
  chown "$CV_RUN_USER": "$tmp"; mv "$tmp" "$ENVF" )
set -a; . "$ENVF"; set +a      # the apps read their secrets from these environment variables
B=$CV_INSTALL_DIR; S=$B/superset; D=$B/django
as_run(){ if [ "$CV_RUN_USER" = root ]; then "$@"; else runuser -u "$CV_RUN_USER" -- "$@"; fi; }
as_pg(){ (cd /tmp && runuser -u postgres -- "$@"); }

# ---------- 1. packages ----------
say "1. system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update </dev/null
apt-get install -y build-essential libssl-dev libffi-dev libsasl2-dev libldap2-dev \
  default-libmysqlclient-dev pkg-config libpq-dev curl ca-certificates gnupg openssl git </dev/null

# ---------- 2. PostgreSQL ----------
say "2. PostgreSQL 17"
# PostgreSQL's own apt repo over https (the helper script in Ubuntu 22.04's postgresql-common still uses http)
if [ ! -f /etc/apt/sources.list.d/pgdg.list ]; then
  install -d /usr/share/postgresql-common/pgdg
  curl -fsS -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc https://www.postgresql.org/media/keys/ACCC4CF8.asc
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $VERSION_CODENAME-pgdg main" > /etc/apt/sources.list.d/pgdg.list
  apt-get update </dev/null
fi
apt-get install -y postgresql-17 </dev/null
PGV=17; CONF=/etc/postgresql/$PGV/main/postgresql.conf
grep -q "^port = $CV_PG_PORT\b" "$CONF" || { sed -i "s/^port = .*/port = $CV_PG_PORT/" "$CONF"; PG_RESTART=1; }
grep -q "^listen_addresses = '127.0.0.1'" "$CONF" || { echo "listen_addresses = '127.0.0.1'" >> "$CONF"; PG_RESTART=1; }  # IPv4 loopback only
if [ "$HAS_SYSTEMD" = yes ]; then systemctl enable postgresql
  if [ "${PG_RESTART:-0}" = 1 ]; then systemctl restart postgresql; else systemctl start postgresql; fi
else pg_ctlcluster "$PGV" main restart; fi
for i in $(seq 30); do pg_isready -q -h 127.0.0.1 -p "$CV_PG_PORT" && break; sleep 1; done

# ---------- 3. roles + databases (idempotent; passwords go in on stdin, never argv) ----------
say "3. database roles and databases"
psqlq(){ as_pg psql -p "$CV_PG_PORT" -v ON_ERROR_STOP=1 -qAt "$@"; }
mkrole(){ local r=$1 p=$2
  [ "$(psqlq -c "SELECT 1 FROM pg_roles WHERE rolname='$r'")" = 1 ] || psqlq -c "CREATE ROLE $r LOGIN"
  psqlq <<<"ALTER ROLE $r WITH LOGIN PASSWORD '${p//\'/\'\'}';"; }
mkdb(){ [ "$(psqlq -c "SELECT 1 FROM pg_database WHERE datname='$1'")" = 1 ] || psqlq -c "CREATE DATABASE $1 OWNER $2"; }
mkrole "$CV_SUPERSET_DB_USER" "$CV_SUPERSET_DB_PASSWORD"
mkrole "$CV_DJANGO_DB_USER" "$CV_DJANGO_DB_PASSWORD"
mkrole campusview_owner "$CV_OWNER_DB_PASSWORD"
mkrole campusview_reader "$CV_READER_DB_PASSWORD"
mkdb superset_meta "$CV_SUPERSET_DB_USER"; mkdb django_app "$CV_DJANGO_DB_USER"; mkdb campusview_data campusview_owner
# campusview_data: owner writes (the Step 1 loader), reader sees the reporting schema only, nobody else connects.
# Every statement is safe to repeat. It also moves an older install, where superset_user owned this database.
psqlq -d campusview_data <<SQL
ALTER DATABASE campusview_data OWNER TO campusview_owner;
REVOKE ALL ON DATABASE campusview_data FROM PUBLIC, $CV_SUPERSET_DB_USER;
GRANT CONNECT ON DATABASE campusview_data TO campusview_reader;
DO \$\$ DECLARE r record; BEGIN
  FOR r IN SELECT nspname FROM pg_namespace WHERE nspowner = '$CV_SUPERSET_DB_USER'::regrole LOOP
    EXECUTE format('ALTER SCHEMA %I OWNER TO campusview_owner', r.nspname); END LOOP;
  FOR r IN SELECT c.oid::regclass AS t, CASE c.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW'
             WHEN 'S' THEN 'SEQUENCE' ELSE 'TABLE' END AS k
           FROM pg_class c WHERE c.relowner = '$CV_SUPERSET_DB_USER'::regrole AND c.relkind IN ('r','p','v','m','S')
             AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('a','i')) LOOP
    EXECUTE format('ALTER %s %s OWNER TO campusview_owner', r.k, r.t); END LOOP;
END \$\$;
CREATE SCHEMA IF NOT EXISTS raw AUTHORIZATION campusview_owner;
CREATE SCHEMA IF NOT EXISTS mapping AUTHORIZATION campusview_owner;
CREATE SCHEMA IF NOT EXISTS reporting AUTHORIZATION campusview_owner;
ALTER SCHEMA raw OWNER TO campusview_owner;
ALTER SCHEMA mapping OWNER TO campusview_owner;
ALTER SCHEMA reporting OWNER TO campusview_owner;
GRANT USAGE ON SCHEMA reporting TO campusview_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO campusview_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE campusview_owner IN SCHEMA reporting GRANT SELECT ON TABLES TO campusview_reader;
SQL

# ---------- 4. uv + Python (kept inside the install folder, not ~/.local) ----------
say "4. uv and Python $PY"
mkdir -p "$S" "$D"; chown "$CV_RUN_USER": "$B" "$S" "$D"
export UV_PYTHON_INSTALL_DIR=$B/.uv/python UV_CACHE_DIR=$B/.uv/cache
[ -x "$B/.uv/bin/uv" ] || as_run env UV_INSTALL_DIR="$B/.uv/bin" UV_NO_MODIFY_PATH=1 sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
as_run "$B/.uv/bin/uv" python install "$PY"

# ---------- 5. Superset ----------
say "5. Superset $SUPERSET_VER"
[ -x "$S/venv/bin/python" ] || as_run "$B/.uv/bin/uv" venv --seed --python "$PY" "$S/venv"
[ -s "$S/constraints-$SUPERSET_VER.txt" ] || as_run sh -c "curl -fsSL https://raw.githubusercontent.com/apache/superset/$SUPERSET_VER/requirements/base.txt | grep -v '^-e' > '$S/constraints-$SUPERSET_VER.txt'"
if ! as_run "$S/venv/bin/pip" show apache_superset 2>/dev/null | grep -q "^Version: $SUPERSET_VER$"; then
  as_run "$S/venv/bin/pip" install -q --upgrade pip
  as_run "$S/venv/bin/pip" install -c "$S/constraints-$SUPERSET_VER.txt" "apache-superset==$SUPERSET_VER" psycopg2-binary
fi
as_run tee "$S/superset_config.py" >/dev/null <<'C'
# Secrets come from /etc/campusview/campusview.env (loaded by systemd or start.sh).
import os
from urllib.parse import quote_plus
SECRET_KEY = os.environ["CV_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://%s:%s@127.0.0.1:%s/superset_meta" % (
    os.environ["CV_SUPERSET_DB_USER"], quote_plus(os.environ["CV_SUPERSET_DB_PASSWORD"]), os.environ["CV_PG_PORT"])
C
export SUPERSET_CONFIG_PATH=$S/superset_config.py FLASK_APP=superset
as_run "$S/venv/bin/superset" db upgrade
as_run "$S/venv/bin/superset" init
# admin user: created from Python so the password is never on a command line
as_run "$S/venv/bin/python" - <<'PY'
import os
from superset.app import create_app
app = create_app()
with app.app_context():
    from superset import security_manager as sm
    u = os.environ["CV_ADMIN_USER"]
    if sm.find_user(username=u):
        print(f"Superset admin '{u}' already exists; left unchanged.")
    else:
        ok = sm.add_user(u, "CampusView", "Admin", os.environ["CV_ADMIN_EMAIL"], sm.find_role("Admin"),
                         password=os.environ["CV_ADMIN_PASSWORD"])
        if not ok: raise SystemExit("could not create the Superset admin")
        print(f"Superset admin '{u}' created.")
PY

# ---------- 6. Django ----------
say "6. Django $DJANGO_VER"
[ -x "$D/venv/bin/python" ] || as_run "$B/.uv/bin/uv" venv --seed --python "$PY" "$D/venv"
as_run "$D/venv/bin/pip" show django 2>/dev/null | grep -q "^Version: $DJANGO_VER$" || \
  as_run "$D/venv/bin/pip" install "Django==$DJANGO_VER" psycopg2-binary gunicorn
[ -f "$D/manage.py" ] || (cd "$D" && as_run venv/bin/django-admin startproject campusview_base .)
# only change to the default project: DATABASES points at PostgreSQL, password read from the environment
as_run "$D/venv/bin/python" - "$D/campusview_base/settings.py" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p).read()
new = """DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'django_app',
        'USER': os.environ['CV_DJANGO_DB_USER'],
        'PASSWORD': os.environ['CV_DJANGO_DB_PASSWORD'],
        'HOST': '127.0.0.1',
        'PORT': os.environ['CV_PG_PORT'],
    }
}
"""
s = re.sub(r"DATABASES = \{.*?\n\}\n", lambda m: new, s, count=1, flags=re.S)
if "\nimport os\n" not in s:
    s = s.replace("from pathlib import Path\n", "import os\nfrom pathlib import Path\n", 1)
open(p, "w").write(s)
PY
as_run chmod 600 "$D/campusview_base/settings.py"
(cd "$D" && as_run venv/bin/python manage.py migrate --noinput)
(cd "$D" && as_run venv/bin/python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model
U = get_user_model(); u = os.environ["CV_ADMIN_USER"]
if U.objects.filter(username=u).exists():
    print(f"Django admin '{u}' already exists; left unchanged.")
else:
    U.objects.create_superuser(u, os.environ["CV_ADMIN_EMAIL"], os.environ["CV_ADMIN_PASSWORD"])
    print(f"Django admin '{u}' created.")
PY
)

# ---------- 7. start/stop scripts (always written; run them as root) ----------
say "7. start.sh / stop.sh"
cat > "$B/start.sh" <<'C'
#!/usr/bin/env bash
# Start Superset and Django without systemd (use systemctl instead if you said yes to start-at-boot).
U=$(stat -c %U /etc/campusview/campusview.env)
[ "$(id -un)" = "$U" ] || exec sudo -u "$U" "$0" "$@"     # run as the account that owns the secrets
set -a; . /etc/campusview/campusview.env; set +a
B=$CV_INSTALL_DIR; export SUPERSET_CONFIG_PATH=$B/superset/superset_config.py
running(){ [ -f "$B/$1.pid" ] && kill -0 "$(cat "$B/$1.pid")" 2>/dev/null; }
running superset || nohup "$B/superset/venv/bin/gunicorn" -w "$CV_SUPERSET_WORKERS" -k gthread --threads 2 --timeout 120 \
  -b "127.0.0.1:$CV_SUPERSET_PORT" --limit-request-line 0 --limit-request-field_size 0 --pid "$B/superset.pid" \
  "superset.app:create_app()" >> "$B/superset.log" 2>&1 &
running django || (cd "$B/django" && nohup "$B/django/venv/bin/gunicorn" -b "127.0.0.1:$CV_DJANGO_PORT" \
  --pid "$B/django.pid" campusview_base.wsgi >> "$B/django.log" 2>&1 &)
echo started
C
cat > "$B/stop.sh" <<'C'
#!/usr/bin/env bash
U=$(stat -c %U /etc/campusview/campusview.env)
[ "$(id -un)" = "$U" ] || exec sudo -u "$U" "$0" "$@"
cd "$(dirname "$0")"; B=$PWD
for p in superset django; do [ -f $B/$p.pid ] && kill "$(cat $B/$p.pid)" 2>/dev/null && echo "stopped $p"; rm -f $B/$p.pid; done
C
chmod 755 "$B/start.sh" "$B/stop.sh"; chown "$CV_RUN_USER": "$B/start.sh" "$B/stop.sh"

# ---------- 8. systemd (optional) or start.sh ----------
if [ "$CV_SYSTEMD" = yes ]; then
  say "8. systemd services"
  as_run "$B/stop.sh" >/dev/null 2>&1 || true
  cat > /etc/systemd/system/cv-superset.service <<C
[Unit]
Description=CampusView Superset
After=postgresql.service
[Service]
User=$CV_RUN_USER
WorkingDirectory=$S
EnvironmentFile=$ENVF
Environment=SUPERSET_CONFIG_PATH=$S/superset_config.py
ExecStart=$S/venv/bin/gunicorn -w $CV_SUPERSET_WORKERS -k gthread --threads 2 --timeout 120 -b 127.0.0.1:$CV_SUPERSET_PORT --limit-request-line 0 --limit-request-field_size 0 "superset.app:create_app()"
Restart=on-failure
[Install]
WantedBy=multi-user.target
C
  cat > /etc/systemd/system/cv-django.service <<C
[Unit]
Description=CampusView Django
After=postgresql.service
[Service]
User=$CV_RUN_USER
WorkingDirectory=$D
EnvironmentFile=$ENVF
ExecStart=$D/venv/bin/gunicorn -b 127.0.0.1:$CV_DJANGO_PORT campusview_base.wsgi
Restart=on-failure
[Install]
WantedBy=multi-user.target
C
  systemctl daemon-reload
  systemctl enable cv-superset cv-django
  systemctl restart cv-superset cv-django
else
  say "8. starting with start.sh"
  as_run "$B/start.sh"
fi

# ---------- 9. verify ----------
say "9. checking everything answers"
code(){ curl -s -o /dev/null -w '%{http_code}' "$1" || true; }
wait200(){ for i in $(seq 60); do [ "$(code "$1")" = 200 ] && return 0; sleep 2; done; return 1; }
ok=1
for u in "http://127.0.0.1:$CV_SUPERSET_PORT/health" "http://127.0.0.1:$CV_SUPERSET_PORT/login/" "http://127.0.0.1:$CV_DJANGO_PORT/admin/login/"; do
  wait200 "$u" || ok=0; echo "  $(code "$u")  $u"; done
dbs=$(psqlq -c "SELECT string_agg(datname, ' ' ORDER BY datname) FROM pg_database WHERE datname IN ('superset_meta','django_app','campusview_data')")
echo "  databases: $dbs"; [ "$(wc -w <<<"$dbs")" = 3 ] || ok=0
if [ $ok = 1 ]; then cat <<E

INSTALL OK
  Superset:      http://127.0.0.1:$CV_SUPERSET_PORT   (log in as $CV_ADMIN_USER)
  Django admin:  http://127.0.0.1:$CV_DJANGO_PORT/admin/
  Passwords:     sudo cat $ENVF
  Everything listens on 127.0.0.1 only.
  From your laptop: ssh -L $CV_SUPERSET_PORT:127.0.0.1:$CV_SUPERSET_PORT -L $CV_DJANGO_PORT:127.0.0.1:$CV_DJANGO_PORT you@this-server

Connect with DBeaver (or another database tool)
  Host 127.0.0.1   Port $CV_PG_PORT   Database campusview_data
  campusview_reader  safe browsing: sees the reporting views only (empty until Step 1)
  campusview_owner   full access to the data; use with care
  Passwords: CV_READER_DB_PASSWORD / CV_OWNER_DB_PASSWORD in $ENVF
  The database only listens on this server, so for either account turn on DBeaver's
  SSH tunnel to this server (or run: ssh -L $CV_PG_PORT:127.0.0.1:$CV_PG_PORT you@this-server).
  Superset's data connection should use campusview_reader.
  django_app and superset_meta belong to the apps. Don't edit them by hand.
E
else echo "INSTALL FINISHED WITH ERRORS (see the lines above)"; exit 1; fi
