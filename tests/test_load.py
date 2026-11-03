import csv
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from loader.contract import FILES
from loader.load import EXTRACT_CUTOFF_DATE, check_folder, check_header, load_drop, main
from loader.maps import MapBatch, MapFault, read_maps

PASSWORD = "throwaway"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "district"


def write_csv(path: Path, header, rows, newline="\n") -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator=newline)
        writer.writerow(header)
        writer.writerows(rows)


def fill(folder: Path, **extra) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, columns in FILES.items():
        write_csv(folder / name, columns, extra.get(name, []))


def cells(filename: str, **values) -> list[str]:
    return [values.get(column, "") for column in FILES[filename]]


def loadable(folder: Path, **extra) -> None:
    rows = {
        "school.csv": [cells("school.csv", schoolID="1", name="School A")],
        "calendar.csv": [cells("calendar.csv", calendarID="1", schoolID="1", endYear="2026")],
    }
    rows.update(extra)
    fill(folder, **rows)


@pytest.fixture
def db(monkeypatch):
    role = f"cv_loader_{os.getpid()}"
    name = f"{role}_db"
    try:
        admin = psycopg.connect(user=os.environ.get("USER", "postgres"), dbname="postgres", host="/var/run/postgresql", autocommit=True)
    except psycopg.Error:
        pytest.skip("cannot create a throwaway database")
    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
    try:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(PASSWORD)))
        admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(name), sql.Identifier(role)))
    except psycopg.Error:
        admin.close()
        pytest.skip("cannot create a throwaway database")
    monkeypatch.setenv("CV_OWNER_DB_PASSWORD", PASSWORD)
    monkeypatch.setenv("CV_PG_USER", role)
    monkeypatch.setenv("CV_PG_DATABASE", name)
    assert name != "campusview_data"
    try:
        yield
    finally:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        admin.close()


def stored(query: str):
    with psycopg.connect(
        host="127.0.0.1",
        port=os.environ.get("CV_PG_PORT", "5432"),
        dbname=os.environ["CV_PG_DATABASE"],
        user=os.environ["CV_PG_USER"],
        password=os.environ["CV_OWNER_DB_PASSWORD"],
    ) as conn:
        assert conn.info.dbname != "campusview_data"
        return conn.execute(query).fetchall()


def test_text_blanks_quotes_and_cutoff(db, tmp_path):
    person_header = list(reversed(FILES["person.csv"]))
    fill(
        tmp_path,
        **{
            "enrollment.csv": [
                cells("enrollment.csv", enrollmentID="1", personID="1", calendarID="104", endDate="2017-06-01"),
                cells("enrollment.csv", enrollmentID="6", personID="1", calendarID="226", startDate="2023-08-01"),
                cells("enrollment.csv", enrollmentID="2", personID="1", calendarID="20", endDate="2029-06-01"),
                cells("enrollment.csv", enrollmentID="3", personID="1", calendarID="3", endDate="2025-06-30"),
                cells("enrollment.csv", enrollmentID="4", personID="1", calendarID="245", startDate="2025-08-01"),
                cells("enrollment.csv", enrollmentID="5", personID="1", calendarID="1", endDate=EXTRACT_CUTOFF_DATE),
            ],
            "day.csv": [cells("day.csv", calendarID="1", date="2026-01-05")],
            "school.csv": [cells("school.csv", schoolID="1", name="School A, North", address='say "hi"')],
            "calendar.csv": [cells("calendar.csv", calendarID="9", schoolID="1", endYear="2026")],
        },
    )
    quoted = {"currentIdentityID": '""', "personID": "1", "stateID": "001", "studentNumber": "STU-001"}
    person_line = ",".join(quoted.get(column, "") for column in person_header)
    (tmp_path / "person.csv").write_text(",".join(person_header) + "\n" + person_line + "\n")
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert stored('SELECT "stateID", "currentIdentityID" FROM raw.person') == [("001", None)]
    assert stored("SELECT name, address FROM raw.school") == [("School A, North", 'say "hi"')]
    assert stored("SELECT name, address FROM ic.school") == [("School A, North", 'say "hi"')]
    assert stored('SELECT "stateID" FROM ic.person') == [("001",)]
    assert stored('SELECT "endYear" FROM ic.calendar') == [(2026,)]
    assert "Warning: calendar 20 has enrollments and no Day rows." in report
    assert "Warning: calendar 245 has enrollments and no Day rows." in report
    assert report.index("calendar 20") < report.index("calendar 245")
    assert "calendar 104" not in report
    assert "calendar 226" not in report
    assert "calendar 3 " not in report
    assert "calendar 1 " not in report


def test_bad_headers(tmp_path):
    fill(tmp_path)
    enrollment = tmp_path / "enrollment.csv"
    text = enrollment.read_text()
    enrollment.write_text(text.replace("enrollmentID", "enrollmentID,extraCol", 1))
    assert "Unknown column extraCol." in "\n".join(check_folder(tmp_path)[1])

    fill(tmp_path)
    person = tmp_path / "person.csv"
    person.write_text(person.read_text().replace("personID", "personId", 1))
    lines = "\n".join(check_folder(tmp_path)[1])
    assert "Unknown column personId." in lines
    assert "Missing column personID." in lines

    fill(tmp_path)
    columns = FILES["person.csv"][:-1]
    write_csv(tmp_path / "person.csv", columns, [])
    assert "Missing column staffstateID." in "\n".join(check_folder(tmp_path)[1])


def test_missing_file(tmp_path):
    fill(tmp_path)
    (tmp_path / "day.csv").unlink()
    fault, lines, _ready = check_folder(tmp_path)
    assert fault == "extract"
    assert lines == [
        "calendar.csv: fail. The file has no data rows.",
        "day.csv: fail. The file is missing from the folder.",
        "school.csv: fail. The file has no data rows.",
    ]


def test_bad_file_keeps_previous_rows(db, tmp_path):
    loadable(tmp_path, **{"person.csv": [cells("person.csv", personID="1", stateID="001")]})
    assert load_drop(tmp_path, EXAMPLES)[0]
    person = tmp_path / "person.csv"
    person.write_text(person.read_text().replace("personID", "personId", 1))
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert not ok and saved
    assert "person.csv: fail. Unknown column personId." in report
    assert "att_day_aggregation.csv" not in report
    assert stored('SELECT "stateID" FROM raw.person') == [("001",)]
    assert stored('SELECT "stateID" FROM ic.person') == [("001",)]
    header = ",".join(FILES["person.csv"])
    (tmp_path / "person.csv").write_text(header + "\n1,,001,,,,NOT-A-CELL\n")
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert not ok and saved
    assert "person.csv: fail. Line 2:" in report
    assert "NOT-A-CELL" not in report
    assert stored('SELECT "stateID" FROM raw.person') == [("001",)]
    assert stored('SELECT "stateID" FROM ic.person') == [("001",)]


def test_zero_byte_file_is_not_also_empty(tmp_path):
    fill(tmp_path)
    (tmp_path / "school.csv").write_bytes(b"")
    lines = "\n".join(check_folder(tmp_path)[1])
    assert "school.csv: fail. The file has no header row." in lines
    assert "school.csv: fail. The file has no data rows." not in lines


def test_empty_calendar_keeps_previous_person(db, tmp_path):
    loadable(tmp_path, **{"person.csv": [cells("person.csv", personID="1", stateID="001")]})
    assert load_drop(tmp_path, EXAMPLES)[0]
    write_csv(tmp_path / "calendar.csv", FILES["calendar.csv"], [])
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert not ok and saved
    assert "calendar.csv: fail. The file has no data rows." in report
    assert "Nothing was loaded." in report
    assert stored('SELECT "stateID" FROM raw.person') == [("001",)]
    assert stored('SELECT "stateID" FROM ic.person') == [("001",)]


def test_header_only_day_warns(db, tmp_path):
    loadable(tmp_path)
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "day.csv: pass, 0 rows." in report
    assert "map_grades.csv: pass, 2 rows." in report
    assert "Warning: day.csv has no data rows." in report
    assert stored("SELECT count(*) FROM ic.day") == [(0,)]


def test_full_timestamp_and_bad_date(db, tmp_path):
    loadable(
        tmp_path,
        **{
            "day.csv": [
                cells("day.csv", calendarID="1", date="2015-02-30"),
                cells("day.csv", calendarID="1", date="2025-08-26 00:00:00.000"),
            ],
            "period.csv": [cells("period.csv", periodID="1", startTime="1900-01-01 07:30:00.000")],
        },
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "Warning: day.csv column date: 1 row, bad timestamp (first line 2)." in report
    assert "2015-02-30" not in report
    assert "column startTime" not in report
    assert stored("SELECT date FROM ic.day ORDER BY ctid") == [(None,), (datetime(2025, 8, 26),)]
    assert stored('SELECT "startTime" FROM ic.period') == [(datetime(1900, 1, 1, 7, 30),)]


def _enroll(enrollment_id, grade):
    return cells(
        "enrollment.csv",
        enrollmentID=enrollment_id,
        personID="P1",
        calendarID="1",
        endYear="2026",
        grade=grade,
        startDate="2026-08-01 00:00:00.000",
    )


def test_two_grades(db, tmp_path):
    loadable(tmp_path, **{"enrollment.csv": [_enroll("1", "01"), _enroll("2", "1")]})
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert stored("SELECT grade FROM ic.enrollment ORDER BY grade") == [("01",), ("1",)]
    assert "Warning: enrollment.csv: 2 rows, two grades for the same student, school, and year." in report
    assert "P1" not in report
    write_csv(tmp_path / "enrollment.csv", FILES["enrollment.csv"], [_enroll("1", "01"), _enroll("2", "01")])
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "two grades" not in report


def test_action_date_before_incident(db, tmp_path):
    loadable(
        tmp_path,
        **{
            "behavior_incident.csv": [cells("behavior_incident.csv", incidentID="1", timestamp="2026-01-02 09:00:00.000")],
            "behavior_event.csv": [cells("behavior_event.csv", eventID="1", incidentID="1")],
            "behavior_role.csv": [cells("behavior_role.csv", roleID="1", eventID="1", personID="2")],
            "behavior_resolution.csv": [
                cells("behavior_resolution.csv", resolutionID="1", roleID="1", discassignDate="2026-01-01 00:00:00.000")
            ],
        },
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "Warning: behavior_resolution.csv: 1 row, action date before the incident was entered." in report
    write_csv(
        tmp_path / "behavior_resolution.csv",
        FILES["behavior_resolution.csv"],
        [cells("behavior_resolution.csv", resolutionID="1", roleID="1", discassignDate="2026-01-02 08:00:00.000")],
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "action date before the incident was entered" not in report


def test_attendance_outside_enrollment(db, tmp_path):
    loadable(
        tmp_path,
        **{
            "enrollment.csv": [_enroll("1", "4")],
            "attendance.csv": [cells("attendance.csv", attendanceID="1", personID="P1", calendarID="1", date="2026-07-15 00:00:00.000")],
        },
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert stored('SELECT "date" FROM ic.attendance') == [(datetime(2026, 7, 15),)]
    assert "Warning: attendance.csv: 1 row, attendance outside enrollment." in report
    assert "2026-07-15" not in report
    write_csv(
        tmp_path / "attendance.csv",
        FILES["attendance.csv"],
        [cells("attendance.csv", attendanceID="1", personID="P1", calendarID="1", date="2026-08-01 00:00:00.000")],
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "attendance outside enrollment" not in report


def test_bad_cells_warn_without_values(db, tmp_path):
    loadable(
        tmp_path,
        **{
            "school.csv": [
                cells("school.csv", schoolID="bad id", name="School A\nNorth", exclude="nope"),
                cells("school.csv", name="School A", exclude="true"),
            ],
            "calendar.csv": [cells("calendar.csv", calendarID="1", schoolID="1", endYear="2025-2026")],
        },
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert stored('SELECT "schoolID", name, exclude FROM ic.school ORDER BY exclude NULLS LAST') == [
        (None, "School A", True),
        (None, None, None),
    ]
    assert stored('SELECT "endYear" FROM ic.calendar') == [(None,)]
    assert "odd id characters" in report
    assert "control character" in report
    assert "bad boolean" in report
    assert "blank required field" in report
    assert "bad school year" in report
    for hidden in ("bad id", "North", "nope", "2025-2026"):
        assert hidden not in report


def copy_district(tmp_path: Path) -> Path:
    district = tmp_path / "district"
    district.mkdir()
    for path in EXAMPLES.glob("*.csv"):
        (district / path.name).write_bytes(path.read_bytes())
    return district


def read_planted(tmp_path: Path, filename: str, text: str):
    district = copy_district(tmp_path)
    (district / filename).write_text(text)
    return read_maps(district, check_header)


_LONG_LABEL = "A" * 81
_BOTH_LABEL = "A" * 80 + "\n"
_SORT_RULE = ("map_grades.csv: fail. Line 2: sort_order: not an integer.",)
_PORTION_RULE = (
    "map_attendance_codes.csv: fail. Line 2: absence_portion: not a decimal from 0 through 1.",
)


def _grades(cell: str) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    return (
        "map_grades.csv",
        f"grade_code,label,sort_order\nFAKE-K,School A kindergarten,{cell}\n",
        _SORT_RULE,
        (cell,),
    )


def _portion(cell: str) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    return (
        "map_attendance_codes.csv",
        f"attendance_code,label,counts_as,absence_portion\nFAKE-P,School A present,PRESENT,{cell}\n",
        _PORTION_RULE,
        (cell,),
    )


@pytest.mark.parametrize(
    ("filename", "body", "lines", "hidden"),
    [
        (
            "map_attendance_codes.csv",
            "attendance_code,label,counts_as,absence_portion\nFAKE-P,School A present,,0\n",
            ("map_attendance_codes.csv: fail. Line 2: counts_as: blank required cell.",),
            (),
        ),
        (
            "map_attendance_codes.csv",
            "attendance_code,label,counts_as,absence_portion\nFAKE-P,School A present,LATE,0\n",
            (
                "map_attendance_codes.csv: fail. Line 2: counts_as: "
                "not one of PRESENT, ABSENT_EXCUSED, ABSENT_UNEXCUSED, TARDY_EXCUSED, TARDY_UNEXCUSED, PARTIAL.",
            ),
            ("LATE",),
        ),
        (
            "map_attendance_codes.csv",
            "attendance_code,label,counts_as,absence_portion\nFAKE-P,School A present, PRESENT,0\n",
            (
                "map_attendance_codes.csv: fail. Line 2: counts_as: "
                "not one of PRESENT, ABSENT_EXCUSED, ABSENT_UNEXCUSED, TARDY_EXCUSED, TARDY_UNEXCUSED, PARTIAL.",
            ),
            (),
        ),
        _portion(".5"),
        _portion("00.5"),
        _portion("1.2"),
        _portion("+1"),
        _portion("1e-1"),
        (
            "map_consequences.csv",
            "consequence_code,label,is_exclusionary\nFAKE-C,School A detention,TRUE\n",
            ("map_consequences.csv: fail. Line 2: is_exclusionary: not true or false.",),
            ("TRUE",),
        ),
        (
            "map_plan_types.csv",
            "plan_type_code,plan_type,label\nFAKE-504,iep,School A 504\n",
            ("map_plan_types.csv: fail. Line 2: plan_type: not 504 or IEP.",),
            ("iep",),
        ),
        _grades("01"),
        _grades("+1"),
        _grades("1.0"),
        _grades("-0"),
        _grades("2147483648"),
        _grades("-2147483649"),
        (
            "map_grades.csv",
            f"grade_code,label,sort_order\nFAKE-K,{_LONG_LABEL},0\n",
            ("map_grades.csv: fail. Line 2: label: not 1 to 80 characters.",),
            (_LONG_LABEL,),
        ),
        (
            "map_grades.csv",
            "grade_code,label,sort_order\nFAKE-K,School\tA,0\n",
            ("map_grades.csv: fail. Line 2: label: contains a control character.",),
            ("School\tA",),
        ),
        (
            "map_grades.csv",
            'grade_code,label,sort_order\nFAKE-K,"' + _BOTH_LABEL + '",0\n',
            (
                "map_grades.csv: fail. Line 2: label: not 1 to 80 characters.",
                "map_grades.csv: fail. Line 2: label: contains a control character.",
            ),
            ("A" * 80,),
        ),
        (
            "map_grades.csv",
            "grade_code,label,sort_order\n"
            "FAKE-K,School A kindergarten,0\n"
            "FAKE-K,School A grade,1\n",
            ("map_grades.csv: fail. Line 3: grade_code: duplicate key.",),
            ("FAKE-K",),
        ),
        (
            "map_grades.csv",
            "grade_code,label,sort_order\n"
            "FAKE-K,School A kindergarten,0\n"
            "FAKE-1,School A grade,0\n",
            ("map_grades.csv: fail. Line 3: sort_order: duplicate sort_order.",),
            ("FAKE-1",),
        ),
        (
            "map_grades.csv",
            "grade_code,label,sort_order\nFAKE-K,School A kindergarten,0,\n",
            ("map_grades.csv: fail. Line 2: row length does not match the header.",),
            ("FAKE-K",),
        ),
    ],
)
def test_bad_map_cell_names_the_rule(tmp_path, filename, body, lines, hidden):
    found = read_planted(tmp_path, filename, body)
    assert isinstance(found, MapFault)
    assert found.fault == "extract"
    assert found.lines == lines
    report = "\n".join(found.lines)
    for value in hidden:
        assert value not in report


def test_bad_map_header_uses_check_header(tmp_path):
    district = copy_district(tmp_path)
    path = district / "map_grades.csv"
    path.write_text("grade_code,label,sort_order,extraCol\nFAKE-K,School A kindergarten,0,PLANTED\n")
    reason, _header = check_header(path, ("grade_code", "label", "sort_order"))
    found = read_maps(district, check_header)
    assert isinstance(found, MapFault)
    assert found.fault == "extract"
    assert found.lines == (f"map_grades.csv: fail. {reason}",)
    assert "PLANTED" not in found.lines[0]


def test_missing_map_file(tmp_path):
    district = copy_district(tmp_path)
    (district / "map_genders.csv").unlink()
    found = read_maps(district, check_header)
    assert isinstance(found, MapFault)
    assert found.lines == ("map_genders.csv: fail. The file is missing from the folder.",)


def test_every_map_is_checked(tmp_path):
    district = copy_district(tmp_path)
    (district / "map_genders.csv").unlink()
    (district / "map_grades.csv").write_text("grade_code,label,sort_order\nFAKE-K,School A kindergarten,01\n")
    found = read_maps(district, check_header)
    assert isinstance(found, MapFault)
    assert found.lines == (
        "map_genders.csv: fail. The file is missing from the folder.",
        "map_grades.csv: fail. Line 2: sort_order: not an integer.",
    )
    assert "01" not in "\n".join(found.lines)


def test_district_path_uses_the_extract_folder_sentences(tmp_path):
    missing = tmp_path / "missing"
    not_dir = tmp_path / "notes.txt"
    not_dir.write_text("x\n")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        for path in (missing, not_dir, locked):
            found = read_maps(path, check_header)
            assert isinstance(found, MapFault)
            assert found.fault == "server"
            assert found.lines == tuple(check_folder(path)[1])
    finally:
        locked.chmod(0o755)


def test_bad_utf8_map_uses_check_header_sentence(tmp_path):
    district = copy_district(tmp_path)
    (district / "map_grades.csv").write_bytes(b"grade_code,label,sort_order\n\xff,School A,0\n")
    probe = tmp_path / "probe.csv"
    probe.write_bytes(b"\xff\n")
    reason, _header = check_header(probe, ("grade_code",))
    found = read_maps(district, check_header)
    assert isinstance(found, MapFault)
    assert found.lines == (f"map_grades.csv: fail. {reason}",)


def test_invalid_csv_names_the_file_not_the_cell(tmp_path):
    district = copy_district(tmp_path)
    token = "Q" * 40
    (district / "map_grades.csv").write_text(
        "grade_code,label,sort_order\n" + token + ",School A kindergarten,0\n"
    )
    limit = csv.field_size_limit(30)
    try:
        found = read_maps(district, check_header)
    finally:
        csv.field_size_limit(limit)
    assert isinstance(found, MapFault)
    assert found.lines == ("map_grades.csv: fail. The file is not valid CSV.",)
    assert token not in found.lines[0]


def test_shuffled_map_header_is_accepted(tmp_path):
    district = copy_district(tmp_path)
    (district / "map_grades.csv").write_text(
        "sort_order,label,grade_code\n0,School A kindergarten,FAKE-K\n1,School A grade,FAKE-1\n"
    )
    found = read_maps(district, check_header)
    assert isinstance(found, MapBatch)
    assert "map_grades.csv" in found.files


def test_header_only_map_is_accepted(tmp_path):
    district = copy_district(tmp_path)
    header = (district / "map_plan_statuses.csv").read_text().splitlines()[0]
    (district / "map_plan_statuses.csv").write_text(header + "\n")
    found = read_maps(district, check_header)
    assert isinstance(found, MapBatch)
    assert "map_plan_statuses.csv" in found.files


def test_edge_map_values_are_accepted(tmp_path):
    district = copy_district(tmp_path)
    (district / "map_attendance_codes.csv").write_text(
        "attendance_code,label,counts_as,absence_portion\n"
        "FAKE-P,School A present,PRESENT,0.5\n"
        "FAKE-A,School A absent,ABSENT_UNEXCUSED,1.00\n"
        "FAKE-T,School A tardy,TARDY_EXCUSED,0\n"
        "FAKE-U,School A unexcused,TARDY_UNEXCUSED,1.0\n"
        "FAKE-E,School A excused,ABSENT_EXCUSED,1\n"
        "FAKE-H,School A half,PARTIAL,0.25\n"
    )
    (district / "map_grades.csv").write_text(
        "grade_code,label,sort_order\n"
        f"FAKE-K,{'A' * 80},-2147483648\n"
        "FAKE-1,School A grade,2147483647\n"
        "FAKE-N,School A negative,-3\n"
    )
    found = read_maps(district, check_header)
    assert isinstance(found, MapBatch)


def test_example_filenames_match_the_batch():
    found = read_maps(EXAMPLES, check_header)
    assert isinstance(found, MapBatch)
    names = {path.name for path in EXAMPLES.glob("*.csv")}
    assert names == set(found.files)
    assert len(found.files) == len(names)


def test_extra_district_csv_is_ignored(tmp_path):
    district = copy_district(tmp_path)
    (district / "notes.csv").write_text("hello,there\nX,Y\n")
    found = read_maps(district, check_header)
    assert isinstance(found, MapBatch)
    assert "notes.csv" not in found.files


def test_map_csv_in_the_drop_is_rejected(tmp_path):
    loadable(tmp_path)
    write_csv(
        tmp_path / "map_grades.csv",
        ["grade_code", "label", "sort_order"],
        [["FAKE-K", "School A kindergarten", "0"]],
    )
    fault, lines, _ready = check_folder(tmp_path)
    assert fault == "extract"
    assert lines == ["map_grades.csv: fail. This file is not in the extract contract."]


def test_main_requires_the_drop_and_the_district(capsys):
    assert main(["loader"]) == 2
    assert main(["loader", "drop"]) == 2
    assert main(["loader", "drop", "district", "extra"]) == 2
    assert capsys.readouterr().err == "Usage: python -m loader FOLDER DISTRICT\n" * 3


def test_bad_sort_order_names_the_rule(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    loadable(tmp_path)
    district = copy_district(tmp_path)
    text = (district / "map_grades.csv").read_text()
    (district / "map_grades.csv").write_text(text.replace(",0\n", ",01\n", 1))
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and not saved
    assert "map_grades.csv: fail. Line 2: sort_order: not an integer." in report
    assert "01" not in report
    assert "Nothing was loaded." in report


def test_extract_and_server_faults_merge(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    loadable(tmp_path)
    (tmp_path / "day.csv").unlink()
    ok, saved, report = load_drop(tmp_path, tmp_path / "missing-district")
    assert not ok and not saved
    assert "day.csv: fail. The file is missing from the folder." in report
    assert "The folder is not on this machine." in report
    assert "problem with the server." in report
    assert "Nothing was loaded." in report


def _ref_snapshot():
    found = read_maps(EXAMPLES, check_header)
    assert isinstance(found, MapBatch)
    return {
        name: stored(
            sql.SQL("SELECT * FROM ref.{} ORDER BY 1").format(sql.Identifier(name.removesuffix(".csv")))
        )
        for name in found.files
    }


def test_rerun_replaces_ref_rows(db, tmp_path):
    loadable(tmp_path)
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    first = _ref_snapshot()
    assert first["map_grades.csv"] == [
        ("FAKE-1", "School A grade", 1),
        ("FAKE-K", "School A kindergarten", 0),
    ]
    assert first["map_attendance_codes.csv"] == [
        ("FAKE-A", "School A absent", "ABSENT_UNEXCUSED", Decimal("1")),
        ("FAKE-P", "School A present", "PRESENT", Decimal("0")),
    ]
    assert first["map_consequences.csv"] == [("FAKE-C", "School A detention", False)]
    assert first["map_plan_statuses.csv"] == [("FAKE-ON", True)]
    assert first["map_referral_statuses.csv"] == [("FAKE-S", "School A status", True, False, False)]
    for name in first:
        assert f"{name}: pass," in report
    ok, saved, _report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert _ref_snapshot() == first

    district = copy_district(tmp_path)
    (district / "map_grades.csv").write_text("grade_code,label,sort_order\nFAKE-K,School A kindergarten,0\n")
    ok, saved, report = load_drop(tmp_path, district)
    assert ok and saved
    assert "map_grades.csv: pass, 1 row." in report
    assert stored("SELECT grade_code, label, sort_order FROM ref.map_grades ORDER BY grade_code") == [
        ("FAKE-K", "School A kindergarten", 0),
    ]
    assert _ref_snapshot()["map_consequences.csv"] == first["map_consequences.csv"]


def test_header_only_map_loads_zero_rows(db, tmp_path):
    loadable(tmp_path)
    district = copy_district(tmp_path)
    header = (district / "map_plan_statuses.csv").read_text().splitlines()[0]
    (district / "map_plan_statuses.csv").write_text(header + "\n")
    ok, saved, report = load_drop(tmp_path, district)
    assert ok and saved
    assert "map_plan_statuses.csv: pass, 0 rows." in report
    assert stored("SELECT count(*) FROM ref.map_plan_statuses") == [(0,)]
    assert stored("SELECT count(*) FROM ref.map_grades") == [(2,)]


def test_shuffled_header_stores_spec_order(db, tmp_path):
    loadable(tmp_path)
    district = copy_district(tmp_path)
    (district / "map_grades.csv").write_text(
        "sort_order,label,grade_code\n0,School A kindergarten,FAKE-K\n1,School A grade,FAKE-1\n"
    )
    ok, saved, _report = load_drop(tmp_path, district)
    assert ok and saved
    assert stored("SELECT grade_code, label, sort_order FROM ref.map_grades ORDER BY sort_order") == [
        ("FAKE-K", "School A kindergarten", 0),
        ("FAKE-1", "School A grade", 1),
    ]


def test_bad_map_keeps_previous_snapshot(db, tmp_path):
    loadable(tmp_path, **{"person.csv": [cells("person.csv", personID="1", stateID="001")]})
    district = copy_district(tmp_path)
    ok, saved, _report = load_drop(tmp_path, district)
    assert ok and saved
    grades = stored("SELECT grade_code, label, sort_order FROM ref.map_grades ORDER BY sort_order")
    text = (district / "map_grades.csv").read_text()
    (district / "map_grades.csv").write_text(text.replace(",0\n", ",01\n", 1))
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and saved
    assert "map_grades.csv: fail. Line 2: sort_order: not an integer." in report
    assert "01" not in report
    assert "Nothing was loaded." in report
    assert stored("SELECT grade_code, label, sort_order FROM ref.map_grades ORDER BY sort_order") == grades
    assert stored('SELECT "stateID" FROM raw.person') == [("001",)]
    assert stored('SELECT "stateID" FROM ic.person') == [("001",)]


def test_unknown_codes_warn_without_the_planted_text(db, tmp_path):
    planted = {
        "attendance": "NOMAP-ATT",
        "behavior": "NOMAP-BEH",
        "location": "NOMAP-LOC",
        "consequence": "NOMAP-CON",
        "gender": "NOMAP-GEN",
        "grade": "NOMAP-GRD",
        "race": "NOMAP-RACE",
        "status": "NOMAP-STA",
        "plan_type": "NOMAP-TYPE",
        "plan": "NOMAP-PLAN",
    }
    loadable(
        tmp_path,
        **{
            "attendance_excuse.csv": [cells("attendance_excuse.csv", excuseID="1", code=planted["attendance"])],
            "behavior_type.csv": [cells("behavior_type.csv", typeID="1", code=planted["behavior"])],
            "behavior_incident.csv": [
                cells(
                    "behavior_incident.csv",
                    incidentID="1",
                    location=planted["location"],
                    status=planted["status"],
                ),
                cells("behavior_incident.csv", incidentID="2"),
            ],
            "behavior_res_type.csv": [cells("behavior_res_type.csv", typeID="1", code=planted["consequence"])],
            "identity.csv": [
                cells("identity.csv", identityID="1", gender=planted["gender"]),
                cells("identity.csv", identityID="2"),
            ],
            "enrollment.csv": [cells("enrollment.csv", enrollmentID="1", grade=planted["grade"])],
            "race_ethnicity.csv": [cells("race_ethnicity.csv", raceId="1", code=planted["race"])],
            "plan_type.csv": [cells("plan_type.csv", typeID="1", type=planted["plan_type"])],
            "plan.csv": [cells("plan.csv", planID="1", status=planted["plan"])],
        },
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    expected = (
        "Warning: attendance_excuse.csv column code: 1 row, no map row (first line 2).",
        "Warning: behavior_type.csv column code: 1 row, no map row (first line 2).",
        "Warning: behavior_incident.csv column location: 1 row, no map row (first line 2).",
        "Warning: behavior_res_type.csv column code: 1 row, no map row (first line 2).",
        "Warning: identity.csv column gender: 1 row, no map row (first line 2).",
        "Warning: enrollment.csv column grade: 1 row, no map row (first line 2).",
        "Warning: race_ethnicity.csv column code: 1 row, no map row (first line 2).",
        "Warning: behavior_incident.csv column status: 1 row, no map row (first line 2).",
        "Warning: plan_type.csv column type: 1 row, no map row (first line 2).",
        "Warning: plan.csv column status: 1 row, no map row (first line 2).",
    )
    assert report.count("no map row") == len(expected)
    positions = [report.index(line) for line in expected]
    assert positions == sorted(positions)
    for token in planted.values():
        assert token not in report
    assert stored('SELECT gender FROM ic.identity ORDER BY "identityID"') == [(planted["gender"],), (None,)]


def test_connect_only_cannot_read_ref_or_ic(db, tmp_path):
    loadable(tmp_path)
    ok, saved, _report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    reader = f"cv_reader_{os.getpid()}"
    admin = psycopg.connect(
        user=os.environ.get("USER", "postgres"),
        dbname="postgres",
        host="/var/run/postgresql",
        autocommit=True,
    )
    created = False
    try:
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(reader)))
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(reader), sql.Literal(PASSWORD))
        )
        created = True
        admin.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(os.environ["CV_PG_DATABASE"]),
                sql.Identifier(reader),
            )
        )
        conn = psycopg.connect(
            host="127.0.0.1",
            port=os.environ.get("CV_PG_PORT", "5432"),
            dbname=os.environ["CV_PG_DATABASE"],
            user=reader,
            password=PASSWORD,
            autocommit=True,
        )
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT 1 FROM ref.map_grades")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT 1 FROM ic.school")
        finally:
            conn.close()
    finally:
        if created:
            admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(reader)))
            admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(reader)))
        admin.close()


