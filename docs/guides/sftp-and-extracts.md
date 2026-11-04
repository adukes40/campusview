# SFTP and extracts

The loader is in this repo. SFTP is not built yet. The loader also builds the typed copy, and that copy keeps the Infinite Campus names. The rules and meanings stay in [DATA_CONTRACT.md](../DATA_CONTRACT.md). The Infinite Campus headers the loader accepts are in `loader/contract.py`. This guide is the operator's version.

## The drop folder

**Not built yet.** On the nightly timer, CampusView pulls the extracts from the SFTP server the district runs into a local drop folder, then validates and loads them, then removes drop files older than 7 nights. CampusView has no built-in SFTP server and no upload account. The files stay on the server and are never committed to either git repo. To confirm: where the remote host, user, folder, and client key are kept, and whether the SFTP server's host key is pinned.

## What a nightly drop contains

The file names in `loader/contract.py`, the rule that this is a full copy of everything on or after the district cutoff date, and which files must contain rows. What a header-only incident file means (no incidents, and the previous incidents are replaced).

## Code-mapping files

The ten code-mapping files live in the district directory, not in the SFTP drop. The rules are in [Code-mapping files](../DATA_CONTRACT.md#code-mapping-files). A bad map file says the problem is in the district config folder's map files. A missing district folder says the problem is the district config folder. The all-false referral warning is not built yet.

Someone with write access to the district repo edits a file when the district adds an attendance code. Commit it there, then run the loader with that directory.

## Infinite Campus

How to schedule the extracts this district confirmed in the TO CONFIRM list, that the loader keeps every column the extract sends, and what the typed copy does after the loader runs. Field-level notes stay in the data contract so this guide does not drift from it.

## Run the loader

The loader reads one folder of Infinite Campus CSV files and the district directory of code-mapping files. It loads the extracts into the `raw` schema, rebuilds the typed copy in schema `ic`, and replaces the ten `ref` tables in the same step. A bad value becomes NULL in `ic` and the report warns. A row that fails a cross-row check is kept and still counts. An empty `school.csv` or `calendar.csv` fails the load. Map-file rules are in [Code-mapping files](../DATA_CONTRACT.md#code-mapping-files).

The installer does not install or run the loader. From a checkout of this repository, load the password file into the environment. Do not put the password on the command line. The command below uses the Python 3.12 the installer already placed. It does not download Python, and it does not install the test tools. The first run installs the loader's database library into that checkout, so it needs internet access. If you chose another install folder, use it in place of `/opt/campusview`.

```
set -a
. /etc/campusview/campusview.env
set +a
cd /path/to/checkout
UV_PYTHON_INSTALL_DIR=/opt/campusview/.uv/python \
  /opt/campusview/.uv/bin/uv run --no-dev --no-python-downloads --python 3.12 \
  python -m loader /path/to/folder /opt/campusview-district
```

A good folder has every CSV file named in `loader/contract.py`, 24 files today, with the names spelled exactly. A CSV file that is not in that list fails the load, including a code-mapping file dropped in that folder. A listed file that is missing fails the load. Files that are not CSV, and folders, are ignored. A file fails when it is not UTF-8, has no header row, or has a blank, repeated, unknown, or missing header. The district directory must hold all ten code-mapping files.

You should see `Load passed.`, one line per extract file with its row count, and one line per map file. The same text is stored in `ops.load_batch`, in the `report` column. `outcome` is `pass` or `fail`. `fault` is `extract` when the files are wrong, and `server` when the machine or the database is the problem. `fault` is empty on a pass. The table also has `batch_id`, `started_at`, and `finished_at`. The loader creates `ops` and the table on its first run. Read the table as `campusview_owner`; `campusview_reader` cannot see it.

The exit code is 0 when the load passed and the report was saved, 1 otherwise, and 2 when the command did not have both paths. When `CV_OWNER_DB_PASSWORD` is not set, or the database cannot be reached, the loader prints the report and saves nothing to `ops.load_batch`.

A failed load writes nothing to `raw`, `ic`, or `ref`. The previous rows stay. On a failure the report lists only the files that failed. `school.csv` or `calendar.csv` with zero data rows fails the load and leaves the previous data. Any other header-only extract file warns and still loads, and that table is replaced with zero rows. See [DATA_CONTRACT.md](../DATA_CONTRACT.md). Running the same extract folder and the same district directory again leaves the same rows.

Every value in `raw` is stored as text, so a leading zero stays. Ids and codes stay text in `ic` as well. A blank cell is stored as NULL, including a quoted empty cell. Postgres reads the CSV, so a quoted comma or a quote inside a value is kept, and the line endings can be LF or CRLF.

A calendar with no Day rows is a warning when an enrollment's end date, or its start date when the end date is empty, is on or after the extract cutoff date, 2025-07-01. The dates are compared as text, so they must start with `YYYY-MM-DD`. Only numeric calendar ids are checked. An old enrollment with a blank end date is left out. The load still passes. The warning lists those calendar ids in numeric order. Day rows may repeat a date for one calendar. Older calendars do that when one date sits on more than one schedule structure. The loader allows the repeat.

If a load is already running, the new one stops at once, without waiting, and names the server as the fault.

## Add a column or a table

File names and header names stay fixed until you change the list in `loader/contract.py`.

1. Add the new header, or the new file and its headers, in `loader/contract.py`. Match the spelling in the extract exactly.
2. Add that same column or file to the extract.
3. Run the loader. It adds a missing text column on the raw table. It does not drop a column that is already there.

Until the list includes the new header, the loader fails that file and the report names the header. A renamed header fails the same way. The report shows an unknown column and a missing column.

## When a load fails

Read the loader output, or `ops.load_batch`. A failed load names only the files that failed, with the reason. When PostgreSQL rejects a row, it gives the line number. You do not see the cell value. The first line of a map-file failure says the district config folder's map files. A missing district folder says the district config folder. `fault` is still `extract` for a bad map file and `server` when the district folder itself is missing. `server` also means this machine, the database, or a load that is already running. The previous rows stay in place.

## Writing a mapping for another student information system

**Not decided.** CampusView keeps the Infinite Campus names (2026-11-03 "The typed layer keeps the Infinite Campus names" in [../DECISIONS.md](../DECISIONS.md)), so there is no vendor-neutral layout for another system to produce. The earlier outline follows. It said to produce the standard files, with these keys, and not to connect CampusView to that system. v1 does not ship that mapping. The steps here will be: list the source files, map each CampusView column to a source field, roll daily attendance up to one row per student per date, keep the other columns, and run the same loader. Promote a real second mapping out of the parking lot before building it.

## History

The district cutoff date, set in the district repo, and why each extract must include everything dated on or after it: a good load replaces the warehouse with the drop, and the warehouse is not purged by school year. How the nightly run cleans old extract files out of the drop: it keeps 7 nights of drop files, then deletes older ones (Austin, relayed by CampusView Engineer, 2026-11-03 7:33 PM ET). Whether 7 is a fixed product value or a district setting is to confirm.
