from psycopg import sql

from loader.contract import FILES, REQUIRED, kind

RULE = {
    "id": "odd id characters",
    "text": "control character",
    "bool": "bad boolean",
    "num": "bad number",
    "year": "bad school year",
    "time": "bad time",
    "date": "bad date",
    "stamp": "bad timestamp",
}


def replace_ic(conn) -> list[str]:
    conn.execute("CREATE SCHEMA IF NOT EXISTS ic")
    for filename, columns in FILES.items():
        _rebuild(conn, filename, columns)
    notes = []
    for filename, columns in FILES.items():
        notes.extend(_value_warnings(conn, filename, columns))
    notes.extend(_cross_warnings(conn))
    return notes


def _col(alias, name):
    return sql.SQL("{}.{}").format(sql.Identifier(alias), sql.Identifier(name))


def _pattern(expr, pattern):
    return sql.SQL("({expr}) ~ {pattern}").format(expr=expr, pattern=sql.Literal(pattern))


def _valid_date(expr):
    year = sql.SQL("substring(({expr}) from 1 for 4)").format(expr=expr)
    month = sql.SQL("substring(({expr}) from 6 for 2)").format(expr=expr)
    day = sql.SQL("substring(({expr}) from 9 for 2)").format(expr=expr)
    leap = sql.SQL(
        "CASE WHEN ({year})::integer % 400 = 0 THEN '29' "
        "WHEN ({year})::integer % 100 = 0 THEN '28' "
        "WHEN ({year})::integer % 4 = 0 THEN '29' ELSE '28' END"
    ).format(year=year)
    last = sql.SQL(
        "CASE WHEN {month} = '02' THEN {leap} "
        "WHEN {month} IN ('04', '06', '09', '11') THEN '30' ELSE '31' END"
    ).format(month=month, leap=leap)
    return sql.SQL(
        "CASE WHEN {shape} THEN ({year}) <> '0000' "
        "AND ({month}) BETWEEN '01' AND '12' "
        "AND ({day}) BETWEEN '01' AND ({last}) ELSE false END"
    ).format(
        shape=_pattern(expr, r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
        year=year,
        month=month,
        day=day,
        last=last,
    )


def _valid_stamp(expr):
    head = sql.SQL("substring(({expr}) from 1 for 10)").format(expr=expr)
    rest = sql.SQL("substring(({expr}) from 11)").format(expr=expr)
    clock = (
        r"^ ([01][0-9]|2[0-3]):[0-5][0-9]",
        r"^ ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]",
        r"^ ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9][.][0-9]{1,6}",
    )
    time_ok = sql.SQL("({rest}) ~ {empty} OR ({rest}) ~ {hm} OR ({rest}) ~ {hms} OR ({rest}) ~ {frac}").format(
        rest=rest,
        empty=sql.Literal(r"^$"),
        hm=sql.Literal(clock[0] + "$"),
        hms=sql.Literal(clock[1] + "$"),
        frac=sql.Literal(clock[2] + "$"),
    )
    return sql.SQL(
        "CASE WHEN length(({expr})) >= 10 AND {date_ok} THEN {time_ok} ELSE false END"
    ).format(expr=expr, date_ok=_valid_date(head), time_ok=time_ok)


def _cast_id(expr):
    return sql.SQL("CASE WHEN {ok} THEN ({expr}) ELSE NULL END").format(
        ok=_pattern(expr, r"^[A-Za-z0-9_-]{1,64}$"), expr=expr
    )


def _cast_text(expr):
    return sql.SQL("CASE WHEN {bad} THEN NULL ELSE ({expr}) END").format(
        bad=_pattern(expr, "[[:cntrl:]]"), expr=expr
    )


def _cast_bool(expr):
    return sql.SQL(
        "CASE WHEN ({expr}) = 'true' THEN true WHEN ({expr}) = 'false' THEN false ELSE NULL END"
    ).format(expr=expr)


def _cast_num(expr):
    return sql.SQL("CASE WHEN {ok} THEN ({expr})::numeric ELSE NULL END").format(
        ok=_pattern(expr, r"^-?[0-9]{1,30}([.][0-9]{1,10})?$"), expr=expr
    )


def _cast_year(expr):
    return sql.SQL("CASE WHEN {ok} THEN ({expr})::integer ELSE NULL END").format(
        ok=_pattern(expr, r"^[12][0-9]{3}$"), expr=expr
    )


def _cast_time(expr):
    return sql.SQL("CASE WHEN {ok} THEN ({expr})::time ELSE NULL END").format(
        ok=_pattern(expr, r"^([01][0-9]|2[0-3]):[0-5][0-9]$"), expr=expr
    )


def _cast_date(expr):
    return sql.SQL("CASE WHEN {ok} THEN ({expr})::date ELSE NULL END").format(ok=_valid_date(expr), expr=expr)


def _cast_stamp(expr):
    return sql.SQL("CASE WHEN {ok} THEN ({expr})::timestamp ELSE NULL END").format(
        ok=_valid_stamp(expr), expr=expr
    )


_CAST = {
    "id": _cast_id,
    "text": _cast_text,
    "bool": _cast_bool,
    "num": _cast_num,
    "year": _cast_year,
    "time": _cast_time,
    "date": _cast_date,
    "stamp": _cast_stamp,
}


def _typed(column, expr):
    return _CAST[kind(column)](expr)


def _rebuild(conn, filename, columns):
    table = filename.removesuffix(".csv")
    conn.execute(sql.SQL("DROP TABLE IF EXISTS {}.{}").format(sql.Identifier("ic"), sql.Identifier(table)))
    selected = sql.SQL(", ").join(
        sql.SQL("{} AS {}").format(_typed(column, sql.Identifier(column)), sql.Identifier(column))
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


def _warning(filename, column, count, line, rule):
    noun = "row" if count == 1 else "rows"
    return f"Warning: {filename} column {column}: {count} {noun}, {rule} (first line {line})."


def _value_warnings(conn, filename, columns):
    table = filename.removesuffix(".csv")
    required = set(REQUIRED[filename])
    notes = []
    for column in columns:
        blank_count, blank_line, bad_count, bad_line = conn.execute(
            sql.SQL(
                """
                SELECT count(*) FILTER (WHERE raw_value IS NULL),
                       min(line) FILTER (WHERE raw_value IS NULL),
                       count(*) FILTER (WHERE raw_value IS NOT NULL AND typed_value IS NULL),
                       min(line) FILTER (WHERE raw_value IS NOT NULL AND typed_value IS NULL)
                FROM (
                    SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line,
                           {col} AS raw_value,
                           {typed} AS typed_value
                    FROM {schema}.{table}
                ) cells
                """
            ).format(
                col=sql.Identifier(column),
                typed=_typed(column, sql.Identifier(column)),
                schema=sql.Identifier("raw"),
                table=sql.Identifier(table),
            )
        ).fetchone()
        if column in required and blank_count:
            notes.append(_warning(filename, column, blank_count, blank_line, "blank required field"))
        if bad_count:
            notes.append(_warning(filename, column, bad_count, bad_line, RULE[kind(column)]))
    return notes


def _one(conn, filename, column, rule, query):
    count, line = conn.execute(query).fetchone()
    if not count:
        return None
    return _warning(filename, column, count, line, rule)


def _cross_warnings(conn):
    person = _typed("personID", _col("n", "personID"))
    end_year = _typed("endYear", _col("n", "endYear"))
    grade = _typed("grade", _col("n", "grade"))
    school = _typed("schoolID", _col("c", "schoolID"))
    grades = sql.SQL(
        """
        WITH numbered AS (
            SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line,
                   "personID", "calendarID", "endYear", "grade"
            FROM raw.enrollment
        ),
        marked AS (
            SELECT n.line, {person} AS person_id, {school} AS school_id,
                   {end_year} AS end_year, {grade} AS grade
            FROM numbered n
            JOIN raw.calendar c ON c."calendarID" = n."calendarID"
        )
        SELECT count(*), min(line)
        FROM marked
        WHERE person_id IS NOT NULL AND school_id IS NOT NULL
          AND end_year IS NOT NULL AND grade IS NOT NULL
          AND (person_id, school_id, end_year) IN (
              SELECT person_id, school_id, end_year
              FROM marked
              WHERE person_id IS NOT NULL AND school_id IS NOT NULL
                AND end_year IS NOT NULL AND grade IS NOT NULL
              GROUP BY person_id, school_id, end_year
              HAVING count(DISTINCT grade) > 1
          )
        """
    ).format(person=person, school=school, end_year=end_year, grade=grade)
    person_a = _typed("personID", _col("n", "personID"))
    school_a = _typed("schoolID", _col("ac", "schoolID"))
    person_e = _typed("personID", _col("e", "personID"))
    school_e = _typed("schoolID", _col("ec", "schoolID"))
    outside = sql.SQL(
        """
        WITH numbered AS (
            SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line,
                   "personID", "calendarID", "date"
            FROM raw.attendance
        )
        SELECT count(*), min(n.line)
        FROM numbered n
        JOIN raw.calendar ac ON ac."calendarID" = n."calendarID"
        WHERE {person_a} IS NOT NULL AND {school_a} IS NOT NULL AND {date_ok}
          AND NOT EXISTS (
              SELECT 1
              FROM raw.enrollment e
              JOIN raw.calendar ec ON ec."calendarID" = e."calendarID"
              WHERE {person_e} = {person_a}
                AND {school_e} = {school_a}
                AND {start_ok}
                AND e."startDate" <= n."date"
                AND (e."endDate" IS NULL OR ({end_ok} AND n."date" <= e."endDate"))
          )
        """
    ).format(
        person_a=person_a,
        school_a=school_a,
        date_ok=_valid_date(_col("n", "date")),
        person_e=person_e,
        school_e=school_e,
        start_ok=_valid_date(_col("e", "startDate")),
        end_ok=_valid_date(_col("e", "endDate")),
    )
    before = sql.SQL(
        """
        WITH numbered AS (
            SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line,
                   "roleID", "discassignDate"
            FROM raw.behavior_resolution
        )
        SELECT count(*), min(n.line)
        FROM numbered n
        WHERE {action_ok}
          AND EXISTS (
              SELECT 1
              FROM raw.behavior_role role
              JOIN raw.behavior_event ev ON ev."eventID" = role."eventID"
              JOIN raw.behavior_incident inc ON inc."incidentID" = ev."incidentID"
              WHERE role."roleID" = n."roleID"
                AND {stamp_ok}
                AND n."discassignDate" < substring(inc."timestamp" from 1 for 10)
          )
        """
    ).format(
        action_ok=_valid_date(_col("n", "discassignDate")),
        stamp_ok=_valid_stamp(_col("inc", "timestamp")),
    )
    found = [
        _one(conn, "enrollment.csv", "grade", "two grades for the same student, school, and year", grades),
        _one(conn, "attendance.csv", "date", "attendance outside enrollment", outside),
        _one(
            conn,
            "behavior_resolution.csv",
            "discassignDate",
            "action date before the incident was entered",
            before,
        ),
    ]
    return [note for note in found if note]
