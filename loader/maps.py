import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from psycopg import sql

# file, extract table, extract column, columns as name:kind
MAPS = (
    ("map_attendance_codes.csv", "attendance", "excuseID", "attendance_code:key,label:label,counts_as:counts_as,absence_portion:portion"),
    ("map_behavior_types.csv", "behavior_type", "code", "behavior_code:key,label:label"),
    ("map_locations.csv", "behavior_incident", "location", "location_code:key,label:label"),
    ("map_consequences.csv", "behavior_res_type", "code", "consequence_code:key,label:label,is_exclusionary:bool"),
    ("map_genders.csv", "identity", "gender", "gender_code:key,label:label"),
    ("map_grades.csv", "enrollment", "grade", "grade_code:key,label:label,sort_order:sort"),
    ("map_race_groups.csv", "race_ethnicity", "code", "race_code:key,equity_group_label:label"),
    ("map_referral_statuses.csv", "behavior_incident", "status", "status_code:key,label:label,is_processed:bool,is_open:bool,is_cancelled:bool"),
    ("map_plan_types.csv", "plan_type", "type", "plan_type_code:key,plan_type:plan,label:label"),
    ("map_plan_statuses.csv", "plan", "status", "status_code:key,is_active:bool"),
)
_COUNTS_AS = "PRESENT, ABSENT_EXCUSED, ABSENT_UNEXCUSED, TARDY_EXCUSED, TARDY_UNEXCUSED, PARTIAL"


def _columns(spec):
    return tuple(piece.split(":") for piece in spec[3].split(","))


def _check(kind, text):
    if text == "":
        return None, "blank required cell"
    if kind == "key":
        return text, None
    if kind == "label":
        if any(ord(char) < 32 or ord(char) == 127 for char in text):
            return None, "contains a control character"
        if not 1 <= len(text) <= 80:
            return None, "not 1 to 80 characters"
        return text, None
    if kind == "counts_as":
        if text not in _COUNTS_AS.split(", "):
            return None, "not one of " + _COUNTS_AS
        return text, None
    if kind == "portion":
        try:
            number = Decimal(text)
        except InvalidOperation:
            return None, "not a decimal from 0 through 1"
        if not number.is_finite() or number < 0 or number > 1:
            return None, "not a decimal from 0 through 1"
        return number, None
    if kind == "bool":
        if text in ("true", "false"):
            return text == "true", None
        return None, "not true or false"
    if kind == "plan":
        if text in ("504", "IEP"):
            return text, None
        return None, "not 504 or IEP"
    try:
        number = int(text)
    except ValueError:
        return None, "not an integer"
    # Past these bounds Postgres says "integer out of range" and names no file.
    if number < -2147483648 or number > 2147483647:
        return None, "not an integer"
    return number, None


def read_maps(district: Path, check_header):
    if not district.is_dir():
        text = (
            "That path is not a district config folder."
            if district.exists()
            else "The district config folder is not on this machine."
        )
        return [text], None
    problems, loaded = [], []
    for spec in MAPS:
        filename, columns = spec[0], _columns(spec)
        path = district / filename
        if not path.is_file():
            problems.append(f"{filename}: fail. The file is missing from the folder.")
            continue
        reason, header = check_header(path, tuple(name for name, _kind in columns))
        if reason:
            problems.append(f"{filename}: fail. {reason}")
            continue
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                raw_rows = list(csv.reader(handle))
        except csv.Error:
            problems.append(f"{filename}: fail. The file is not valid CSV.")
            continue
        rows, row_problems = _rows(filename, columns, header, raw_rows)
        problems.extend(row_problems)
        loaded.append((spec, rows))
    return (problems, None) if problems else ([], loaded)


def _rows(filename, columns, header, raw_rows):
    problems, parsed, seen_keys, seen_sorts = [], [], set(), set()
    key_name = next(name for name, kind in columns if kind == "key")
    sort_name = next((name for name, kind in columns if kind == "sort"), None)
    for line_no, raw in enumerate(raw_rows[1:], start=2):
        if len(raw) != len(header):
            problems.append(f"{filename}: fail. Line {line_no}: row length does not match the header.")
            continue
        by_name, values, bad = dict(zip(header, raw)), [], False
        key_value = sort_value = None
        for name, kind in columns:
            value, reason = _check(kind, by_name[name])
            if reason:
                problems.append(f"{filename}: fail. Line {line_no}: {name}: {reason}.")
                bad = True
            elif kind == "key":
                key_value = value
            elif kind == "sort":
                sort_value = value
            values.append(value)
        if key_value in seen_keys:
            problems.append(f"{filename}: fail. Line {line_no}: {key_name}: duplicate key.")
            bad = True
        elif key_value is not None:
            seen_keys.add(key_value)
        if sort_value in seen_sorts:
            problems.append(f"{filename}: fail. Line {line_no}: {sort_name}: duplicate sort_order.")
            bad = True
        elif sort_value is not None:
            seen_sorts.add(sort_value)
        if not bad:
            parsed.append(tuple(values))
    return parsed, problems


def replace_maps(conn, loaded):
    conn.execute("CREATE SCHEMA IF NOT EXISTS ref")
    lines = []
    for spec, rows in loaded:
        columns = _columns(spec)
        table = spec[0].removesuffix(".csv")
        conn.execute(sql.SQL("DROP TABLE IF EXISTS ref.{}").format(sql.Identifier(table)))
        definitions = sql.SQL(", ").join(
            sql.SQL("{} {}").format(
                sql.Identifier(name),
                sql.SQL({"portion": "numeric", "bool": "boolean", "sort": "integer"}.get(kind, "text")),
            )
            for name, kind in columns
        )
        conn.execute(sql.SQL("CREATE TABLE ref.{} ({})").format(sql.Identifier(table), definitions))
        if rows:
            names = sql.SQL(", ").join(sql.Identifier(name) for name, _kind in columns)
            places = sql.SQL(", ").join(sql.Placeholder() for _column in columns)
            statement = sql.SQL("INSERT INTO ref.{} ({}) VALUES ({})").format(sql.Identifier(table), names, places)
            with conn.cursor() as cursor:
                cursor.executemany(statement, rows)
        noun = "row" if len(rows) == 1 else "rows"
        lines.append(f"{spec[0]}: pass, {len(rows)} {noun}.")
    notes = []
    for spec, _rows in loaded:
        count, first = conn.execute(_warning_query(spec)).fetchone()
        if count:
            noun = "row" if count == 1 else "rows"
            notes.append(f"Warning: {spec[1]}.csv column {spec[2]}: {count} {noun}, no map row (first line {first}).")
    return lines, notes


def _warning_query(spec):
    key = sql.Identifier(next(name for name, kind in _columns(spec) if kind == "key"))
    mapped = sql.SQL("ref.{}").format(sql.Identifier(spec[0].removesuffix(".csv")))
    if spec[0] == "map_attendance_codes.csv":
        source = sql.SQL(
            'SELECT (row_number() OVER (ORDER BY a.ctid)) + 1 AS line, e.code AS code '
            'FROM ic.attendance a JOIN ic.attendance_excuse e ON e."excuseID" = a."excuseID"'
        )
    else:
        source = sql.SQL(
            "SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line, {code} AS code FROM ic.{table}"
        ).format(code=sql.Identifier(spec[2]), table=sql.Identifier(spec[1]))
    return sql.SQL(
        "SELECT count(*)::int, min(line)::int FROM ({source}) src "
        "WHERE code IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {mapped} m WHERE m.{key} = src.code)"
    ).format(source=source, mapped=mapped, key=key)
