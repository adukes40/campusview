from loader.contract import BOOLEANS, FILES, assert_contract, kind


def test_kind_examples():
    assert kind("endYear") == "year"
    assert kind("halfDayAbsence") == "num"
    assert all(kind(column) == "bool" for column in BOOLEANS)
    for column in ("studentNumber", "staffNumber", "number", "grade", "zip", "hispanicEthnicity"):
        assert kind(column) == "text"
    assert kind("startTime") == "time"
    assert kind("endTime") == "time"
    assert kind("timestamp") == "stamp"
    assert kind("endtimeStamp") == "stamp"
    assert kind("schoolID") == "id"
    assert kind("attributeId") == "id"
    assert kind("raceId") == "id"
    assert kind("date") == "date"
    assert kind("birthdate") == "date"
    assert kind("startDate") == "date"
    assert kind("discassignDate") == "date"


def test_assert_contract_and_kind_totals():
    assert_contract()
    allowed = {"id", "text", "date", "time", "stamp", "bool", "num", "year"}
    counts = {name: 0 for name in allowed}
    for columns in FILES.values():
        for column in columns:
            got = kind(column)
            assert got in allowed
            counts[got] += 1
    assert counts == {
        "id": 62,
        "text": 69,
        "date": 24,
        "time": 2,
        "stamp": 3,
        "bool": 16,
        "num": 13,
        "year": 2,
    }
