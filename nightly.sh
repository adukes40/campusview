#!/usr/bin/env bash
# Pull this night's CSV extracts from the district SFTP server, load them, then
# delete local drop folders older than 7 nights. 7 is fixed. A failed fetch
# loads nothing and deletes nothing.
set -euo pipefail

ENVF=/etc/campusview/campusview.env
DISTRICT=/opt/campusview-district
DROP=/var/lib/campusview/drop
KNOWN=/etc/campusview/sftp_known_hosts
KEEP_SECONDS=$((7 * 24 * 3600))

fail(){ echo "$1" >&2; exit 1; }
file_value(){
  local line val
  line=$(grep -m1 -E "^${2}=" "$1" || true)
  [ -n "$line" ] || return 1
  val=${line#*=}
  case $val in \'*\') val=${val#\'}; val=${val%\'} ;; esac
  val=${val%$'\r'}
  printf '%s' "$val"
}

[ -f "$ENVF" ] || fail "No saved settings in $ENVF."
[ -f "$DISTRICT/settings" ] || fail "The district config folder has no settings file."
unset CV_SFTP_PASSWORD SSHPASS || true

sftp_host=$(file_value "$DISTRICT/settings" sftp_host) || fail "The district settings have no sftp_host."
sftp_port=$(file_value "$DISTRICT/settings" sftp_port) || fail "The district settings have no sftp_port."
sftp_user=$(file_value "$DISTRICT/settings" sftp_user) || fail "The district settings have no sftp_user."
sftp_folder=$(file_value "$DISTRICT/settings" sftp_folder) || fail "The district settings have no sftp_folder."
sftp_auth=$(file_value "$DISTRICT/settings" sftp_auth) || fail "The district settings have no sftp_auth."
[ -n "$sftp_host" ] && [ -n "$sftp_port" ] && [ -n "$sftp_user" ] && [ -n "$sftp_folder" ] && [ -n "$sftp_auth" ] || fail "The district SFTP settings are incomplete."
install_dir=$(file_value "$ENVF" CV_INSTALL_DIR) || fail "CV_INSTALL_DIR is not set."
owner_pw=$(file_value "$ENVF" CV_OWNER_DB_PASSWORD) || fail "CV_OWNER_DB_PASSWORD is not set."
pg_port=$(file_value "$ENVF" CV_PG_PORT || true)

sftp_pw=
sftp_key=
if [ "$sftp_auth" = password ]; then
  sftp_pw=$(file_value "$ENVF" CV_SFTP_PASSWORD) || fail "CV_SFTP_PASSWORD is not set."
  [ -n "$sftp_pw" ] || fail "CV_SFTP_PASSWORD is not set."
  command -v sshpass >/dev/null || fail "sshpass is not installed."
elif [ "$sftp_auth" = key ]; then
  sftp_key=$(file_value "$ENVF" CV_SFTP_KEY) || fail "CV_SFTP_KEY is not set."
  [ -f "$sftp_key" ] || fail "The SFTP key is not on this machine."
else
  fail "The district settings have an unknown SFTP sign-in."
fi
command -v scp >/dev/null || fail "scp is not installed."
[ -x "$install_dir/.uv/bin/uv" ] || fail "The CampusView checkout has no uv."

mkdir -p -- "$DROP"
partial=$(mktemp -d "$DROP/.partial.XXXXXX")
cleanup_partial(){ [ -n "${partial:-}" ] && [ -d "$partial" ] && rm -rf -- "$partial"; partial=; }
trap cleanup_partial EXIT

fetch_extracts(){
  local status=0
  local -a opts
  # sftp -b never prompts, so sshpass cannot answer it. scp does, and the password stays off the command line.
  opts=(
    -o StrictHostKeyChecking=accept-new
    -o UserKnownHostsFile="$KNOWN"
    -o GlobalKnownHostsFile=/dev/null
    -o Port="$sftp_port"
    -o ConnectTimeout=20
    -o LogLevel=ERROR
  )
  if [ "$sftp_auth" = password ]; then
    sshpass -d 3 scp "${opts[@]}" \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o KbdInteractiveAuthentication=no \
      -o NumberOfPasswordPrompts=1 \
      "${sftp_user}@${sftp_host}:${sftp_folder}/*.csv" "$partial/" 3<<<"$sftp_pw" || status=$?
  else
    scp "${opts[@]}" \
      -o BatchMode=yes \
      -o PreferredAuthentications=publickey \
      -o PasswordAuthentication=no \
      -o KbdInteractiveAuthentication=no \
      -o IdentitiesOnly=yes \
      -o IdentityFile="$sftp_key" \
      "${sftp_user}@${sftp_host}:${sftp_folder}/*.csv" "$partial/" || status=$?
  fi
  return "$status"
}

echo "Fetching extracts from ${sftp_user}@${sftp_host}:${sftp_port}${sftp_folder}"
pinned=no
[ -s "$KNOWN" ] || pinned=yes
if ! fetch_extracts; then
  cleanup_partial
  trap - EXIT
  fail "Could not fetch the extracts from the SFTP server. Nothing was loaded, and no drop folders were removed."
fi
if ! compgen -G "$partial/*.csv" >/dev/null; then
  cleanup_partial
  trap - EXIT
  fail "The SFTP folder had no CSV files. Nothing was loaded, and no drop folders were removed."
fi
if [ "$pinned" = yes ]; then
  echo "Pinned the SFTP host key. Check this fingerprint with the SFTP admin:"
fi
ssh-keygen -lf "$KNOWN"

stamp=$(date +%Y-%m-%d)
dest="$DROP/$stamp"
[ -e "$dest" ] && dest="$DROP/${stamp}-$(date +%H%M%S)"
mv -- "$partial" "$dest"
partial=
trap - EXIT

echo "Loading $dest"
set +e
CV_OWNER_DB_PASSWORD="$owner_pw" CV_PG_PORT="${pg_port:-5432}" \
  UV_PYTHON_INSTALL_DIR=$install_dir/.uv/python \
  "$install_dir/.uv/bin/uv" run --no-dev --no-python-downloads --python 3.12 \
  python -m loader "$dest" "$DISTRICT"
loader_status=$?
set -e

now=$(date +%s)
limit=$((now - KEEP_SECONDS))
shopt -s nullglob
for dir in "$DROP"/*/; do
  modified=$(stat -c %Y "$dir")
  [ "$modified" -lt "$limit" ] && rm -rf -- "$dir"
done

exit "$loader_status"
