import csv
import os
import re
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import psycopg
from psycopg import sql

from loader.contract import FILES
from loader.maps import read_maps, replace_maps
from loader.typed import replace_ic

LOCK = 814202611


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("Usage: python -m loader FOLDER DISTRICT\n")
        return 2
    ok, saved, report = load_drop(Path(argv[1]), Path(argv[2]))
    sys.stdout.write(report)
    return 0 if ok and saved else 1


def read_cutoff(district: Path) -> tuple[str | None, str | None]:
    if not district.is_dir():
        return None, None
    found = None
    try:
        text = (district / "settings").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("cutoff_date="):
            found = line.split("=", 1)[1].strip()
    if not found:
        return None, "The district config folder has no cutoff date."
    try:
        if date.fromisoformat(found).isoformat() != found:
            raise ValueError
    except ValueError:
        return None, "The cutoff date is not YYYY-MM-DD."
    return found, None


def _phrase(fault, map_lines, district: Path) -> str:
    if not map_lines:
        return "the extract" if fault == "extract" else "the server"
    district_phrase = (
        "the district config folder"
        if not district.is_dir()
        else "the district config folder's map files"
    )
    if fault == "server":
        return "the server"
    if fault == "extract":
        return f"the extract and {district_phrase}"
    return district_phrase


def load_drop(folder: Path, district: Path) -> tuple[bool, bool, str]:
    started = datetime.now(UTC)
    fault, lines, ready = check_folder(folder)
    map_lines, maps = read_maps(district, check_header)
    cutoff, cutoff_problem = read_cutoff(district)
    phrase = _phrase(fault, map_lines, district)
    if cutoff_problem and not map_lines and district.is_dir():
        phrase = "the district config folder"
    if cutoff_problem:
        map_lines = [*map_lines, cutoff_problem]
    if map_lines:
        lines = [*lines, *map_lines]
        if not district.is_dir():
            fault = fault or "server"
        else:
            fault = "server" if fault == "server" else "extract"
    if not os.environ.get("CV_OWNER_DB_PASSWORD"):
        if not fault:
            fault, lines = "server", ["CV_OWNER_DB_PASSWORD is not set."]
        return False, False, render(False, phrase, lines, [])
    try:
        conn = connect()
    except psycopg.Error:
        if not fault:
            fault, lines = "server", ["The database could not be reached."]
        return False, False, render(False, phrase, lines, [])
    copy_name = None
    warnings = []
    try:
        if not fault:
            with conn.transaction():
                locked = conn.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK,)).fetchone()[0]
                if not locked:
                    fault, lines = "server", ["Another load is already running."]
                    phrase = "the server"
                else:
                    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
                    lines = []
                    for name, path, columns, header, _has_data in ready:
                        copy_name = name
                        lines.append(copy_file(conn, name, path, columns, header))
                    copy_name = None
                    warnings = [
                        f"Warning: {name} has no data rows."
                        for name, _path, _columns, _header, has_data in ready
                        if not has_data
                    ]
                    warnings.extend(replace_ic(conn))
                    warnings.extend(
                        f"Warning: calendar {calendar_id} has enrollments and no Day rows."
                        for calendar_id in day_warnings(conn, cutoff)
                    )
                    passed, notes = replace_maps(conn, maps)
                    lines.extend(passed)
                    warnings.extend(notes)
                    fault = None
        ok = fault is None
        report = render(ok, phrase, lines, warnings)
        return ok, save_report(conn, report, ok, fault, started), report
    except psycopg.Error as exc:
        report = render(False, "the extract", [copy_failure(exc, copy_name)], [])
        return False, save_report(conn, report, False, "extract", started), report
    finally:
        conn.close()


def copy_failure(exc, name) -> str:
    message = "The database rejected the file."
    line_no = None
    if exc.diag is not None:
        primary = exc.diag.message_primary or ""
        quoted = re.findall(r'"([^"]*)"', primary)
        columns = FILES.get(name or "", ())
        if primary and "\n" not in primary and all(part in columns for part in quoted):
            message = primary
        if exc.diag.context:
            found = re.search(r"\bline (\d+)\b", exc.diag.context)
            if found:
                line_no = found.group(1)
    if line_no:
        message = f"Line {line_no}: {message}"
    return f"{name}: fail. {message}" if name else message


def check_folder(folder: Path):
    message = ""
    names = []
    if not folder.exists():
        message = "The folder is not on this machine."
    elif not folder.is_dir():
        message = "That path is not a folder."
    else:
        try:
            names = [
                entry.name
                for entry in folder.iterdir()
                if not entry.is_symlink() and entry.is_file() and entry.name.lower().endswith(".csv")
            ]
        except OSError:
            message = "The server could not read the folder."
    if message:
        return "server", [message], []
    problems = []
    ready = []

    def problem(name, reason):
        problems.append(f"{name}: fail. {reason}")

    for name, columns in FILES.items():
        path = folder / name
        if path.is_symlink():
            problem(name, "The file is a link. Remove it.")
            continue
        if not path.is_file():
            problem(name, "The file is missing from the folder.")
            continue
        reason, header = check_header(path, columns)
        if reason:
            problem(name, reason)
            continue
        data = has_rows(path)
        if name in ("school.csv", "calendar.csv") and not data:
            problem(name, "The file has no data rows.")
        else:
            ready.append((name, path, columns, header, data))
    for name in sorted(names):
        if name not in FILES:
            problem(name, "This file is not in the extract contract.")
    if problems:
        return "extract", problems, []
    return None, [], ready


def has_rows(path: Path) -> bool:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return next(reader, None) is not None


def header_names(label: str, names: list[str]) -> str:
    shown = [name for name in names if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name)]
    hidden = len(names) - len(shown)
    parts = []
    if shown:
        parts.append(label + " " + ", ".join(shown) + ".")
    if hidden:
        parts.append(f"Line 1: the header has {hidden} unknown columns.")
    return " ".join(parts)


def check_header(path: Path, columns: tuple[str, ...]):
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), None)
    except UnicodeDecodeError:
        return "The file is not UTF-8.", None
    except OSError:
        return "The server could not read this file.", None
    if not header:
        return "The file has no header row.", None
    if any(name == "" for name in header):
        return "A column has no name.", None
    repeated = sorted({name for name in header if header.count(name) > 1})
    if repeated:
        return header_names("Repeated column", repeated), None
    unknown = [name for name in header if name not in columns]
    missing = [name for name in columns if name not in header]
    parts = []
    if unknown:
        parts.append(header_names("Unknown column", unknown))
    if missing:
        parts.append("Missing column " + ", ".join(missing) + ".")
    if parts:
        return " ".join(parts), None
    return "", header


def connect():
    return psycopg.connect(
        host="127.0.0.1",
        port=os.environ.get("CV_PG_PORT", "5432"),
        dbname=os.environ.get("CV_PG_DATABASE", "campusview_data"),
        user=os.environ.get("CV_PG_USER", "campusview_owner"),
        password=os.environ["CV_OWNER_DB_PASSWORD"],
    )


def copy_file(conn, name: str, path: Path, columns: tuple[str, ...], header) -> str:
    table = name.removesuffix(".csv")
    ensure_table(conn, table, columns)
    conn.execute(sql.SQL("TRUNCATE {}.{}").format(sql.Identifier("raw"), sql.Identifier(table)))
    listed = sql.SQL(", ").join(sql.Identifier(column) for column in header)
    statement = sql.SQL(
        "COPY {}.{} ({}) FROM STDIN WITH (FORMAT csv, HEADER true, FORCE_NULL ({}))"
    ).format(sql.Identifier("raw"), sql.Identifier(table), listed, listed)
    with conn.cursor() as cur, path.open("rb") as handle:
        with cur.copy(statement) as copy:
            copy.write(handle.read())
        count = cur.rowcount
    noun = "row" if count == 1 else "rows"
    return f"{name}: pass, {count} {noun}."


def ensure_table(conn, table: str, columns: tuple[str, ...]) -> None:
    conn.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
            sql.Identifier("raw"),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(column)) for column in columns),
        )
    )
    for column in columns:
        conn.execute(
            sql.SQL("ALTER TABLE {}.{} ADD COLUMN IF NOT EXISTS {} text").format(
                sql.Identifier("raw"),
                sql.Identifier(table),
                sql.Identifier(column),
            )
        )


def day_warnings(conn, cutoff: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT e."calendarID"
        FROM raw.enrollment e
        WHERE e."calendarID" ~ '^[0-9]+$'
          AND COALESCE(e."endDate", e."startDate") >= %s
          AND NOT EXISTS (
              SELECT 1 FROM raw.day d WHERE d."calendarID" = e."calendarID"
          )
        GROUP BY e."calendarID"
        ORDER BY e."calendarID"::bigint
        """,
        (cutoff,),
    ).fetchall()
    return [row[0] for row in rows]


def render(ok: bool, phrase, lines, warnings) -> str:
    if ok:
        head = ["Load passed."]
        lines = [*lines, *warnings]
    else:
        head = [
            f"Load failed. This looks like a problem with {phrase}.",
            "Nothing was loaded. The previous data is still in place.",
        ]
    return "\n".join([*head, *lines]) + "\n"


def save_report(conn, report: str, ok: bool, fault, started: datetime) -> bool:
    try:
        with conn.transaction():
            conn.execute("CREATE SCHEMA IF NOT EXISTS ops")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ops.load_batch (
                    batch_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    started_at timestamptz NOT NULL,
                    finished_at timestamptz NOT NULL,
                    outcome text NOT NULL CHECK (outcome IN ('pass', 'fail')),
                    fault text CHECK (fault IS NULL OR fault IN ('extract', 'server')),
                    report text NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO ops.load_batch (started_at, finished_at, outcome, fault, report)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (started, datetime.now(UTC), "pass" if ok else "fail", fault, report),
            )
        return True
    except psycopg.Error:
        return False
