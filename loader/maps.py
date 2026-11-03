import csv
import enum
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from psycopg import sql

from loader.contract import FILES


class Rule(enum.Enum):
    KEY = "key"
    LABEL = "label"
    COUNTS_AS = "counts_as"
    PORTION = "portion"
    BOOL = "bool"
    PLAN_TYPE = "plan_type"
    SORT = "sort"


_SQL = {
    Rule.KEY: "text",
    Rule.LABEL: "text",
    Rule.COUNTS_AS: "text",
    Rule.PLAN_TYPE: "text",
    Rule.PORTION: "numeric",
    Rule.BOOL: "boolean",
    Rule.SORT: "integer",
}

_COUNTS_AS = (
    "PRESENT",
    "ABSENT_EXCUSED",
    "ABSENT_UNEXCUSED",
    "TARDY_EXCUSED",
    "TARDY_UNEXCUSED",
    "PARTIAL",
)
_PLAN_TYPES = frozenset({"504", "IEP"})
_PORTION = re.compile(r"^(?:0(?:\.[0-9]+)?|1(?:\.0+)?)$")
_SORT = re.compile(r"^(?:0|-?[1-9][0-9]*)$")
_SORT_MIN = -2147483648
_SORT_MAX = 2147483647


@dataclass(frozen=True)
class _Spec:
    file: str
    columns: tuple[tuple[str, Rule], ...]
    extract_file: str
    extract_column: str

    @property
    def table(self) -> str:
        return self.file.removesuffix(".csv")

    @property
    def key(self) -> str:
        return next(name for name, rule in self.columns if rule is Rule.KEY)


_MAPS = (
    _Spec(
        "map_attendance_codes.csv",
        (
            ("attendance_code", Rule.KEY),
            ("label", Rule.LABEL),
            ("counts_as", Rule.COUNTS_AS),
            ("absence_portion", Rule.PORTION),
        ),
        "attendance_excuse.csv",
        "code",
    ),
    _Spec(
        "map_behavior_types.csv",
        (
            ("behavior_code", Rule.KEY),
            ("label", Rule.LABEL),
        ),
        "behavior_type.csv",
        "code",
    ),
    _Spec(
        "map_locations.csv",
        (
            ("location_code", Rule.KEY),
            ("label", Rule.LABEL),
        ),
        "behavior_incident.csv",
        "location",
    ),
    _Spec(
        "map_consequences.csv",
        (
            ("consequence_code", Rule.KEY),
            ("label", Rule.LABEL),
            ("is_exclusionary", Rule.BOOL),
        ),
        "behavior_res_type.csv",
        "code",
    ),
    _Spec(
        "map_genders.csv",
        (
            ("gender_code", Rule.KEY),
            ("label", Rule.LABEL),
        ),
        "identity.csv",
        "gender",
    ),
    _Spec(
        "map_grades.csv",
        (
            ("grade_code", Rule.KEY),
            ("label", Rule.LABEL),
            ("sort_order", Rule.SORT),
        ),
        "enrollment.csv",
        "grade",
    ),
    _Spec(
        "map_race_groups.csv",
        (
            ("race_code", Rule.KEY),
            ("equity_group_label", Rule.LABEL),
        ),
        "race_ethnicity.csv",
        "code",
    ),
    _Spec(
        "map_referral_statuses.csv",
        (
            ("status_code", Rule.KEY),
            ("label", Rule.LABEL),
            ("is_processed", Rule.BOOL),
            ("is_open", Rule.BOOL),
            ("is_cancelled", Rule.BOOL),
        ),
        "behavior_incident.csv",
        "status",
    ),
    _Spec(
        "map_plan_types.csv",
        (
            ("plan_type_code", Rule.KEY),
            ("plan_type", Rule.PLAN_TYPE),
            ("label", Rule.LABEL),
        ),
        "plan_type.csv",
        "type",
    ),
    _Spec(
        "map_plan_statuses.csv",
        (
            ("status_code", Rule.KEY),
            ("is_active", Rule.BOOL),
        ),
        "plan.csv",
        "status",
    ),
)


def _agree_with_files() -> None:
    for spec in _MAPS:
        columns = FILES.get(spec.extract_file)
        if columns is None or spec.extract_column not in columns:
            raise RuntimeError(
                f"{spec.file} names {spec.extract_file} column {spec.extract_column}, "
                "which is not in the extract contract."
            )
        keys = sum(rule is Rule.KEY for _name, rule in spec.columns)
        sorts = sum(rule is Rule.SORT for _name, rule in spec.columns)
        if keys != 1 or sorts > 1:
            raise RuntimeError(f"{spec.file} needs exactly one key column and at most one sort column.")


_agree_with_files()


@dataclass(frozen=True)
class _Ready:
    spec: _Spec
    rows: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class MapFault:
    fault: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class MapBatch:
    _maps: tuple[_Ready, ...]

    @property
    def files(self) -> tuple[str, ...]:
        return tuple(ready.spec.file for ready in self._maps)

    def replace(self, conn) -> tuple[list[str], list[str]]:
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier("ref")))
        pass_lines = []
        for ready in self._maps:
            spec = ready.spec
            schema = sql.Identifier("ref")
            table = sql.Identifier(spec.table)
            conn.execute(sql.SQL("DROP TABLE IF EXISTS {}.{}").format(schema, table))
            definitions = sql.SQL(", ").join(
                sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(_SQL[rule]))
                for name, rule in spec.columns
            )
            conn.execute(sql.SQL("CREATE TABLE {}.{} ({})").format(schema, table, definitions))
            if ready.rows:
                names = sql.SQL(", ").join(sql.Identifier(name) for name, _rule in spec.columns)
                places = sql.SQL(", ").join(sql.Placeholder() for _name in spec.columns)
                statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(schema, table, names, places)
                with conn.cursor() as cursor:
                    cursor.executemany(statement, ready.rows)
            count = len(ready.rows)
            noun = "row" if count == 1 else "rows"
            pass_lines.append(f"{spec.file}: pass, {count} {noun}.")
        notes = []
        for spec in _MAPS:
            count, first = conn.execute(_unknown_codes(spec)).fetchone()
            if count:
                noun = "row" if count == 1 else "rows"
                notes.append(
                    f"Warning: {spec.extract_file} column {spec.extract_column}: "
                    f"{count} {noun}, no map row (first line {first})."
                )
        return pass_lines, notes


def _unknown_codes(spec: _Spec):
    return sql.SQL(
        """
        SELECT count(*)::int, min(line)::int
        FROM (
            SELECT (row_number() OVER (ORDER BY ctid)) + 1 AS line, {code} AS code
            FROM {schema}.{table}
        ) src
        WHERE code IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM {ref}.{map_table} AS m
              WHERE m.{key} = src.code
          )
        """
    ).format(
        code=sql.Identifier(spec.extract_column),
        schema=sql.Identifier("ic"),
        table=sql.Identifier(spec.extract_file.removesuffix(".csv")),
        ref=sql.Identifier("ref"),
        map_table=sql.Identifier(spec.table),
        key=sql.Identifier(spec.key),
    )


def _cell(rule: Rule, text: str) -> tuple[object | None, tuple[str, ...]]:
    if text == "":
        return None, ("blank required cell",)
    if rule is Rule.KEY:
        return text, ()
    if rule is Rule.LABEL:
        problems = []
        if not 1 <= len(text) <= 80:
            problems.append("not 1 to 80 characters")
        if any(ord(char) < 32 or ord(char) == 127 for char in text):
            problems.append("contains a control character")
        if problems:
            return None, tuple(problems)
        return text, ()
    if rule is Rule.COUNTS_AS:
        if text not in _COUNTS_AS:
            return None, ("not one of " + ", ".join(_COUNTS_AS),)
        return text, ()
    if rule is Rule.PORTION:
        if _PORTION.fullmatch(text):
            return Decimal(text), ()
        return None, ("not a decimal from 0 through 1",)
    if rule is Rule.BOOL:
        if text == "true":
            return True, ()
        if text == "false":
            return False, ()
        return None, ("not true or false",)
    if rule is Rule.PLAN_TYPE:
        if text in _PLAN_TYPES:
            return text, ()
        return None, ("not 504 or IEP",)
    if rule is Rule.SORT:
        if _SORT.fullmatch(text):
            value = int(text)
            if _SORT_MIN <= value <= _SORT_MAX:
                return value, ()
        return None, ("not an integer",)
    raise RuntimeError(f"unknown map rule {rule}")


def _folder_problem(district: Path) -> str:
    if not district.exists():
        return "The folder is not on this machine."
    if not district.is_dir():
        return "That path is not a folder."
    try:
        for _entry in district.iterdir():
            pass
    except OSError:
        return "The server could not read the folder."
    return ""


def read_maps(district: Path, check_header) -> MapFault | MapBatch:
    message = _folder_problem(district)
    if message:
        return MapFault("server", (message,))
    problems: list[str] = []
    ready: list[_Ready] = []
    for spec in _MAPS:
        path = district / spec.file
        if not path.is_file():
            problems.append(f"{spec.file}: fail. The file is missing from the folder.")
            continue
        columns = tuple(name for name, _rule in spec.columns)
        reason, header = check_header(path, columns)
        if reason:
            problems.append(f"{spec.file}: fail. {reason}")
            continue
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
        except UnicodeDecodeError:
            problems.append(f"{spec.file}: fail. The file is not UTF-8.")
            continue
        except OSError:
            problems.append(f"{spec.file}: fail. The server could not read this file.")
            continue
        except csv.Error:
            problems.append(f"{spec.file}: fail. The file is not valid CSV.")
            continue
        seen_keys: set[str] = set()
        seen_sorts: set[int] = set()
        sort_name = next((name for name, rule in spec.columns if rule is Rule.SORT), None)
        parsed: list[tuple[object, ...]] = []
        for line_no, raw in enumerate(rows[1:], start=2):
            before = len(problems)
            if len(raw) != len(header):
                problems.append(f"{spec.file}: fail. Line {line_no}: row length does not match the header.")
                continue
            by_name = dict(zip(header, raw))
            values: list[object | None] = []
            key_value = None
            sort_value = None
            for column, rule in spec.columns:
                parsed_value, rule_texts = _cell(rule, by_name[column])
                for rule_text in rule_texts:
                    problems.append(f"{spec.file}: fail. Line {line_no}: {column}: {rule_text}.")
                if rule is Rule.KEY and isinstance(parsed_value, str):
                    key_value = parsed_value
                if rule is Rule.SORT and isinstance(parsed_value, int):
                    sort_value = parsed_value
                values.append(parsed_value)
            if key_value is not None:
                if key_value in seen_keys:
                    problems.append(f"{spec.file}: fail. Line {line_no}: {spec.key}: duplicate key.")
                seen_keys.add(key_value)
            if sort_value is not None and sort_name is not None:
                if sort_value in seen_sorts:
                    problems.append(f"{spec.file}: fail. Line {line_no}: {sort_name}: duplicate sort_order.")
                seen_sorts.add(sort_value)
            if len(problems) == before:
                parsed.append(tuple(values))
        ready.append(_Ready(spec, tuple(parsed)))
    if problems:
        return MapFault("extract", tuple(problems))
    return MapBatch(tuple(ready))
