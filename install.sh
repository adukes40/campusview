#!/usr/bin/env bash
# CampusView bare-bones installer: PostgreSQL + Superset 6.1.0 + Django 6.1.2 (both on Python 3.12).
# Debian 12 / Ubuntu 22.04 / Ubuntu 24.04. PostgreSQL 17 comes from postgresql.org's apt repo. Default folder /opt/campusview. Run as root: `sudo ./install.sh` (Debian as root: `./install.sh`).
# Network access (CV_ACCESS): tunnel = nothing on the network; http / https = nginx on port 80 / 443 sends / to Superset
# and /app/ to Django. The apps and PostgreSQL always listen on 127.0.0.1 only.
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
DISTRICT=/opt/campusview-district
RE_REF='^[A-Za-z0-9][A-Za-z0-9._/-]{0,80}$'
export GIT_TERMINAL_PROMPT=0

say(){ printf '\n==> %s\n' "$*"; }
section(){ printf '\n--- %s ---\n' "$1"; }
die(){ echo "FATAL: $*" >&2; exit 1; }
as_run(){ if [ "$CV_RUN_USER" = root ]; then "$@"; else runuser -u "$CV_RUN_USER" -- "$@"; fi; }
g(){ as_run git -C "$B" "$@"; }
usage(){ echo "Usage: sudo bash $0 --update [--allow-downgrade]" >&2; exit 1; }
valid_ref(){
  local r=${1:-${CV_REF:-}}
  [[ $r =~ $RE_REF ]] || return 1
  [[ $r == *..* ]] && return 1
  [ "$r" != main ] || return 1
  return 0
}
read_env(){
  [ -f "$ENVF" ] || die "No saved settings in $ENVF. Run install.sh."
  set -a; . "$ENVF"; set +a
  : "${CV_INSTALL_DIR:=/opt/campusview}"
  : "${CV_RUN_USER:=${SUDO_USER:-root}}"
  : "${CV_SYSTEMD:=no}"
  B=$CV_INSTALL_DIR; S=$B/superset; D=$B/django
}
stopped(){ echo "${1:+$1 }The checkout was left as it is." >&2; exit 1; }
classify_fetched_ref(){ # a tag wins when the same name is also a branch
  local tag="refs/tags/$CV_REF" branch="refs/remotes/origin/$CV_REF"
  if g show-ref --verify --quiet "$tag"; then ref_kind=tag; target=$(g rev-parse --verify "${tag}^{}")
  elif g show-ref --verify --quiet "$branch"; then ref_kind=branch; target=$(g rev-parse --verify "$branch")
  else stopped "$CV_REF is not a branch or a tag on the remote."; fi
}
have_python(){
  [ -x "$B/.uv/bin/uv" ] || return 1
  local f
  f=$(find "$B/.uv/python" -name 'python3.12' -print -quit 2>/dev/null || true)
  [ -n "$f" ] && [ -x "$f" ]
}
pkg_ver(){ as_run "$1" show "$2" 2>/dev/null | sed -n 's/^Version: //p'; }
sync_superset(){
  export UV_PYTHON_INSTALL_DIR=$B/.uv/python UV_CACHE_DIR=$B/.uv/cache
  [ -x "$S/venv/bin/python" ] || as_run "$B/.uv/bin/uv" venv --seed --python "$PY" "$S/venv" || return 1
  [ -s "$S/constraints-$SUPERSET_VER.txt" ] || as_run sh -c "curl -fsSL https://raw.githubusercontent.com/apache/superset/$SUPERSET_VER/requirements/base.txt | grep -v '^-e' > '$S/constraints-$SUPERSET_VER.txt'" || return 1
  # sed reads the whole pip listing. grep -q would close the pipe early and, with pipefail, look like a missing package.
  if [ "$(pkg_ver "$S/venv/bin/pip" apache_superset)" != "$SUPERSET_VER" ]; then
    as_run "$S/venv/bin/pip" install -q --upgrade pip || return 1
    as_run "$S/venv/bin/pip" install -c "$S/constraints-$SUPERSET_VER.txt" "apache-superset==$SUPERSET_VER" psycopg2-binary || return 1
  fi
}
sync_django(){
  export UV_PYTHON_INSTALL_DIR=$B/.uv/python UV_CACHE_DIR=$B/.uv/cache
  [ -x "$D/venv/bin/python" ] || as_run "$B/.uv/bin/uv" venv --seed --python "$PY" "$D/venv" || return 1
  [ "$(pkg_ver "$D/venv/bin/pip" django)" = "$DJANGO_VER" ] || \
    as_run "$D/venv/bin/pip" install "Django==$DJANGO_VER" psycopg2-binary gunicorn || return 1
}
quiet(){ local out; out=$("$@" 2>&1) || { printf '%s\n' "$out" >&2; return 1; }; }
upgrade_superset_db(){
  export SUPERSET_CONFIG_PATH=$S/superset_config.py FLASK_APP=superset
  as_run "$S/venv/bin/superset" db upgrade
}
migrate_django(){ (cd "$D" && as_run venv/bin/python manage.py migrate --noinput); }
restart_apps(){
  if [ "$CV_SYSTEMD" = yes ]; then systemctl restart cv-superset cv-django
  else as_run "$B/stop.sh" >/dev/null 2>&1 || true; as_run "$B/start.sh"; fi
}
# campusview.running is the commit that finished a restart. A failed restart leaves it unset, so the next run retries.
mark_running(){ g config --local campusview.running "$(g rev-parse HEAD)"; }
pull_district(){
  if [ ! -e "$DISTRICT/.git" ]; then echo "No district checkout at $DISTRICT. Skipped."; return 0; fi
  local err
  err=$(as_run git -C "$DISTRICT" pull --ff-only 2>&1) || {
    case $err in
      *dubious\ ownership*) echo "Git refused the district checkout because of dubious ownership." >&2; printf '%s\n' "$err" >&2 ;;
      *) echo "The district repo did not fast-forward." >&2 ;;
    esac
    stopped; }
}
create_checkout(){
  mkdir -p -- "$B"; chown "$CV_RUN_USER": "$B"
  if [ -e "$B/.git" ] && g rev-parse --verify -q HEAD >/dev/null 2>&1; then return 0; fi
  local script root
  script=$(readlink -f -- "$0"); root=$(readlink -f -- "$B")
  case $script in "$root"|"$root"/*) die "Copy install.sh out of $B and run that copy." ;; esac
  say "checkout $CV_REF"
  [ -e "$B/.git" ] || g init -q
  g remote get-url origin >/dev/null 2>&1 || g remote add origin "${CV_REPO:-https://github.com/adukes40/campusview.git}"
  g fetch origin --tags
  classify_fetched_ref
  g checkout --detach "$target" || die "Could not check out $CV_REF."
}
update_main(){
  local allow_down=no tmp head running previous
  case ${2:-} in
    "") ;;
    --allow-downgrade) allow_down=yes ;;
    *) usage ;;
  esac
  [ "$#" -le 2 ] || usage
  case $0 in
    /tmp/campusview-update.*) rm -f -- "$0" ;;
    *)
      # Bash reads this file as it runs, so checkout must not replace the copy that is executing.
      tmp=$(mktemp /tmp/campusview-update.XXXXXX)
      cp -- "$0" "$tmp"; chmod 700 "$tmp"
      exec bash "$tmp" "$@" ;;
  esac
  read_env
  if [ -z "${CV_REF:-}" ]; then
    die "CV_REF is not set. Run install.sh once, for example: sudo CV_REF=dev bash ./install.sh"
  fi
  valid_ref || die "CV_REF has an invalid value ($CV_REF). Use dev, or a release tag. No server uses main."
  if [ ! -e "$B/.git" ] || ! g rev-parse --verify -q HEAD >/dev/null 2>&1; then
    die "This folder has no CampusView checkout yet. Run install.sh once, for example: sudo CV_REF=dev bash ./install.sh"
  fi
  if ! g diff --quiet HEAD || ! g diff --cached --quiet; then stopped "The checkout has local edits."; fi
  g fetch origin --tags
  classify_fetched_ref
  head=$(g rev-parse HEAD)
  running=$(g config --local --get campusview.running 2>/dev/null || true)
  previous=$head
  if [ "$head" != "$target" ]; then
    if [ "$ref_kind" = branch ]; then
      g merge-base --is-ancestor "$head" "$target" || stopped "Branch $CV_REF is not a straight step forward."
    elif g merge-base --is-ancestor "$target" "$head"; then
      [ "$allow_down" = yes ] || stopped "Tag $CV_REF is behind the version already installed. To go back, run the same command with --allow-downgrade."
    fi
  fi
  pull_district
  if [ "$head" = "$target" ] && [ "$running" = "$head" ]; then
    echo "Already on $CV_REF at ${head:0:12}. Nothing to do."; exit 0
  fi
  if [ "$head" != "$target" ]; then
    g checkout --detach "$target" || die "Could not check out $CV_REF."
  fi
  # The checked-out install.sh carries this release's package versions. The copy above is the previous one.
  CV_APPLY=1 exec bash -- "$B/install.sh" --apply "$previous"
}
apply_main(){
  local previous now
  [ "${CV_APPLY:-}" = 1 ] || usage
  [ "$#" -eq 2 ] || usage
  previous=$2
  [[ $previous =~ ^[0-9a-f]{40}$ ]] || usage
  read_env
  if ! have_python; then echo "Python 3.12 is not in the install folder. Run install.sh." >&2; exit 1; fi
  if ! sync_superset || ! sync_django; then
    g checkout --detach "$previous" || die "Could not put the checkout back."
    echo "Installing packages failed. The checkout was put back. Services were not restarted." >&2; exit 1
  fi
  if ! quiet upgrade_superset_db || ! quiet migrate_django; then
    g checkout --detach "$previous" || die "Could not put the checkout back."
    restart_apps || true
    echo "The database update failed. CampusView is running the previous checkout. Python packages may already be the newer ones." >&2; exit 1
  fi
  restart_apps || { echo "The new checkout is in place, and the services did not restart. Run the update command again." >&2; exit 1; }
  mark_running
  now=$(g rev-parse HEAD)
  echo "Updated $CV_REF from ${previous:0:12} to ${now:0:12}. Services restarted."
  exit 0
}

case ${1:-} in
  "") ;;
  --update) update_main "$@"; exit 1 ;;
  --apply) apply_main "$@"; exit 1 ;;
  *) usage ;;
esac

setting_get(){
  [ -f "$DISTRICT/settings" ] || return 0
  sed -n "s/^$1=//p" "$DISTRICT/settings" | head -n 1
}
sftp_settings_match(){
  [ "$(setting_get sftp_host)" = "$CV_SFTP_HOST" ] &&
  [ "$(setting_get sftp_port)" = "$CV_SFTP_PORT" ] &&
  [ "$(setting_get sftp_user)" = "$CV_SFTP_USER" ] &&
  [ "$(setting_get sftp_folder)" = "$CV_SFTP_FOLDER" ] &&
  [ "$(setting_get sftp_auth)" = "$CV_SFTP_AUTH" ]
}
write_sftp_settings(){
  sftp_settings_match && return 0
  if [ ! -d "$DISTRICT" ]; then
    mkdir -p -m 755 -- "$DISTRICT"
    chown "$CV_RUN_USER": "$DISTRICT"
  fi
  local tmp
  tmp=$(mktemp)
  if [ -f "$DISTRICT/settings" ]; then
    grep -v -E '^(sftp_host|sftp_port|sftp_user|sftp_folder|sftp_auth)=' "$DISTRICT/settings" > "$tmp" || true
  fi
  printf 'sftp_host=%s\nsftp_port=%s\nsftp_user=%s\nsftp_folder=%s\nsftp_auth=%s\n' \
    "$CV_SFTP_HOST" "$CV_SFTP_PORT" "$CV_SFTP_USER" "$CV_SFTP_FOLDER" "$CV_SFTP_AUTH" >> "$tmp"
  chown "$CV_RUN_USER": "$tmp"
  chmod 644 "$tmp"
  mv "$tmp" "$DISTRICT/settings"
}
ask_sftp_password(){
  local ans again
  while :; do
    read -r -s -p "  SFTP password (not shown): " ans; echo
    [[ $ans =~ $RE_SECRET ]] || { echo "  Use at least 8 characters, with no spaces, quotes (' or \") or backslashes."; continue; }
    read -r -s -p "  Type it again: " again; echo
    [ "$ans" = "$again" ] || { echo "  Those didn't match. Try again."; continue; }
    CV_SFTP_PASSWORD=$ans
    return 0
  done
}

# ---------- answers: answers file, then saved values from a previous run (saved values win) ----------
: "${CV_ANSWERS:=}"; : "${CV_NONINTERACTIVE:=0}"
if [ -n "$CV_ANSWERS" ]; then [ -f "$CV_ANSWERS" ] || { echo "answers file $CV_ANSWERS not found" >&2; exit 1; }; . "$CV_ANSWERS"; fi
# The network answers are the exception: one given in the answers file (or the environment) wins over the saved one,
# so a re-run can switch between tunnel, http and https.
NETV="CV_ACCESS CV_SERVER_NAME CV_TLS_CERT_SOURCE CV_TLS_CERT_FILE CV_TLS_KEY_FILE"; declare -A GIVEN=()
for v in $NETV; do [ -n "${!v:-}" ] && GIVEN[$v]=${!v}; done
RERUN=no; NET_SAVED=no
if [ -f "$ENVF" ]; then . "$ENVF"; RERUN=yes; grep -q "^CV_ACCESS='[a-z]" "$ENVF" && NET_SAVED=yes; fi
for v in "${!GIVEN[@]}"; do printf -v "$v" '%s' "${GIVEN[$v]}"; done
: "${CV_RUN_USER:=${SUDO_USER:-root}}"
: "${CV_INSTALL_DIR:=/opt/campusview}"; : "${CV_PG_PORT:=5432}"; : "${CV_SUPERSET_PORT:=8088}"; : "${CV_DJANGO_PORT:=8000}"
if [ -z "${CV_REF+x}" ]; then CV_REF=dev; fi
: "${CV_SUPERSET_WORKERS:=4}"; : "${CV_SUPERSET_DB_USER:=superset_user}"; : "${CV_DJANGO_DB_USER:=django_user}"
: "${CV_SUPERSET_DB_PASSWORD:=}"; : "${CV_DJANGO_DB_PASSWORD:=}"; : "${CV_SECRET_KEY:=}"
: "${CV_OWNER_DB_PASSWORD:=}"; : "${CV_READER_DB_PASSWORD:=}"   # campusview_owner / campusview_reader (campusview_data)
: "${CV_ADMIN_USER:=admin}"; : "${CV_ADMIN_EMAIL:=}"; : "${CV_ADMIN_PASSWORD:=}"
HAS_SYSTEMD=no; [ -d /run/systemd/system ] && HAS_SYSTEMD=yes
: "${CV_SYSTEMD:=$HAS_SYSTEMD}"
: "${CV_ACCESS:=}"; : "${CV_SERVER_NAME:=}"; : "${CV_TLS_CERT_SOURCE:=selfsigned}"; : "${CV_TLS_CERT_FILE:=}"; : "${CV_TLS_KEY_FILE:=}"
: "${CV_SFTP_HOST:=}"; : "${CV_SFTP_PORT:=}"; : "${CV_SFTP_USER:=}"; : "${CV_SFTP_FOLDER:=}"; : "${CV_SFTP_AUTH:=}"
: "${CV_SFTP_PASSWORD:=}"; : "${CV_SFTP_KEY:=}"
# Saved district settings win over the answers file, the same way the password file wins.
if [ -f "$DISTRICT/settings" ]; then
  _v=$(setting_get sftp_host); [ -n "$_v" ] && CV_SFTP_HOST=$_v
  _v=$(setting_get sftp_port); [ -n "$_v" ] && CV_SFTP_PORT=$_v
  _v=$(setting_get sftp_user); [ -n "$_v" ] && CV_SFTP_USER=$_v
  _v=$(setting_get sftp_folder); [ -n "$_v" ] && CV_SFTP_FOLDER=$_v
  _v=$(setting_get sftp_auth); [ -n "$_v" ] && CV_SFTP_AUTH=$_v
fi
: "${CV_SFTP_PORT:=22}"
TLS=/etc/campusview/tls   # the certificate nginx uses (key: mode 0600, root only)

# value rules (shared by the wizard and the answers file)
RE_PORT='^[0-9]{2,5}$'; RE_YN='^(yes|no)$'; RE_NAME='^[A-Za-z0-9_.@+-]+$'
RE_SECRET='^[^'"'"'"\[:space:]]{8,}$'   # 8+ chars, no spaces, no ' " or \
RE_PATH='^/[A-Za-z0-9._/-]*$'; RE_EMAIL='^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+$'   # nothing that could break the saved file
RE_ACCESS='^(tunnel|http|https)$'; RE_CERTSRC='^(selfsigned|own)$'; RE_HOST='^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$'
RE_IP='^[0-9]{1,3}(\.[0-9]{1,3}){3}$'

ask(){ # ask VAR REGEX "Prompt" ["help line"] [secret]
  local var=$1 re=$2 prompt=$3 help=${4:-} secret=${5:-} ans again
  [ "$CV_NONINTERACTIVE" = 1 ] && return 0
  [ -n "$help" ] && printf '\n  %s\n' "$help"
  while :; do
    if [ -n "$secret" ]; then
      local hint="Enter = make one for me"; [ -n "${!var}" ] && hint="Enter = keep the saved one"
      read -r -s -p "  $prompt [$hint]: " ans; echo
      [ -z "$ans" ] && return 0
      [[ $ans =~ $re ]] || { echo "  Use at least 8 characters, with no spaces, quotes (' or \") or backslashes."; continue; }
      read -r -s -p "  Type it again: " again; echo
      [ "$ans" = "$again" ] || { echo "  Those didn't match. Try again."; continue; }
    else
      read -r -p "  $prompt [${!var}]: " ans; ans=${ans:-${!var}}
      [[ $ans =~ $re ]] || { echo "  \"$ans\" isn't a valid answer here."; continue; }
    fi
    printf -v "$var" '%s' "$ans"; return 0
  done
}

primary_ip(){ local ip; ip=$({ ip -4 route get 1.1.1.1 2>/dev/null || true; } | sed -n 's/.* src \([0-9.]*\).*/\1/p')
  [ -n "$ip" ] || ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -m1 -E "$RE_IP" || true); echo "${ip:-127.0.0.1}"; }
check_own_cert(){ # prints why and fails if CV_TLS_CERT_FILE / CV_TLS_KEY_FILE can't be used together
  local c=$CV_TLS_CERT_FILE k=$CV_TLS_KEY_FILE a b
  [ -f "$c" ] || { echo "certificate file $c not found"; return 1; }
  [ -f "$k" ] || { echo "key file $k not found"; return 1; }
  a=$(openssl x509 -in "$c" -noout -pubkey 2>/dev/null) || { echo "$c is not a PEM certificate"; return 1; }
  b=$(openssl pkey -in "$k" -pubout -passin pass: 2>/dev/null) || { echo "$k is not a PEM private key without a passphrase"; return 1; }
  [ "$a" = "$b" ] || { echo "the key in $k does not match the certificate in $c"; return 1; }
  openssl x509 -in "$c" -noout -checkend 0 >/dev/null || { echo "the certificate in $c has expired"; return 1; }
}
access_desc(){ case $CV_ACCESS in
  tunnel) echo "only from this server (SSH tunnel)";;
  http)   echo "HTTP on port 80, at http://$CV_SERVER_NAME/";;
  https)  echo "HTTPS on port 443, at https://$CV_SERVER_NAME/ ($([ "$CV_TLS_CERT_SOURCE" = own ] && echo "your certificate" || echo "self-signed certificate"))";; esac; }
ask_network(){ # the "How should people reach CampusView?" questions
  case $CV_ACCESS in tunnel) CV_ACCESS_N=1;; http) CV_ACCESS_N=2;; *) CV_ACCESS_N=3;; esac
  printf '\n  How should people reach CampusView?\n    1) Only from this server (SSH tunnel)\n    2) HTTP on port 80\n    3) HTTPS on port 443 (recommended)\n'
  ask CV_ACCESS_N '^[123]$' "Choose 1, 2 or 3"
  case $CV_ACCESS_N in 1) CV_ACCESS=tunnel;; 2) CV_ACCESS=http;; 3) CV_ACCESS=https;; esac
  [ $CV_ACCESS = tunnel ] && return 0
  [ -n "$CV_SERVER_NAME" ] || CV_SERVER_NAME=$(primary_ip)
  ask CV_SERVER_NAME "$RE_HOST" "Server name or IP address" "The address people type in their browser, without http:// (for example 10.0.0.25 or campusview.yourdistrict.org)."
  [ $CV_ACCESS = https ] || return 0
  printf '\n  Which certificate should HTTPS use?\n    1) Make a self-signed one for me (browsers show a warning; fine for testing)\n    2) Use my own certificate and key files\n'
  CV_TLS_N=1; [ "$CV_TLS_CERT_SOURCE" = own ] && CV_TLS_N=2
  ask CV_TLS_N '^[12]$' "Choose 1 or 2"
  [ $CV_TLS_N = 1 ] && { CV_TLS_CERT_SOURCE=selfsigned; return 0; }
  CV_TLS_CERT_SOURCE=own; local why
  while :; do
    ask CV_TLS_CERT_FILE "$RE_PATH" "Certificate file (full path, PEM, with any intermediate certificates)"
    ask CV_TLS_KEY_FILE "$RE_PATH" "Private key file (full path, PEM, no passphrase)"
    why=$(check_own_cert) && return 0; echo "  That pair can't be used: $why."
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
  ask CV_INSTALL_DIR "$RE_PATH" "Install folder" "Where the programs go. It is created for you, owned by that account. Letters, digits, . _ - and / only."
  section "Network ports"
  ask CV_PG_PORT "$RE_PORT" "Database (PostgreSQL) port" "Keep these unless something else on this server already uses them."
  ask CV_SUPERSET_PORT "$RE_PORT" "Superset web page port"
  ask CV_DJANGO_PORT "$RE_PORT" "Django admin page port"
  section "How people reach CampusView"
  if [ $NET_SAVED = yes ]; then
    printf '\n  Saved: %s\n' "$(access_desc)"; CV_NET_CHANGE=no
    ask CV_NET_CHANGE "$RE_YN" "Change how people reach CampusView? (yes/no)"
    [ $CV_NET_CHANGE = yes ] && ask_network
  else ask_network; fi
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
    ask CV_ADMIN_EMAIL "$RE_EMAIL" "Admin email"
    ask CV_ADMIN_PASSWORD "$RE_SECRET" "Admin password" "" secret
  else
    section "Report data accounts, Superset secret key and your admin login"
    printf '\n  Kept from the first install (admin username: %s). They are not asked again.\n' "$CV_ADMIN_USER"
  fi
  section "Nightly extracts"
  if [ -n "$CV_SFTP_HOST" ]; then
    printf '\n  Kept from the first install (SFTP host: %s, user: %s, %s).\n' "$CV_SFTP_HOST" "$CV_SFTP_USER" "$CV_SFTP_AUTH"
  else
    printf '\n  CampusView pulls the CSV extracts from the SFTP server the district runs.\n  This machine does not run an SFTP server. A password is not shown as you type.\n'
    ask CV_SFTP_HOST "$RE_HOST" "SFTP host" "The district SFTP server's name or IP address. Example: files.example.test."
    ask CV_SFTP_PORT "$RE_PORT" "SFTP port"
    ask CV_SFTP_USER "$RE_NAME" "SFTP user"
    ask CV_SFTP_FOLDER "$RE_PATH" "Remote folder" "The folder on that server that holds the CSV files. A full path, such as /exports."
    printf '\n  How does that server sign CampusView in?\n    1) SSH key (this server makes a key and shows the public half)\n    2) Password\n'
    CV_SFTP_AUTH_N=1; [ "$CV_SFTP_AUTH" = password ] && CV_SFTP_AUTH_N=2
    ask CV_SFTP_AUTH_N '^[12]$' "Choose 1 or 2"
    if [ "$CV_SFTP_AUTH_N" = 2 ]; then CV_SFTP_AUTH=password; ask_sftp_password
    else CV_SFTP_AUTH=key; fi
  fi
  section "Starting up"
  ask CV_SYSTEMD "$RE_YN" "Start CampusView automatically when the server boots (yes/no)"
  ask CV_REF "$RE_REF" "Branch or tag this server follows" "dev on the dev server. A release tag such as v1.3.0 on production. No server uses main."
fi

# ---------- validate, fill in generated secrets ----------
chk(){ [[ ${!1} =~ $2 ]] || die "$1 has an invalid value${3:+ ($3)}"; }
[ -z "$CV_SUPERSET_DB_PASSWORD" ] && CV_SUPERSET_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_DJANGO_DB_PASSWORD" ] && CV_DJANGO_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_OWNER_DB_PASSWORD" ] && CV_OWNER_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_READER_DB_PASSWORD" ] && CV_READER_DB_PASSWORD=$(openssl rand -hex 16)
[ -z "$CV_SECRET_KEY" ] && CV_SECRET_KEY=$(openssl rand -base64 42)
[ -z "$CV_ADMIN_PASSWORD" ] && CV_ADMIN_PASSWORD=$(openssl rand -hex 10)
[ -z "$CV_ADMIN_EMAIL" ] && CV_ADMIN_EMAIL="$CV_ADMIN_USER@example.invalid"
chk CV_INSTALL_DIR "$RE_PATH" "use a full path with letters, digits, . _ - and / only"; chk CV_SYSTEMD "$RE_YN"
chk CV_ADMIN_EMAIL "$RE_EMAIL" "use a plain address like name@school.org"
for v in CV_PG_PORT CV_SUPERSET_PORT CV_DJANGO_PORT; do chk $v "$RE_PORT"; done
for v in CV_RUN_USER CV_ADMIN_USER CV_SUPERSET_DB_USER CV_DJANGO_DB_USER; do chk $v "$RE_NAME"; done
for v in CV_SUPERSET_DB_PASSWORD CV_DJANGO_DB_PASSWORD CV_OWNER_DB_PASSWORD CV_READER_DB_PASSWORD CV_SECRET_KEY CV_ADMIN_PASSWORD; do chk $v "$RE_SECRET" "8+ characters, no spaces, quotes or backslashes"; done
valid_ref || die "CV_REF has an invalid value${CV_REF:+ ($CV_REF)}. Use dev, or a release tag. No server uses main."
[ -n "$CV_SFTP_HOST" ] || die "CV_SFTP_HOST is not set"
[ -n "$CV_SFTP_USER" ] || die "CV_SFTP_USER is not set"
[ -n "$CV_SFTP_FOLDER" ] || die "CV_SFTP_FOLDER is not set"
[ -n "$CV_SFTP_AUTH" ] || die "CV_SFTP_AUTH is not set (key or password)"
chk CV_SFTP_HOST "$RE_HOST" "a host name or IPv4 address"
chk CV_SFTP_PORT "$RE_PORT" "a port from 10 to 65535"
[ "$CV_SFTP_PORT" -le 65535 ] || die "CV_SFTP_PORT is not a port"
chk CV_SFTP_USER "$RE_NAME" "letters, digits, and . _ @ + -"
chk CV_SFTP_FOLDER "$RE_PATH" "a full path with letters, digits, . _ - and / only"
chk CV_SFTP_AUTH '^(key|password)$' "key or password"
if [ "$CV_SFTP_AUTH" = password ]; then
  chk CV_SFTP_PASSWORD "$RE_SECRET" "8+ characters, no spaces, quotes or backslashes"
  CV_SFTP_KEY=
else
  CV_SFTP_PASSWORD=
  CV_SFTP_KEY=/etc/campusview/sftp_ed25519
fi
getent passwd "$CV_RUN_USER" >/dev/null || die "Linux user $CV_RUN_USER does not exist"
# network: a fresh install defaults to HTTPS; an older install re-run from an answers file stays tunnel-only until asked
[ -n "$CV_ACCESS" ] || { [ $RERUN = yes ] && CV_ACCESS=tunnel || CV_ACCESS=https; }
chk CV_ACCESS "$RE_ACCESS" "tunnel, http or https"
if [ "$CV_ACCESS" != tunnel ]; then
  [ -n "$CV_SERVER_NAME" ] || CV_SERVER_NAME=$(primary_ip)
  chk CV_SERVER_NAME "$RE_HOST" "a host name or IPv4 address, without http://"
fi
if [ "$CV_ACCESS" = https ]; then chk CV_TLS_CERT_SOURCE "$RE_CERTSRC" "selfsigned or own"
  if [ "$CV_TLS_CERT_SOURCE" = own ]; then
    chk CV_TLS_CERT_FILE "$RE_PATH" "a full path to the certificate file"; chk CV_TLS_KEY_FILE "$RE_PATH" "a full path to the key file"
    if [ -f "$CV_TLS_CERT_FILE" ] || [ "$(cat $TLS/source 2>/dev/null)" != own ]; then
      why=$(check_own_cert) || die "can't use your certificate: $why. Nothing was changed."
    else echo "NOTE: $CV_TLS_CERT_FILE is gone; keeping the copy already in $TLS."; fi
  fi
fi
case $CV_ACCESS in tunnel) URL_SS="http://127.0.0.1:$CV_SUPERSET_PORT"; URL_DJ="http://127.0.0.1:$CV_DJANGO_PORT/admin/";;
  *) URL_SS="$CV_ACCESS://$CV_SERVER_NAME/"; URL_DJ="$CV_ACCESS://$CV_SERVER_NAME/app/";; esac
[ "$CV_SYSTEMD" = yes ] && [ "$HAS_SYSTEMD" = no ] && { echo "systemd is not running here; using start.sh instead."; CV_SYSTEMD=no; }

if [ "$CV_NONINTERACTIVE" != 1 ]; then
  cat <<S

  Ready to install:
    Folder:        $CV_INSTALL_DIR   (apps run as $CV_RUN_USER)
    Following:     $CV_REF
    PostgreSQL:    17, port $CV_PG_PORT
    Reached:       $(access_desc)
    Superset:      $URL_SS
    Django admin:  $URL_DJ
    Admin login:   $CV_ADMIN_USER ($CV_ADMIN_EMAIL)
    Start at boot: $CV_SYSTEMD
    SFTP:          $CV_SFTP_USER@$CV_SFTP_HOST:$CV_SFTP_PORT $CV_SFTP_FOLDER ($CV_SFTP_AUTH)
    Passwords:     saved to $ENVF (only $CV_RUN_USER can read it)
S
  read -r -p "  Go ahead? [Y/n]: " ans; case ${ans:-y} in [Yy]*) ;; *) echo "Nothing was changed."; exit 0;; esac
fi

# ---------- save answers + secrets (0600, owned by the account that runs CampusView) ----------
mkdir -p -m 700 /etc/campusview; chown "$CV_RUN_USER": /etc/campusview
( umask 077; tmp=$(mktemp /etc/campusview/.env.XXXXXX)
  for v in CV_INSTALL_DIR CV_REF CV_RUN_USER CV_PG_PORT CV_SUPERSET_PORT CV_DJANGO_PORT CV_SUPERSET_WORKERS \
           CV_SUPERSET_DB_USER CV_DJANGO_DB_USER CV_ADMIN_USER CV_ADMIN_EMAIL CV_SYSTEMD \
           CV_SUPERSET_DB_PASSWORD CV_DJANGO_DB_PASSWORD CV_OWNER_DB_PASSWORD CV_READER_DB_PASSWORD \
           CV_SECRET_KEY CV_ADMIN_PASSWORD CV_SFTP_PASSWORD CV_SFTP_KEY $NETV; do
    printf "%s='%s'\n" "$v" "${!v}"; done > "$tmp"
  chown "$CV_RUN_USER": "$tmp"; mv "$tmp" "$ENVF" )
set -a; . "$ENVF"; set +a      # the apps read their secrets from these environment variables
write_sftp_settings
install -d -m 700 -o "$CV_RUN_USER" -g "$CV_RUN_USER" /var/lib/campusview/drop
B=$CV_INSTALL_DIR; S=$B/superset; D=$B/django
as_pg(){ (cd /tmp && runuser -u postgres -- "$@"); }

cd /   # the run user may not be able to read the folder the installer was started from (uv reads ./uv.toml)

# ---------- 1. packages ----------
say "1. system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update </dev/null
apt-get install -y build-essential libssl-dev libffi-dev libsasl2-dev libldap2-dev \
  default-libmysqlclient-dev pkg-config libpq-dev curl ca-certificates gnupg openssl git \
  openssh-client sshpass </dev/null
if [ "$CV_SFTP_AUTH" = key ] && [ ! -s "$CV_SFTP_KEY" ]; then
  ssh-keygen -q -t ed25519 -N '' -f "$CV_SFTP_KEY" -C campusview
  chown "$CV_RUN_USER": "$CV_SFTP_KEY" "$CV_SFTP_KEY.pub"
  chmod 600 "$CV_SFTP_KEY"; chmod 644 "$CV_SFTP_KEY.pub"
fi
create_checkout
[ "$CV_ACCESS" = tunnel ] || apt-get install -y nginx </dev/null   # from the distro's own repo

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
  # On failure psql (and the server log) can quote the statement, so keep the server from logging it and
  # hide the password in anything shown.
  local err; err=$(psqlq 2>&1 >/dev/null <<<"SET log_min_error_statement = panic; ALTER ROLE $r WITH LOGIN PASSWORD '$p';") ||
    die "could not set the password for database role $r: ${err//"$p"/<hidden>}"; }
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
DO \$\$ BEGIN   -- earlier installs called the ref schema "mapping"
  IF to_regnamespace('mapping') IS NOT NULL AND to_regnamespace('ref') IS NULL THEN ALTER SCHEMA mapping RENAME TO ref; END IF;
END \$\$;
CREATE SCHEMA IF NOT EXISTS raw AUTHORIZATION campusview_owner;
CREATE SCHEMA IF NOT EXISTS ic AUTHORIZATION campusview_owner;
CREATE SCHEMA IF NOT EXISTS ref AUTHORIZATION campusview_owner;
CREATE SCHEMA IF NOT EXISTS reporting AUTHORIZATION campusview_owner;
ALTER SCHEMA raw OWNER TO campusview_owner;
ALTER SCHEMA ic OWNER TO campusview_owner;
ALTER SCHEMA ref OWNER TO campusview_owner;
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
sync_superset
as_run tee "$S/superset_config.py" >/dev/null <<'C'
# Secrets come from /etc/campusview/campusview.env (loaded by systemd or start.sh).
import os
from urllib.parse import quote_plus
SECRET_KEY = os.environ["CV_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://%s:%s@127.0.0.1:%s/superset_meta" % (
    os.environ["CV_SUPERSET_DB_USER"], quote_plus(os.environ["CV_SUPERSET_DB_PASSWORD"]), os.environ["CV_PG_PORT"])
# Behind nginx (CV_ACCESS http or https): trust its X-Forwarded-* headers for redirects and links.
_cv_access = os.environ.get("CV_ACCESS", "tunnel")
if _cv_access in ("http", "https"):
    ENABLE_PROXY_FIX = True
    PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1}
if _cv_access == "https":
    PREFERRED_URL_SCHEME = "https"
    SESSION_COOKIE_SECURE = True
C
upgrade_superset_db
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
sync_django
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
net = """# --- CampusView network settings (install.sh). CV_ACCESS and CV_SERVER_NAME come from the env file. ---
import socket
_cv_access = os.environ.get('CV_ACCESS', 'tunnel')
_cv_hosts = list(dict.fromkeys(h for h in (os.environ.get('CV_SERVER_NAME', ''), socket.gethostname()) if h))
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', '[::1]'] + _cv_hosts
STATIC_ROOT = BASE_DIR / 'static'
if _cv_access in ('http', 'https'):   # nginx serves Django under /app/
    DEBUG = False                     # debug pages must never reach the network
    FORCE_SCRIPT_NAME = '/app'
    STATIC_URL = '/app/static/'
    CSRF_TRUSTED_ORIGINS = [f'{_cv_access}://{h}' for h in _cv_hosts]
if _cv_access == 'https':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
# --- end CampusView network settings ---
"""
s = re.sub(r"\n# --- CampusView network settings .*?# --- end CampusView network settings ---\n", "", s, flags=re.S)
s = s.rstrip("\n") + "\n\n" + net
if "\nimport os\n" not in s:
    s = s.replace("from pathlib import Path\n", "import os\nfrom pathlib import Path\n", 1)
open(p, "w").write(s)
PY
as_run chmod 600 "$D/campusview_base/settings.py"
(cd "$D" && as_run venv/bin/python manage.py collectstatic --noinput -v0)   # nginx serves these at /app/static/
migrate_django
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
U=$(stat -c %U "$0")                                      # the install's account owns this script and the secrets
if [ "$(id -un)" != "$U" ]; then
  if [ "$(id -u)" = 0 ]; then exec runuser -u "$U" -- "$0" "$@"
  elif command -v sudo >/dev/null; then exec sudo -u "$U" "$0" "$@"
  else echo "Run this as $U or as root (sudo is not installed)." >&2; exit 1; fi
fi
export HOME=$(getent passwd "$U" | cut -d: -f6)          # runuser keeps root's HOME; Superset writes under ~
set -a; . /etc/campusview/campusview.env; set +a
B=$CV_INSTALL_DIR; export SUPERSET_CONFIG_PATH=$B/superset/superset_config.py
cd "$B/superset"                                          # gunicorn fails if it cannot read the starting folder
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
U=$(stat -c %U "$0")                                      # the install's account owns this script and the secrets
if [ "$(id -un)" != "$U" ]; then
  if [ "$(id -u)" = 0 ]; then exec runuser -u "$U" -- "$0" "$@"
  elif command -v sudo >/dev/null; then exec sudo -u "$U" "$0" "$@"
  else echo "Run this as $U or as root (sudo is not installed)." >&2; exit 1; fi
fi
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
UnsetEnvironment=CV_SFTP_PASSWORD
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
UnsetEnvironment=CV_SFTP_PASSWORD
ExecStart=$D/venv/bin/gunicorn -b 127.0.0.1:$CV_DJANGO_PORT campusview_base.wsgi
Restart=on-failure
[Install]
WantedBy=multi-user.target
C
  cat > /etc/systemd/system/cv-nightly.service <<C
[Unit]
Description=CampusView nightly extract load
After=network-online.target postgresql.service
Wants=network-online.target
[Service]
Type=oneshot
User=$CV_RUN_USER
WorkingDirectory=$B
ExecStart=$B/nightly.sh
TimeoutStartSec=infinity
C
  cat > /etc/systemd/system/cv-nightly.timer <<C
[Unit]
Description=CampusView nightly extract load
[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
[Install]
WantedBy=timers.target
C
  systemctl daemon-reload
  systemctl enable cv-superset cv-django
  systemctl enable --now cv-nightly.timer
  restart_apps
else
  say "8. starting with start.sh"
  restart_apps
fi

# ---------- 9. network access (nginx is the only thing on the network) ----------
put(){ # put FILE MODE < content: replace FILE only when the content differs (re-runs stay byte-identical)
  local t; t=$(mktemp "$1.XXXXXX"); cat > "$t"
  if cmp -s "$t" "$1"; then rm -f "$t"; return 1; fi; chmod "$2" "$t"; mv "$t" "$1"; }
nginx_up(){ nginx -t -q || die "nginx rejected its configuration (see above)"
  if [ "$HAS_SYSTEMD" = yes ]; then systemctl enable -q nginx; systemctl reload-or-restart nginx
  elif [ -s /run/nginx.pid ] && kill -0 "$(cat /run/nginx.pid)" 2>/dev/null; then nginx -s reload; else nginx; fi; }
SITE=/etc/nginx/sites-available/campusview
if [ "$CV_ACCESS" = tunnel ]; then
  say "9. network access: SSH tunnel only (no web server)"
  if [ -e "$SITE" ] || [ -L /etc/nginx/sites-enabled/campusview ]; then
    rm -f /etc/nginx/sites-enabled/campusview "$SITE"; echo "  removed the CampusView nginx site"
    if [ -z "$(ls -A /etc/nginx/sites-enabled 2>/dev/null)" ]; then
      if [ "$HAS_SYSTEMD" = yes ]; then systemctl disable -q --now nginx; else nginx -s stop 2>/dev/null || true; fi
      echo "  nginx had no other sites, so it is stopped and won't start at boot"
    else nginx_up; fi
  fi
else
  say "9. network access: nginx, $(access_desc)"
  L80=; L443=; if [ -f /proc/net/if_inet6 ]; then   # listen on IPv6 too, when the server has it
    L80='    listen [::]:80 default_server;'$'\n'; L443='    listen [::]:443 ssl default_server;'$'\n'; fi
  if [ "$CV_ACCESS" = https ]; then
    install -d -m 700 -o root -g root "$TLS"
    if [ "$CV_TLS_CERT_SOURCE" = own ]; then
      if [ -f "$CV_TLS_CERT_FILE" ]; then
        put "$TLS/campusview.crt" 644 < "$CV_TLS_CERT_FILE" || true; put "$TLS/campusview.key" 600 < "$CV_TLS_KEY_FILE" || true
      fi
      echo own | put "$TLS/source" 644 || true
    else
      want="selfsigned $CV_SERVER_NAME $(hostname)"
      if [ "$(cat $TLS/source 2>/dev/null)" != "$want" ] || ! openssl x509 -in $TLS/campusview.crt -noout -checkend 2592000 >/dev/null 2>&1; then
        san="DNS:$(hostname)"; [[ $CV_SERVER_NAME =~ $RE_IP ]] && san="IP:$CV_SERVER_NAME,$san"
        [[ $CV_SERVER_NAME =~ $RE_IP ]] || [ "$CV_SERVER_NAME" = "$(hostname)" ] || san="DNS:$CV_SERVER_NAME,$san"
        ( umask 077; openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 3650 -subj "/CN=$CV_SERVER_NAME" \
            -addext "subjectAltName=$san" -keyout $TLS/campusview.key.new -out $TLS/campusview.crt.new 2>/dev/null )
        chmod 644 $TLS/campusview.crt.new; mv $TLS/campusview.key.new $TLS/campusview.key; mv $TLS/campusview.crt.new $TLS/campusview.crt
        echo "$want" | put "$TLS/source" 644 || true; echo "  made a self-signed certificate for $san"
      fi
    fi
  fi
  { echo "# CampusView, written by install.sh (re-running it rewrites this file)."
    echo "# Superset at /, Django at /app/. The apps and PostgreSQL listen on 127.0.0.1 only."
    if [ "$CV_ACCESS" = https ]; then
      printf 'server {\n    listen 80 default_server;\n%s    server_name _;\n    return 301 https://$host$request_uri;\n}\n' "$L80"
      printf 'server {\n    listen 443 ssl default_server;\n%s' "$L443"
      printf '    ssl_certificate     %s/campusview.crt;\n    ssl_certificate_key %s/campusview.key;\n    ssl_protocols TLSv1.2 TLSv1.3;\n' $TLS $TLS
    else printf 'server {\n    listen 80 default_server;\n%s' "$L80"; fi
    sed -e "s#@D@#$D#g" -e "s#@SP@#$CV_SUPERSET_PORT#g" -e "s#@DP@#$CV_DJANGO_PORT#g" <<'NGX'
    server_name _;
    client_max_body_size 100m;
    proxy_http_version 1.1;
    proxy_read_timeout 300s;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    location = /app { return 301 /app/; }
    location = /app/ { return 302 /app/admin/; }
    location /app/static/ { alias @D@/static/; }
    location /app/ { proxy_pass http://127.0.0.1:@DP@/; }
    location / { proxy_pass http://127.0.0.1:@SP@; }
}
NGX
  } | put "$SITE" 644 || true
  ln -sfn "$SITE" /etc/nginx/sites-enabled/campusview; rm -f /etc/nginx/sites-enabled/default
  nginx_up
  runuser -u www-data -- test -r "$D/static/admin/css/base.css" 2>/dev/null ||
    echo "  NOTE: nginx (www-data) can't read $D/static, so the Django admin pages will have no styling."
fi

# ---------- 10. verify ----------
say "10. checking everything answers"
code(){ curl -s -o /dev/null -w '%{http_code}' "$1" || true; }
wait200(){ for i in $(seq 60); do [ "$(code "$1")" = 200 ] && return 0; sleep 2; done; return 1; }
ok=1
for u in "http://127.0.0.1:$CV_SUPERSET_PORT/health" "http://127.0.0.1:$CV_SUPERSET_PORT/login/" "http://127.0.0.1:$CV_DJANGO_PORT/admin/login/"; do
  wait200 "$u" || ok=0; echo "  $(code "$u")  $u"; done
if [ "$CV_ACCESS" != tunnel ]; then   # through nginx, the way a browser comes in (curl -k: the certificate may be self-signed)
  pcode(){ curl -sk --noproxy '*' --resolve "$CV_SERVER_NAME:80:127.0.0.1" --resolve "$CV_SERVER_NAME:443:127.0.0.1" -o /dev/null -w '%{http_code}' "$1" || true; }
  for u in "${URL_SS}health" "${URL_SS}login/" "${URL_SS}app/admin/login/"; do
    for i in $(seq 30); do [ "$(pcode "$u")" = 200 ] && break; sleep 2; done; echo "  $(pcode "$u")  $u"; [ "$(pcode "$u")" = 200 ] || ok=0; done
  if [ "$CV_ACCESS" = https ]; then u="http://$CV_SERVER_NAME/login/"; echo "  $(pcode "$u")  $u (should send you to https)"; [ "$(pcode "$u")" = 301 ] || ok=0; fi
fi
dbs=$(psqlq -c "SELECT string_agg(datname, ' ' ORDER BY datname) FROM pg_database WHERE datname IN ('superset_meta','django_app','campusview_data')")
echo "  databases: $dbs"; [ "$(wc -w <<<"$dbs")" = 3 ] || ok=0
if [ $ok = 1 ]; then
  mark_running
  if [ "$CV_ACCESS" = tunnel ]; then cat <<E

INSTALL OK
  Superset:      http://127.0.0.1:$CV_SUPERSET_PORT   (log in as $CV_ADMIN_USER)
  Django admin:  http://127.0.0.1:$CV_DJANGO_PORT/admin/
  Passwords:     sudo cat $ENVF
  Everything listens on 127.0.0.1 only.
  From your laptop: ssh -L $CV_SUPERSET_PORT:127.0.0.1:$CV_SUPERSET_PORT -L $CV_DJANGO_PORT:127.0.0.1:$CV_DJANGO_PORT you@this-server
E
  else cat <<E

INSTALL OK
  Open these in your browser:
    Superset:      $URL_SS   (log in as $CV_ADMIN_USER)
    Django admin:  $URL_DJ   (takes you to the admin sign-in page)
  Passwords:     sudo cat $ENVF
  Only nginx (port $([ "$CV_ACCESS" = https ] && echo "443, and 80 to send you to https" || echo 80)) is reachable from the network.
  Superset, Django and PostgreSQL listen on 127.0.0.1 only.
E
    if [ "$CV_ACCESS" = http ]; then cat <<E
  Plain HTTP: passwords cross the network unencrypted. Use it only for testing with fake data.
E
    elif [ "$CV_TLS_CERT_SOURCE" = selfsigned ]; then cat <<E
  The certificate is self-signed, so your browser will warn that the connection isn't private
  or the certificate isn't trusted. That's expected the first time: choose Advanced, then
  Continue (or Proceed / Accept the risk). To be sure it's this server, compare the fingerprint:
    $(openssl x509 -in $TLS/campusview.crt -noout -fingerprint -sha256 | cut -d= -f2)
E
    fi
  fi
  if [ "$CV_SYSTEMD" = yes ]; then cat <<E

Nightly load
  The timer cv-nightly.timer runs at 02:00 in this server's time zone. Set that time zone to the district's.
  A missed night runs after the server is back.
  Next run:  systemctl list-timers cv-nightly.timer
  Last run:  journalctl -u cv-nightly.service
  install.sh --update does not install this timer. A full install.sh run does.
E
  else cat <<E

Nightly load
  This server has no systemd, so there is no timer. Run this once a night:
    $([ "$CV_RUN_USER" = root ] && echo "$B/nightly.sh" || echo "runuser -u $CV_RUN_USER -- $B/nightly.sh")
  install.sh --update does not install a timer either.
E
  fi
  if [ "$CV_SFTP_AUTH" = key ]; then
    echo "  SFTP public key (give this to the SFTP admin):"
    cat "$CV_SFTP_KEY.pub"
  fi
  cat <<E

Connect with DBeaver (or another database tool)
  Host 127.0.0.1   Port $CV_PG_PORT   Database campusview_data
  campusview_reader  safe browsing: sees the reporting views only (empty until Step 1)
  campusview_owner   full access to the raw, ic, ref and reporting schemas; use with care
  Passwords: CV_READER_DB_PASSWORD / CV_OWNER_DB_PASSWORD in $ENVF
  The database only listens on this server, so for either account turn on DBeaver's
  SSH tunnel to this server (or run: ssh -L $CV_PG_PORT:127.0.0.1:$CV_PG_PORT you@this-server).
  Superset's data connection should use campusview_reader.
  django_app and superset_meta belong to the apps. Don't edit them by hand.
E
else echo "INSTALL FINISHED WITH ERRORS (see the lines above)"; exit 1; fi
