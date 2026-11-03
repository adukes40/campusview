from psycopg import sql

from loader.contract import FILES, REQUIRED, kind

_TYPE = {"bool": "boolean", "num": "numeric", "year": "integer", "timestamp": "timestamp"}
_RULE = {
    "id": "odd id characters",
    "text": "control character",
    "bool": "bad boolean",
    "num": "bad number",
    "year": "bad school year",
    "timestamp": "bad timestamp",
}


def replace_ic(conn) -> list[str]:
    conn.execute("CREATE SCHEMA IF NOT EXISTS ic")
    notes = []
    for filename, columns in FILES.items():
        _rebuild(conn, filename, columns)
        notes.extend(_value_warnings(conn, filename, columns))
    notes.extend(_cross_warnings(conn))
    return notes


def _cast(column, expr):
    kind_name = kind(column)
    if kind_name == "id":
        return sql.SQL("CASE WHEN {e} ~ {p} THEN {e} END").format(
            e=expr, p=sql.Literal(r"^[A-Za-z0-9_-]{1,64}$")
        )
    if kind_name == "text":
        return sql.SQL("CASE WHEN {e} ~ '[[:cntrl:]]' THEN NULL ELSE {e} END").format(e=expr)
    type_name = _TYPE[kind_name]
    return sql.SQL("CASE WHEN pg_input_is_valid({e}, {n}) THEN {e}::{t} END").format(
        e=expr, n=sql.Literal(type_name), t=sql.SQL(type_name)
    )


def _rebuild(conn, filename, columns):
    table = filename.removesuffix(".csv")
    conn.execute(sql.SQL("DROP TABLE IF EXISTS {}.{}").format(sql.Identifier("ic"), sql.Identifier(table)))
    selected = sql.SQL(", ").join(
        sql.SQL("{} AS {}").format(_cast(column, sql.Identifier(column)), sql.Identifier(column))
        for column in columns
    )
    conn.execute(
        sql.SQL("CREATE TABLE {}.{} AS SELECT {} FROM {}.{}").format(
            sql.Identifier("ic"),
            sql.Identifier(table),
            selected,
            sql.Identifier("raw"),
            sql.Identifier(table),
        )
    )


def _value_warnings(conn, filename, columns):
    table = sql.Identifier(filename.removesuffix(".csv"))
    required = set(REQUIRED.get(filename, ()))
    hits = []
    for column in columns:
        col = sql.Identifier(column)
        if column in required:
            hits.append(
                sql.SQL("CASE WHEN {c} IS NULL THEN {lab} END").format(
                    c=col, lab=sql.Literal(f"{column}|blank required field")
                )
            )
        hits.append(
            sql.SQL("CASE WHEN {c} IS NOT NULL AND ({cast}) IS NULL THEN {lab} END").format(
                c=col,
                cast=_cast(column, col),
                lab=sql.Literal(f"{column}|{_RULE[kind(column)]}"),
            )
        )
    rows = conn.execute(
        sql.SQL(
            """
            SELECT split_part(hit, '|', 1), split_part(hit, '|', 2), count(*)::int, min(line)
            FROM (
                SELECT line, unnest(ARRAY[{hits}]) AS hit
                FROM (
                    SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line, t.*
                    FROM raw.{table} t
                ) src
            ) flat
            WHERE hit IS NOT NULL
            GROUP BY hit
            """
        ).format(hits=sql.SQL(", ").join(hits), table=table)
    ).fetchall()
    notes = []
    for column, rule, count, line in rows:
        noun = "row" if count == 1 else "rows"
        notes.append(f"Warning: {filename} column {column}: {count} {noun}, {rule} (first line {line}).")
    return notes


def _cross_warnings(conn):
    checks = (
        (
            "enrollment.csv",
            "two grades for the same student, school, and year",
            """
            SELECT count(*)::int FROM ic.enrollment e
            JOIN ic.calendar c ON c."calendarID" = e."calendarID"
            WHERE e."personID" IS NOT NULL AND c."schoolID" IS NOT NULL
              AND e."endYear" IS NOT NULL AND e.grade IS NOT NULL
              AND (e."personID", c."schoolID", e."endYear") IN (
                  SELECT e2."personID", c2."schoolID", e2."endYear"
                  FROM ic.enrollment e2
                  JOIN ic.calendar c2 ON c2."calendarID" = e2."calendarID"
                  WHERE e2."personID" IS NOT NULL AND c2."schoolID" IS NOT NULL
                    AND e2."endYear" IS NOT NULL AND e2.grade IS NOT NULL
                  GROUP BY 1, 2, 3
                  HAVING count(DISTINCT e2.grade) > 1
              )
            """,
        ),
        (
            "attendance.csv",
            "attendance outside enrollment",
            """
            SELECT count(*)::int FROM ic.attendance a
            JOIN ic.calendar ac ON ac."calendarID" = a."calendarID"
            WHERE a."personID" IS NOT NULL AND a."date" IS NOT NULL AND ac."schoolID" IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM ic.enrollment e
                  JOIN ic.calendar ec ON ec."calendarID" = e."calendarID"
                  WHERE e."personID" = a."personID" AND ec."schoolID" = ac."schoolID"
                    AND e."startDate" IS NOT NULL AND a."date" >= e."startDate"
                    AND (e."endDate" IS NULL OR a."date" <= e."endDate")
              )
            """,
        ),
        (
            "behavior_resolution.csv",
            "action date before the incident was entered",
            """
            SELECT count(*)::int FROM ic.behavior_resolution res
            WHERE res."discassignDate" IS NOT NULL AND EXISTS (
                SELECT 1 FROM ic.behavior_role role
                JOIN ic.behavior_event ev ON ev."eventID" = role."eventID"
                JOIN ic.behavior_incident inc ON inc."incidentID" = ev."incidentID"
                WHERE role."roleID" = res."roleID" AND inc."timestamp" IS NOT NULL
                  AND res."discassignDate"::date < inc."timestamp"::date
            )
            """,
        ),
    )
    notes = []
    for filename, rule, query in checks:
        count = conn.execute(query).fetchone()[0]
        if count:
            noun = "row" if count == 1 else "rows"
            notes.append(f"Warning: {filename}: {count} {noun}, {rule}.")
    return notes
