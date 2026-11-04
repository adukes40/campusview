import csv
import os
from datetime import datetime
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from loader.contract import FILES
from loader.load import check_folder, load_drop, main, read_cutoff

PASSWORD = "throwaway"
EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "district"
EXTRACT_CUTOFF_DATE = read_cutoff(EXAMPLES)[0]


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
    assert "problem with the extract." in report
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
    for path in EXAMPLES.iterdir():
        if path.suffix == ".csv" or path.name == "settings":
            (district / path.name).write_bytes(path.read_bytes())
    return district


def test_cutoff_is_read_from_district_settings(tmp_path):
    assert EXTRACT_CUTOFF_DATE == "2025-07-01"
    assert read_cutoff(EXAMPLES) == ("2025-07-01", None)
    district = tmp_path / "plain"
    district.mkdir()
    assert read_cutoff(district)[1] == "The district config folder has no cutoff date."
    (district / "settings").write_text("cutoff_date=2025-07-01\nsftp_host=files.example.test\n")
    assert read_cutoff(district) == ("2025-07-01", None)
    (district / "settings").write_text("# kept\ncutoff_date=07/01/2025\n")
    assert read_cutoff(district)[1] == "The cutoff date is not YYYY-MM-DD."
    (district / "settings").write_text("cutoff_date=2026-13-45\n")
    assert read_cutoff(district)[1] == "The cutoff date is not YYYY-MM-DD."
    assert read_cutoff(tmp_path / "missing") == (None, None)


def test_maps_load_and_rerun(db, tmp_path):
    loadable(tmp_path)
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    counts = stored(
        """
        SELECT c.relname, (xpath('/row/c/text()', query_to_xml(
            format('SELECT count(*) AS c FROM ref.%I', c.relname), false, true, '')))[1]::text::int
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ref' AND c.relkind = 'r' ORDER BY 1
        """
    )
    assert counts == [
        ("map_attendance_codes", 2),
        ("map_behavior_types", 1),
        ("map_consequences", 1),
        ("map_genders", 1),
        ("map_grades", 2),
        ("map_locations", 1),
        ("map_plan_statuses", 1),
        ("map_plan_types", 2),
        ("map_race_groups", 1),
        ("map_referral_statuses", 1),
    ]
    assert "map_grades.csv: pass, 2 rows." in report
    grades = stored("SELECT grade_code, sort_order FROM ref.map_grades ORDER BY sort_order")
    ok, saved, _report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert stored("SELECT grade_code, sort_order FROM ref.map_grades ORDER BY sort_order") == grades
    assert stored("SELECT count(*) FROM ops.load_batch WHERE outcome = 'pass'") == [(2,)]


def test_missing_map_names_the_district_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    loadable(tmp_path)
    district = copy_district(tmp_path)
    (district / "map_genders.csv").unlink()
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and not saved
    assert "problem with the district config folder's map files." in report
    assert "map_genders.csv: fail. The file is missing from the folder." in report
    ok, saved, report = load_drop(tmp_path, tmp_path / "missing-district")
    assert not ok and not saved
    assert "problem with the district config folder." in report
    assert "The district config folder is not on this machine." in report


def test_bad_map_header(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    loadable(tmp_path)
    district = copy_district(tmp_path)
    (district / "map_grades.csv").write_text(
        "grade_code,label,sort_order,extraCol\nFAKE-K,School A kindergarten,0,PLANTED\n"
    )
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and not saved
    assert "map_grades.csv: fail. Unknown column extraCol." in report
    assert "PLANTED" not in report
    assert "district config folder's map files." in report


@pytest.mark.parametrize(
    ("filename", "body", "line", "hidden"),
    [
        (
            "map_attendance_codes.csv",
            "attendance_code,label,counts_as,absence_portion\nFAKE-P,School A present,LATE,0\n",
            "counts_as: not one of PRESENT, ABSENT_EXCUSED, ABSENT_UNEXCUSED, TARDY_EXCUSED, TARDY_UNEXCUSED, PARTIAL.",
            "LATE",
        ),
        (
            "map_consequences.csv",
            "consequence_code,label,is_exclusionary\nFAKE-C,School A detention,TRUE\n",
            "is_exclusionary: not true or false.",
            "TRUE",
        ),
        (
            "map_grades.csv",
            "grade_code,label,sort_order\nFAKE-K,School A kindergarten,1.0\n",
            "sort_order: not an integer.",
            "1.0",
        ),
        (
            "map_grades.csv",
            "grade_code,label,sort_order\nFAKE-K,School A kindergarten,2147483648\n",
            "sort_order: not an integer.",
            "2147483648",
        ),
    ],
)
def test_bad_map_cell(tmp_path, monkeypatch, filename, body, line, hidden):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    loadable(tmp_path)
    district = copy_district(tmp_path)
    (district / filename).write_text(body)
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and not saved
    assert f"{filename}: fail. Line 2: {line}" in report
    assert hidden not in report


def test_duplicate_map_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    loadable(tmp_path)
    district = copy_district(tmp_path)
    (district / "map_grades.csv").write_text(
        "grade_code,label,sort_order\nFAKE-K,School A kindergarten,0\nFAKE-K,School A grade,1\n"
    )
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and not saved
    assert "map_grades.csv: fail. Line 3: grade_code: duplicate key." in report
    assert "FAKE-K" not in report


def test_unknown_code_warns_for_codes_that_are_used(db, tmp_path):
    loadable(
        tmp_path,
        **{
            "attendance.csv": [cells("attendance.csv", attendanceID="1", excuseID="1", calendarID="1")],
            "attendance_excuse.csv": [
                cells("attendance_excuse.csv", excuseID="1", code="NOMAP-USED"),
                cells("attendance_excuse.csv", excuseID="9", code="NOMAP-UNUSED"),
            ],
            "enrollment.csv": [cells("enrollment.csv", enrollmentID="1", grade="NOMAP-GRD")],
        },
    )
    ok, saved, report = load_drop(tmp_path, EXAMPLES)
    assert ok and saved
    assert "Warning: attendance.csv excuse code: 1 row, no map row (first line 2)." in report
    assert "Warning: enrollment.csv column grade: 1 row, no map row (first line 2)." in report
    assert report.count("no map row") == 2
    assert "NOMAP-USED" not in report
    assert "NOMAP-UNUSED" not in report
    assert "NOMAP-GRD" not in report


def test_bad_map_keeps_previous_ref(db, tmp_path):
    loadable(tmp_path, **{"person.csv": [cells("person.csv", personID="1", stateID="001")]})
    district = copy_district(tmp_path)
    assert load_drop(tmp_path, district)[0]
    grades = stored("SELECT grade_code, sort_order FROM ref.map_grades ORDER BY sort_order")
    text = (district / "map_grades.csv").read_text()
    (district / "map_grades.csv").write_text(text.replace(",0\n", ",NOPE\n", 1))
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and saved
    assert "sort_order: not an integer." in report
    assert "NOPE" not in report
    assert "Nothing was loaded." in report
    assert stored("SELECT grade_code, sort_order FROM ref.map_grades ORDER BY sort_order") == grades
    assert stored('SELECT "stateID" FROM ic.person') == [("001",)]
    assert stored("SELECT outcome, fault FROM ops.load_batch ORDER BY batch_id DESC LIMIT 1") == [("fail", "extract")]


def test_missing_cutoff_is_extract(db, tmp_path):
    loadable(tmp_path)
    district = copy_district(tmp_path)
    (district / "settings").write_text("sftp_host=files.example.test\n")
    ok, saved, report = load_drop(tmp_path, district)
    assert not ok and saved
    assert "has no cutoff date." in report
    assert stored("SELECT outcome, fault FROM ops.load_batch") == [("fail", "extract")]


def test_reader_cannot_see_ref_or_ic(db, tmp_path):
    loadable(tmp_path)
    assert load_drop(tmp_path, EXAMPLES)[0]
    reader = f"cv_reader_{os.getpid()}"
    admin = psycopg.connect(
        user=os.environ.get("USER", "postgres"), dbname="postgres", host="/var/run/postgresql", autocommit=True
    )
    admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(reader)))
    admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(reader), sql.Literal(PASSWORD)))
    admin.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(os.environ["CV_PG_DATABASE"]), sql.Identifier(reader)
        )
    )
    try:
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
        admin.execute(
            sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(
                sql.Identifier(os.environ["CV_PG_DATABASE"]), sql.Identifier(reader)
            )
        )
        admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(reader)))
        admin.close()


def test_usage_needs_both_paths(capsys):
    assert main(["loader"]) == 2
    assert main(["loader", "drop"]) == 2
    assert capsys.readouterr().err == "Usage: python -m loader FOLDER DISTRICT\n" * 2

