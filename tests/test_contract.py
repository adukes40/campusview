from loader.contract import BOOLEANS, kind


def test_kind_examples():
    assert kind("endYear") == "year"
    assert kind("behavior") == "bool"
    assert all(kind(column) == "bool" for column in BOOLEANS)
    for column in ("studentNumber", "grade", "zip", "hispanicEthnicity"):
        assert kind(column) == "text"
    for column in ("date", "birthdate", "startDate", "modifiedDate", "discassignDate", "startTime", "timestamp", "endtimeStamp"):
        assert kind(column) == "timestamp"
    assert kind("schoolID") == "id"
