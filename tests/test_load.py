import os
from pathlib import Path

import psycopg
import pytest

from loader.contract import FILES
from loader.load import inspect_drop, load_drop

TOKEN = "NOT-A-CELL"


def field(value: str) -> str:
    if "," in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def write_drop(folder: Path, rows=None, *, omit=(), extra=()) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    rows = rows or {}
    for name, columns in FILES.items():
        if name in omit:
            continue
        lines = [",".join(columns)]
        for values in rows.get(name, []):
            lines.append(",".join(field(value) for value in values))
        (folder / name).write_bytes(("\r\n".join(lines) + "\r\n").encode())
    for name, content in extra:
        (folder / name).write_bytes(content)


def cells(filename: str, **values: str) -> list[str]:
    return [values.get(column, "") for column in FILES[filename]]


def test_keeps_text_and_blanks(tmp_path):
    write_drop(
        tmp_path,
        {"person.csv": [cells("person.csv", personID="1", stateID="001", studentNumber="STU-001")]},
    )
    result = inspect_drop(tmp_path)
    assert result.ok
    assert result.fault is None
    person = next(item for item in result.files if item.name == "person.csv")
    assert person.rows == [("1", None, "001", "STU-001", None, None)]
    assert "person.csv: pass, 1 row." in result.report


def test_quoted_comma_stays_one_value(tmp_path):
    write_drop(
        tmp_path,
        {
            "school.csv": [
                cells("school.csv", schoolID="1", districtID="1", number="100", name="School A, North")
            ]
        },
    )
    result = inspect_drop(tmp_path)
    assert result.ok
    school = next(item for item in result.files if item.name == "school.csv")
    assert school.rows[0][FILES["school.csv"].index("name")] == "School A, North"


def test_quote_without_comma_fails(tmp_path):
    write_drop(tmp_path)
    header = ",".join(FILES["person.csv"])
    (tmp_path / "person.csv").write_bytes(f"{header}\r\n\"1\",,,,,\r\n".encode())
    result = inspect_drop(tmp_path)
    assert not result.ok
    assert result.fault == "extract"
    assert "A value is quoted but does not contain a comma." in result.report


def test_bom_and_line_endings_fail(tmp_path):
    write_drop(tmp_path)
    person = tmp_path / "person.csv"
    person.write_bytes(b"\xef\xbb\xbf" + person.read_bytes())
    bom = inspect_drop(tmp_path)
    assert "UTF-8 BOM" in bom.report

    write_drop(tmp_path)
    person.write_bytes(person.read_bytes().replace(b"\r\n", b"\n"))
    endings = inspect_drop(tmp_path)
    assert "Line endings must be CRLF." in endings.report
    assert endings.fault == "extract"


def test_unknown_column_names_the_column_and_hides_the_cell(tmp_path):
    write_drop(tmp_path)
    columns = FILES["enrollment.csv"]
    header = ",".join(columns) + ",extraCol"
    values = ",".join(["1"] + [""] * (len(columns) - 1)) + "," + TOKEN
    (tmp_path / "enrollment.csv").write_bytes(f"{header}\r\n{values}\r\n".encode())
    result = inspect_drop(tmp_path)
    assert result.fault == "extract"
    assert "enrollment.csv: fail, 0 rows. Unknown column extraCol." in result.report
    assert TOKEN not in result.report
    assert "Nothing was loaded." in result.report


def test_renamed_column_is_unknown_and_missing(tmp_path):
    write_drop(tmp_path)
    person = tmp_path / "person.csv"
    text = person.read_bytes().decode().replace("personID", "personId", 1)
    person.write_bytes(text.encode())
    result = inspect_drop(tmp_path)
    assert "Unknown column personId." in result.report
    assert "Missing column personID." in result.report


def test_missing_column_fails(tmp_path):
    write_drop(tmp_path)
    columns = FILES["person.csv"][:-1]
    (tmp_path / "person.csv").write_bytes((",".join(columns) + "\r\n").encode())
    result = inspect_drop(tmp_path)
    assert "Missing column staffstateID." in result.report


def test_unknown_file_and_missing_file(tmp_path):
    write_drop(tmp_path, omit=("day.csv",), extra=(("notes.csv", b"hello\r\n"),))
    result = inspect_drop(tmp_path)
    assert "day.csv: fail, 0 rows. The file is missing from the folder." in result.report
    assert "notes.csv: fail, 0 rows. This file is not in the extract contract." in result.report
    assert "Warning:" not in result.report


def test_day_warning_allows_repeated_dates(tmp_path):
    day = cells("day.csv", calendarID="1", date="2026-01-05", duration="1", instruction="1", schoolDay="1")
    write_drop(
        tmp_path,
        {
            "enrollment.csv": [cells("enrollment.csv", enrollmentID="1", personID="1", calendarID="9")],
            "day.csv": [day, day],
        },
    )
    result = inspect_drop(tmp_path)
    assert result.ok
    assert "day.csv: pass, 2 rows." in result.report
    assert "Warning: calendar 9 has enrollments and no Day rows." in result.report


def test_missing_folder_is_a_server_fault(tmp_path):
    result = inspect_drop(tmp_path / "absent")
    assert result.fault == "server"
    assert "The folder is not on this machine." in result.report


def test_missing_password_is_a_server_fault(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_OWNER_DB_PASSWORD", raising=False)
    write_drop(tmp_path)
    result = load_drop(tmp_path)
    assert result.fault == "server"
    assert result.saved is False
    assert "CV_OWNER_DB_PASSWORD is not set." in result.report


@pytest.mark.skipif(not os.environ.get("CV_OWNER_DB_PASSWORD"), reason="no database password")
def test_load_replaces_and_a_bad_file_keeps_the_previous_rows(tmp_path):
    day = cells("day.csv", calendarID="1", date="2026-01-05", duration="1", instruction="1", schoolDay="1")
    good = {
        "person.csv": [cells("person.csv", personID="1", stateID="001", studentNumber="STU-001")],
        "identity.csv": [cells("identity.csv", identityID="1", personID="1", firstName="Test", lastName="Test")],
        "enrollment.csv": [cells("enrollment.csv", enrollmentID="1", personID="1", calendarID="9")],
        "day.csv": [day, day],
        "school.csv": [cells("school.csv", schoolID="1", name="School A")],
    }
    write_drop(tmp_path, good)
    first = load_drop(tmp_path)
    assert first.ok and first.saved
    assert "Warning: calendar 9 has enrollments and no Day rows." in first.report
    again = load_drop(tmp_path)
    assert again.ok and again.saved

    columns = FILES["enrollment.csv"]
    header = ",".join((*columns, "extraCol"))
    values = ",".join(["1"] + [""] * (len(columns) - 1)) + "," + TOKEN
    (tmp_path / "enrollment.csv").write_bytes(f"{header}\r\n{values}\r\n".encode())
    failed = load_drop(tmp_path)
    assert not failed.ok
    assert failed.fault == "extract"
    assert failed.saved
    assert TOKEN not in failed.report

    with psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("CV_PG_PORT", "5432")),
        dbname="campusview_data",
        user="campusview_owner",
        password=os.environ["CV_OWNER_DB_PASSWORD"],
    ) as conn:
        stored = conn.execute('SELECT "stateID", "currentIdentityID" FROM raw.person').fetchall()
        assert stored == [("001", None)]
        name = conn.execute('SELECT "firstName" FROM raw.identity').fetchone()
        assert name == ("Test",)
        report = conn.execute(
            "SELECT outcome, fault, report FROM ops.load_batch ORDER BY batch_id DESC LIMIT 1"
        ).fetchone()
    assert report[0] == "fail"
    assert report[1] == "extract"
    assert "Unknown column extraCol." in report[2]

    write_drop(tmp_path, {key: value for key, value in good.items() if key != "person.csv"})
    cleared = load_drop(tmp_path)
    assert cleared.ok and cleared.saved
    with psycopg.connect(
        host="127.0.0.1",
        port=int(os.environ.get("CV_PG_PORT", "5432")),
        dbname="campusview_data",
        user="campusview_owner",
        password=os.environ["CV_OWNER_DB_PASSWORD"],
    ) as conn:
        count = conn.execute("SELECT count(*) FROM raw.person").fetchone()[0]
    assert count == 0
