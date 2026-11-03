import csv
import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from loader.contract import FILES
from loader.load import EXTRACT_CUTOFF_DATE, check_folder, load_drop

PASSWORD = "throwaway"


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
        },
    )
    quoted = {"currentIdentityID": '""', "personID": "1", "stateID": "001", "studentNumber": "STU-001"}
    person_line = ",".join(quoted.get(column, "") for column in person_header)
    (tmp_path / "person.csv").write_text(",".join(person_header) + "\n" + person_line + "\n")
    ok, saved, report = load_drop(tmp_path)
    assert ok and saved
    assert stored('SELECT "stateID", "currentIdentityID" FROM raw.person') == [("001", None)]
    assert stored("SELECT name, address FROM raw.school") == [("School A, North", 'say "hi"')]
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
    assert lines == ["day.csv: fail. The file is missing from the folder."]


def test_bad_file_keeps_previous_rows(db, tmp_path):
    fill(tmp_path, **{"person.csv": [cells("person.csv", personID="1", stateID="001")]})
    assert load_drop(tmp_path)[0]
    person = tmp_path / "person.csv"
    person.write_text(person.read_text().replace("personID", "personId", 1))
    ok, saved, report = load_drop(tmp_path)
    assert not ok and saved
    assert "person.csv: fail. Unknown column personId." in report
    assert "att_day_aggregation.csv" not in report
    assert stored('SELECT "stateID" FROM raw.person') == [("001",)]
    header = ",".join(FILES["person.csv"])
    (tmp_path / "person.csv").write_text(header + "\n1,,001,,,,NOT-A-CELL\n")
    ok, saved, report = load_drop(tmp_path)
    assert not ok and saved
    assert "person.csv: fail. Line 2:" in report
    assert "NOT-A-CELL" not in report
    assert stored('SELECT "stateID" FROM raw.person') == [("001",)]
