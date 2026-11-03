# SFTP and extracts

The loader is in this repo. SFTP and the typed copy of the loaded tables are not built yet. The typed copy keeps the Infinite Campus names. The rules and meanings stay in [DATA_CONTRACT.md](../DATA_CONTRACT.md). The Infinite Campus headers the loader accepts are in `loader/contract.py`. This guide is the operator's version.

## The drop folder

Where files land, which account can upload, and the fact that this account cannot read the database. That uploaded files stay on the server and are never committed to either git repo.

## What a nightly drop contains

The file names in `loader/contract.py`, the rule that this is a full snapshot of the years to keep, and which files must contain rows. What a header-only incident file means (no incidents, and the previous incidents are replaced).

## Code-mapping files

Where they live (the district repo, not the SFTP drop). Who edits them when the district adds an attendance code. That a code in the extract with no map row is a warning on the load report, and loading continues.

## Infinite Campus

How to schedule the extracts this district confirmed in the TO CONFIRM list, that the loader keeps every column the extract sends, and what the typed copy does after the loader runs. Field-level notes stay in the data contract so this guide does not drift from it.

## Run the loader

The loader reads one folder of Infinite Campus CSV files and loads them into the `raw` schema. SFTP pickup and the typed copy in schema `ic` come later. The typed copy will report bad values (stored as NULL in `ic`), bad keys, unknown codes, and cross-row problems as warnings, and keep loading. A row that fails a cross-row check is kept as it is and still counts in the metrics. Planned failures, on top of today's: an empty `school.csv` or `calendar.csv` (zero data rows), and a bad district code-mapping file (a header problem or a bad code). See [DATA_CONTRACT.md](../DATA_CONTRACT.md).

The installer does not install or run the loader. From a checkout of this repository, load the password file into the environment. Do not put the password on the command line. The command below uses the Python 3.12 the installer already placed. It does not download Python, and it does not install the test tools. The first run installs the loader's database library into that checkout, so it needs internet access. If you chose another install folder, use it in place of `/opt/campusview`.

```
set -a
. /etc/campusview/campusview.env
set +a
cd /path/to/checkout
UV_PYTHON_INSTALL_DIR=/opt/campusview/.uv/python \
  /opt/campusview/.uv/bin/uv run --no-dev --no-python-downloads --python 3.12 \
  python -m loader /path/to/folder
```

A good folder has every CSV file named in `loader/contract.py`, 24 files today, with the names spelled exactly. A CSV file that is not in that list fails the load. A listed file that is missing fails the load. Files that are not CSV, and folders, are ignored. A file fails when it is not UTF-8, has no header row, or has a blank, repeated, unknown, or missing header.

You should see `Load passed.` and one line per file with its row count. The same text is stored in `ops.load_batch`, in the `report` column. `outcome` is `pass` or `fail`. `fault` is `extract` when the files are wrong, and `server` when the machine or the database is the problem. `fault` is empty on a pass. The table also has `batch_id`, `started_at`, and `finished_at`. The loader creates `ops` and the table on its first run. Read the table as `campusview_owner`; `campusview_reader` cannot see it.

The exit code is 0 when the load passed and the report was saved, 1 otherwise, and 2 when the folder is missing from the command. When `CV_OWNER_DB_PASSWORD` is not set, or the database cannot be reached, the loader prints the report and saves nothing to `ops.load_batch`.

A failed load writes nothing to `raw`. The previous rows stay. On a failure the report lists only the files that failed. A file that has only a header row is a pass, and it clears that table. That changes with the typed copy: an empty `school.csv` or `calendar.csv` will fail the load, and any other empty file will be a warning on the load report. See [DATA_CONTRACT.md](../DATA_CONTRACT.md). Running the same folder again leaves the same rows.

Every value is stored as text, so a leading zero stays. A blank cell is stored as NULL, including a quoted empty cell. Postgres reads the CSV, so a quoted comma or a quote inside a value is kept, and the line endings can be LF or CRLF.

A calendar with no Day rows is a warning when an enrollment's end date, or its start date when the end date is empty, is on or after the extract cutoff date, 2025-07-01. The dates are compared as text, so they must start with `YYYY-MM-DD`. Only numeric calendar ids are checked. An old enrollment with a blank end date is left out. The load still passes. The warning lists those calendar ids in numeric order. Day rows may repeat a date for one calendar. Older calendars do that when one date sits on more than one schedule structure. The loader allows the repeat.

If a load is already running, the new one stops at once, without waiting, and names the server as the fault.

## Add a column or a table

File names and header names stay fixed until you change the list in `loader/contract.py`.

1. Add the new header, or the new file and its headers, in `loader/contract.py`. Match the spelling in the extract exactly.
2. Add that same column or file to the extract.
3. Run the loader. It adds a missing text column on the raw table. It does not drop a column that is already there.

Until the list includes the new header, the loader fails that file and the report names the header. A renamed header fails the same way. The report shows an unknown column and a missing column.

## When a load fails

Read the loader output, or `ops.load_batch`. A failed load names only the files that failed, with the reason. When PostgreSQL rejects a row, it gives the line number. You do not see the cell value. Use `fault` to decide where to look. `extract` means fix the files. `server` means check this machine, the database, or whether a load is already running. The previous rows stay in place.

## Writing a mapping for another student information system

**Not decided.** CampusView keeps the Infinite Campus names (2026-11-03 "The typed layer keeps the Infinite Campus names" in [../DECISIONS.md](../DECISIONS.md)), so there is no vendor-neutral layout for another system to produce. The earlier outline follows. It said to produce the standard files, with these keys, and not to connect CampusView to that system. v1 does not ship that mapping. The steps here will be: list the source files, map each CampusView column to a source field, roll daily attendance up to one row per student per date, keep the other columns, and run the same loader. Promote a real second mapping out of the parking lot before building it.

## History

How the "years to keep" setting purges older school years on a successful load, and why the extract must include every year that should survive.
