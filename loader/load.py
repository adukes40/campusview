import csv
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql

from loader.contract import FILES

LOCK = 814202611


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("Usage: python -m loader FOLDER\n")
        return 2
    ok, saved, report = load_drop(Path(argv[1]))
    sys.stdout.write(report)
    return 0 if ok and saved else 1


def load_drop(folder: Path) -> tuple[bool, bool, str]:
    started = datetime.now(UTC)
    fault, lines, ready = check_folder(folder)
    if fault:
        report = render(False, fault, lines, [])
        return False, record(report, False, fault, started), report
    if not os.environ.get("CV_OWNER_DB_PASSWORD"):
        report = render(False, "server", ["CV_OWNER_DB_PASSWORD is not set."], [])
        return False, False, report
    copy_name = None
    try:
        conn = connect()
    except psycopg.Error:
        report = render(False, "server", ["The database could not be reached."], [])
        return False, False, report
    try:
        with conn.transaction():
            locked = conn.execute("SELECT pg_try_advisory_xact_lock(%s)", (LOCK,)).fetchone()[0]
            if not locked:
                fault = "server"
                lines = ["Another load is already running."]
                warnings = []
            else:
                lines = []
                for name, path, columns in ready:
                    copy_name = name
                    lines.append(copy_file(conn, name, path, columns))
                warnings = day_warnings(conn)
                fault = None
        ok = fault is None
        report = render(ok, fault, lines, warnings)
        return ok, save_report(conn, report, ok, fault, started), report
    except psycopg.Error as exc:
        message = "The database rejected the file."
        if exc.diag is not None and exc.diag.message_primary:
            message = exc.diag.message_primary
        line = f"{copy_name}: fail. {message}" if copy_name else message
        report = render(False, "extract", [line], [])
        return False, save_report(conn, report, False, "extract", started), report
    finally:
        conn.close()


def check_folder(folder: Path):
    if not folder.exists():
        return "server", ["The folder is not on this machine."], []
    if not folder.is_dir():
        return "server", ["That path is not a folder."], []
    try:
        names = [entry.name for entry in folder.iterdir() if entry.is_file() and entry.name.lower().endswith(".csv")]
    except OSError:
        return "server", ["The server could not read the folder."], []
    problems = []
    ready = []
    for name, columns in FILES.items():
        path = folder / name
        if name not in names and not path.is_file():
            problems.append(f"{name}: fail. The file is missing from the folder.")
            continue
        reason = check_header(path, columns)
        if reason:
            problems.append(f"{name}: fail. {reason}")
        else:
            ready.append((name, path, columns))
    for name in sorted(names):
        if name not in FILES:
            problems.append(f"{name}: fail. This file is not in the extract contract.")
    if problems:
        return "extract", problems, []
    return None, [], ready


def check_header(path: Path, columns: tuple[str, ...]) -> str:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), None)
    except UnicodeDecodeError:
        return "The file is not UTF-8."
    except OSError:
        return "The server could not read this file."
    if not header:
        return "The file has no header row."
    if any(name == "" for name in header):
        return "A column has no name."
    repeated = sorted({name for name in header if header.count(name) > 1})
    if repeated:
        return "Repeated column " + ", ".join(repeated) + "."
    unknown = [name for name in header if name not in columns]
    missing = [name for name in columns if name not in header]
    parts = []
    if unknown:
        parts.append("Unknown column " + ", ".join(unknown) + ".")
    if missing:
        parts.append("Missing column " + ", ".join(missing) + ".")
    return " ".join(parts)


def connect():
    return psycopg.connect(
        host="127.0.0.1",
        port=os.environ.get("CV_PG_PORT", "5432"),
        dbname=os.environ.get("CV_PG_DATABASE", "campusview_data"),
        user=os.environ.get("CV_PG_USER", "campusview_owner"),
        password=os.environ["CV_OWNER_DB_PASSWORD"],
    )


def copy_file(conn, name: str, path: Path, columns: tuple[str, ...]) -> str:
    table = name.removesuffix(".csv")
    ensure_table(conn, table, columns)
    with path.open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    conn.execute(sql.SQL("TRUNCATE {}.{}").format(sql.Identifier("raw"), sql.Identifier(table)))
    statement = sql.SQL("COPY {}.{} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
        sql.Identifier("raw"),
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in header),
    )
    with conn.cursor() as cur, path.open("rb") as handle:
        with cur.copy(statement) as copy:
            copy.write(handle.read())
        count = cur.rowcount
    noun = "row" if count == 1 else "rows"
    return f"{name}: pass, {count} {noun}."


def ensure_table(conn, table: str, columns: tuple[str, ...]) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    conn.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
            sql.Identifier("raw"),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(column)) for column in columns),
        )
    )
    present = {
        row[0]
        for row in conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = %s
            """,
            (table,),
        )
    }
    for column in columns:
        if column not in present:
            conn.execute(
                sql.SQL("ALTER TABLE {}.{} ADD COLUMN {} text").format(
                    sql.Identifier("raw"),
                    sql.Identifier(table),
                    sql.Identifier(column),
                )
            )


def day_warnings(conn) -> list[str]:
    rows = conn.execute(
        """
        SELECT e."calendarID"
        FROM raw.enrollment e
        WHERE e."calendarID" ~ '^[0-9]+$'
          AND e."endYear" ~ '^[0-9]+$'
          AND e."endYear"::int >= (
              SELECT MAX(y."endYear"::int) - 1
              FROM raw.enrollment y
              WHERE y."endYear" ~ '^[0-9]+$'
          )
          AND NOT EXISTS (
              SELECT 1 FROM raw.day d WHERE d."calendarID" = e."calendarID"
          )
        GROUP BY e."calendarID"
        ORDER BY e."calendarID"::bigint
        """
    ).fetchall()
    return [row[0] for row in rows]


def render(ok: bool, fault, lines, warnings) -> str:
    if ok:
        head = ["Load passed."]
        lines = [
            *lines,
            *[f"Warning: calendar {calendar_id} has enrollments and no Day rows." for calendar_id in warnings],
        ]
    else:
        where = "the extract" if fault == "extract" else "the server"
        head = [
            f"Load failed. This looks like a problem with {where}.",
            "Nothing was loaded. The previous data is still in place.",
        ]
    return "\n".join([*head, *lines]) + "\n"


def record(report: str, ok: bool, fault, started: datetime) -> bool:
    if not os.environ.get("CV_OWNER_DB_PASSWORD"):
        return False
    try:
        conn = connect()
    except psycopg.Error:
        return False
    try:
        return save_report(conn, report, ok, fault, started)
    finally:
        conn.close()


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
