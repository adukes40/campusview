import os
import sys
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql

from loader.contract import FILES

LOCK = 814202611


@dataclass
class FileCheck:
    name: str
    ok: bool
    row_count: int
    reason: str
    server: bool = False
    rows: list[tuple[str | None, ...]] = field(default_factory=list, repr=False)


@dataclass
class DropResult:
    ok: bool
    fault: str | None
    files: list[FileCheck]
    warnings: list[str]
    note: str
    saved: bool
    report: str


class DatabaseError(Exception):
    def __init__(self, note: str) -> None:
        self.note = note


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("Usage: python -m loader FOLDER\n")
        return 2
    result = load_drop(Path(argv[1]))
    sys.stdout.write(result.report)
    if result.ok and result.saved:
        return 0
    return 1


def load_drop(folder: Path) -> DropResult:
    started = datetime.now(UTC)
    inspected = inspect_drop(folder)
    try:
        conn = connect()
    except DatabaseError as err:
        fault = inspected.fault if not inspected.ok else "server"
        failed = finish(False, fault, inspected.files, [], err.note, False)
        return failed
    try:
        outcome = write_all(conn, inspected) if inspected.ok else inspected
        saved = save_report(conn, outcome, started, datetime.now(UTC))
        if saved:
            return replace(outcome, saved=True)
        note = f"{outcome.note} The report was not saved.".strip()
        return finish(outcome.ok, outcome.fault, outcome.files, outcome.warnings, note, False)
    finally:
        conn.close()


def inspect_drop(folder: Path) -> DropResult:
    if not folder.exists():
        return finish(False, "server", [], [], "The folder is not on this machine.", False)
    if not folder.is_dir():
        return finish(False, "server", [], [], "That path is not a folder.", False)
    try:
        names = [
            entry.name
            for entry in folder.iterdir()
            if entry.is_file() and entry.name.lower().endswith(".csv")
        ]
    except OSError:
        return finish(False, "server", [], [], "The server could not read the folder.", False)

    checks: list[FileCheck] = []
    for name in FILES:
        path = folder / name
        if name not in names and not path.is_file():
            checks.append(
                FileCheck(name, False, 0, "The file is missing from the folder.", False, [])
            )
            continue
        checks.append(check_file(path, FILES[name]))
    for name in sorted(names):
        if name not in FILES:
            checks.append(
                FileCheck(name, False, 0, "This file is not in the extract contract.", False, [])
            )

    if all(check.ok for check in checks):
        return finish(True, None, checks, day_warnings(checks), "", False)
    if any(not check.ok and not check.server for check in checks):
        return finish(False, "extract", checks, [], "", False)
    return finish(False, "server", checks, [], "", False)


def finish(ok, fault, files, warnings, note, saved) -> DropResult:
    shown = warnings if ok else []
    return DropResult(ok, fault, files, shown, note, saved, render(ok, fault, files, shown, note))


def render(ok, fault, files, warnings, note) -> str:
    lines: list[str] = []
    if ok:
        lines.append("Load passed.")
    else:
        where = "the extract" if fault == "extract" else "the server"
        lines.append(f"Load failed. This looks like a problem with {where}.")
        lines.append("Nothing was loaded. The previous data is still in place.")
    if note:
        lines.append(note)
    for check in files:
        if check.ok:
            lines.append(f"{check.name}: pass, {row_phrase(check.row_count)}.")
        else:
            lines.append(f"{check.name}: fail, 0 rows. {check.reason}")
    for calendar_id in warnings:
        lines.append(f"Warning: calendar {calendar_id} has enrollments and no Day rows.")
    return "\n".join(lines) + "\n"


def row_phrase(count: int) -> str:
    if count == 1:
        return "1 row"
    return f"{count} rows"


def day_warnings(checks: list[FileCheck]) -> list[str]:
    enrollment = next(check for check in checks if check.name == "enrollment.csv")
    day = next(check for check in checks if check.name == "day.csv")
    enrollment_id = FILES["enrollment.csv"].index("calendarID")
    day_id = FILES["day.csv"].index("calendarID")
    present = {row[day_id] for row in day.rows if row[day_id]}
    missing: list[str] = []
    seen: set[str] = set()
    for row in enrollment.rows:
        calendar_id = row[enrollment_id]
        if calendar_id and calendar_id not in present and calendar_id not in seen:
            seen.add(calendar_id)
            missing.append(calendar_id)
    missing.sort()
    return missing


def check_file(path: Path, columns: tuple[str, ...]) -> FileCheck:
    try:
        data = path.read_bytes()
    except OSError:
        return FileCheck(path.name, False, 0, "The server could not read this file.", True, [])
    if data.startswith(b"\xef\xbb\xbf"):
        return reject(path.name, "The file starts with a UTF-8 BOM. Save it as UTF-8 with no BOM.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return reject(path.name, "The file is not UTF-8.")
    ending = line_error(text)
    if ending:
        return reject(path.name, ending)
    parsed: list[list[str]] = []
    for number, line in enumerate(text.split("\r\n")[:-1], start=1):
        fields = parse_line(line)
        if isinstance(fields, str):
            return reject(path.name, f"Row {number}: {fields}")
        parsed.append(fields)
    headers = parsed[0]
    if any(header == "" for header in headers):
        return reject(path.name, "A column has no name.")
    repeated = sorted({header for header in headers if headers.count(header) > 1})
    if repeated:
        return reject(path.name, "Repeated column " + ", ".join(repeated) + ".")
    unknown = [header for header in headers if header not in columns]
    missing = [column for column in columns if column not in headers]
    if unknown or missing:
        parts: list[str] = []
        if unknown:
            parts.append("Unknown column " + ", ".join(unknown) + ".")
        if missing:
            parts.append("Missing column " + ", ".join(missing) + ".")
        return reject(path.name, " ".join(parts))
    index = {name: position for position, name in enumerate(headers)}
    rows: list[tuple[str | None, ...]] = []
    width = len(headers)
    for number, fields in enumerate(parsed[1:], start=2):
        if len(fields) != width:
            return reject(
                path.name,
                f"Row {number} has {len(fields)} values and the header has {width}.",
            )
        rows.append(
            tuple(None if fields[index[column]] == "" else fields[index[column]] for column in columns)
        )
    return FileCheck(path.name, True, len(rows), "", False, rows)


def reject(name: str, reason: str) -> FileCheck:
    return FileCheck(name, False, 0, reason, False, [])


def line_error(text: str) -> str | None:
    if text == "":
        return "The file is empty."
    if "\x00" in text:
        return "The file contains a NUL byte."
    stripped = text.replace("\r\n", "")
    if "\n" in stripped or "\r" in stripped or not text.endswith("\r\n"):
        return "Line endings must be CRLF."
    return None


def parse_line(line: str) -> list[str] | str:
    if line == "":
        return "The row is blank."
    fields: list[str] = []
    index = 0
    size = len(line)
    while index < size:
        if line[index] == '"':
            index += 1
            chars: list[str] = []
            closed = False
            while index < size:
                if line[index] == '"':
                    if index + 1 < size and line[index + 1] == '"':
                        chars.append('"')
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                chars.append(line[index])
                index += 1
            if not closed:
                return "A quoted value is missing its closing quote."
            value = "".join(chars)
            if "," not in value:
                return "A value is quoted but does not contain a comma."
            fields.append(value)
        else:
            start = index
            while index < size and line[index] != ",":
                if line[index] == '"':
                    return "A quote appears in a value that does not contain a comma."
                index += 1
            fields.append(line[start:index])
        if index >= size:
            break
        if line[index] != ",":
            return "A quoted value is not followed by a comma."
        index += 1
        if index == size:
            fields.append("")
            break
    return fields


def connect():
    password = os.environ.get("CV_OWNER_DB_PASSWORD", "")
    if not password:
        raise DatabaseError("CV_OWNER_DB_PASSWORD is not set.")
    port = os.environ.get("CV_PG_PORT", "5432")
    try:
        port_number = int(port)
    except ValueError:
        raise DatabaseError("CV_PG_PORT is not a port number.") from None
    try:
        return psycopg.connect(
            host="127.0.0.1",
            port=port_number,
            dbname="campusview_data",
            user="campusview_owner",
            password=password,
            connect_timeout=10,
        )
    except psycopg.Error:
        raise DatabaseError("The database could not be reached.") from None


def write_all(conn, inspected: DropResult) -> DropResult:
    with conn.transaction():
        locked = conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK,)).fetchone()[0]
    if not locked:
        return finish(
            False,
            "server",
            inspected.files,
            [],
            "Another load is already running.",
            False,
        )
    try:
        try:
            with conn.transaction():
                write_tables(conn, inspected)
        except psycopg.Error as exc:
            return finish(
                False,
                "server",
                inspected.files,
                [],
                f"The database refused the load ({type(exc).__name__}).",
                False,
            )
        return inspected
    finally:
        try:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK,))
        except psycopg.Error:
            pass


def write_tables(conn, result: DropResult) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    for check in result.files:
        columns = FILES[check.name]
        table = check.name.removesuffix(".csv")
        conn.execute(
            sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
                sql.Identifier("raw"),
                sql.Identifier(table),
                sql.SQL(", ").join(
                    sql.SQL("{} text").format(sql.Identifier(column)) for column in columns
                ),
            )
        )
        present = {
            row[0]
            for row in conn.execute(
                """
                SELECT column_name
                FROM information_schema.columns
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
        conn.execute(sql.SQL("TRUNCATE {}.{}").format(sql.Identifier("raw"), sql.Identifier(table)))
        copy_sql = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
            sql.Identifier("raw"),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        )
        with conn.cursor() as cur, cur.copy(copy_sql) as copy:
            for row in check.rows:
                copy.write_row(row)


def save_report(conn, result: DropResult, started: datetime, finished: datetime) -> bool:
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
                (
                    started,
                    finished,
                    "pass" if result.ok else "fail",
                    result.fault,
                    result.report,
                ),
            )
        return True
    except psycopg.Error:
        return False
