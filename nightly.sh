#!/usr/bin/env bash
# Pull this night's CSV extracts, load them, then delete dated drop folders older than 7 nights.
# 7 is fixed. A failed fetch or a failed load deletes nothing.
set -euo pipefail

ENVF=/etc/campusview/campusview.env
DISTRICT=/opt/campusview-district
DROP=/var/lib/campusview/drop
KNOWN=/etc/campusview/sftp_known_hosts

fail(){ echo "$1" >&2; exit 1; }
file_value(){ local v; v=$(grep -m1 "^$2=" "$1") || return 1; v=${v#*=}; v=${v#\'}; printf '%s' "${v%\'}"; }
stop(){ [ -n "${partial:-}" ] && rm -rf -- "$partial"; fail "$1"; }

unset CV_SFTP_PASSWORD SSHPASS || true
for key in sftp_host sftp_port sftp_user sftp_folder sftp_auth; do
  val=$(file_value "$DISTRICT/settings" "$key") || fail "The district settings have no $key."
  printf -v "$key" '%s' "$val"
done
install_dir=$(file_value "$ENVF" CV_INSTALL_DIR) || fail "CV_INSTALL_DIR is not set."
owner_pw=$(file_value "$ENVF" CV_OWNER_DB_PASSWORD) || fail "CV_OWNER_DB_PASSWORD is not set."
pg_port=$(file_value "$ENVF" CV_PG_PORT || true)

mkdir -p -- "$DROP"
partial=$(mktemp -d "$DROP/.partial.XXXXXX")
opts=(
  -o StrictHostKeyChecking=accept-new
  -o UserKnownHostsFile="$KNOWN"
  -o GlobalKnownHostsFile=/dev/null
  -o Port="$sftp_port"
  -o ConnectTimeout=20
  -o LogLevel=ERROR
)
remote="${sftp_user}@${sftp_host}:${sftp_folder}/*.csv"
echo "Fetching extracts from ${sftp_user}@${sftp_host}:${sftp_port}${sftp_folder}"
pinned=no
[ -s "$KNOWN" ] || pinned=yes
if [ "$sftp_auth" = password ]; then
  sftp_pw=$(file_value "$ENVF" CV_SFTP_PASSWORD) || stop "CV_SFTP_PASSWORD is not set."
  sshpass -d 3 scp "${opts[@]}" \
    -o PreferredAuthentications=password -o PubkeyAuthentication=no \
    -o KbdInteractiveAuthentication=no -o NumberOfPasswordPrompts=1 \
    "$remote" "$partial/" 3<<<"$sftp_pw"
else
  sftp_key=$(file_value "$ENVF" CV_SFTP_KEY) || stop "CV_SFTP_KEY is not set."
  scp "${opts[@]}" \
    -o BatchMode=yes -o PreferredAuthentications=publickey \
    -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no \
    -o IdentitiesOnly=yes -o IdentityFile="$sftp_key" \
    "$remote" "$partial/"
fi || stop "Could not fetch the extracts from the SFTP server. Nothing was loaded, and no drop folders were removed."
compgen -G "$partial/*.csv" >/dev/null \
  || stop "The SFTP folder had no CSV files. Nothing was loaded, and no drop folders were removed."
[ "$pinned" = no ] || echo "Pinned the SFTP host key. Check this fingerprint with the SFTP admin:"
ssh-keygen -lf "$KNOWN"

stamp=$(date +%Y-%m-%d)
dest="$DROP/$stamp"
[ -e "$dest" ] && dest="$DROP/${stamp}-$(date +%H%M%S)"
mv -- "$partial" "$dest"
partial=

echo "Loading $dest"
set +e
cd "$install_dir"
CV_OWNER_DB_PASSWORD="$owner_pw" CV_PG_PORT="${pg_port:-5432}" \
  UV_PYTHON_INSTALL_DIR=$install_dir/.uv/python \
  "$install_dir/.uv/bin/uv" run --no-dev --no-python-downloads --python 3.12 \
  python -m loader "$dest" "$DISTRICT"
loader_status=$?
set -e
[ "$loader_status" = 0 ] || exit "$loader_status"

limit=$(date -d "7 days ago" +%Y-%m-%d)
for dir in "$DROP"/*/; do
  name=$(basename "$dir")
  day=${name:0:10}
  [[ $day =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || continue
  [[ $name == "$day" || $name == "$day"-* ]] || continue
  [[ $day < $limit ]] && rm -rf -- "$dir"
done
exit 0
