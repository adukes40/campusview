FILES = {
    "att_day_aggregation.csv": "calendarID,personID,date,scheduledMinutes,absentMinutes,unexcusedAbsentMinutes,tardies,absentPeriods,mostCommonExcuseID".split(","),
    "attendance.csv": "attendanceID,calendarID,personID,periodID,excuseID,date,status,presentMinutes".split(","),
    "attendance_excuse.csv": "excuseID,calendarID,excuse,code,status,behavior,description".split(","),
    "behavior_event.csv": "eventID,calendarID,incidentID,typeID,violenceIndicator,referralName".split(","),
    "behavior_incident.csv": "incidentID,calendarID,referralpersonID,location,status,timestamp".split(","),
    "behavior_res_type.csv": "typeID,code,name".split(","),
    "behavior_resolution.csv": "resolutionID,adminpersonID,roleID,typeID,discassignDate,timestamp,endDate,endtimeStamp,schooldaysDuration".split(","),
    "behavior_role.csv": "eventID,personID,roleID,role".split(","),
    "behavior_type.csv": "typeID,code,name,alignment,stateeventCode".split(","),
    "calendar.csv": "calendarID,districtID,schoolID,endYear,name,number,startDate,endDate,exclude,summerSchool,studentDay,wholeDayAbsence,halfDayAbsence,type".split(","),
    "campus_attribute.csv": "attributeId,element,object".split(","),
    "campus_dictionary.csv": "attributeId,name,code".split(","),
    "day.csv": "calendarID,date,duration,instruction,schoolDay".split(","),
    "enrollment.csv": "enrollmentID,personID,calendarID,structureID,endYear,grade,serviceType,noShow,stateExclude,startStatus,endStatus,active,startDate,endDate,endAction,districtID,modifiedDate".split(","),
    "identity.csv": "identityID,personID,effectiveDate,lastName,firstName,middleName,suffix,birthdate,gender,hispanicEthnicity,raceethnicityFed,raceEthnicity,homeprimarylanguage".split(","),
    "identity_race_ethnicity.csv": "identityId,raceId".split(","),
    "period.csv": "periodID,periodScheduleID,name,seq,startTime,endTime,nonInstructional,periodMinutes".split(","),
    "person.csv": "personID,currentIdentityID,stateID,studentNumber,staffNumber,staffstateID".split(","),
    "plan.csv": "planID,personID,typeID,districtID,startDate,endDate,status,locked,archive,autoEnded,amendedFromPlanID,endDatePreAmend,amendmentStartDate,createdDate,modifiedDate".split(","),
    "plan_type.csv": "typeID,name,abbreviation,type,module,contentArea,interventionTier,active,districtID".split(","),
    "program.csv": "programID,name,code,type,programCategory,programType,active,modifiedDate".split(","),
    "program_participation.csv": "participationID,programID,personID,startDate,endDate,eligibilityStartDate,eligibilityEndDate,status,studentStatus,exitReason,programCategory,type,districtID,modifiedDate".split(","),
    "race_ethnicity.csv": "raceId,code,federalCode,active,name".split(","),
    "school.csv": "schoolID,districtID,number,name,type,address,city,state,zip,phone,principalName,exclude".split(","),
}

YEARS = frozenset({"endYear"})
BOOLEANS = frozenset({
    "exclude", "summerSchool", "instruction", "schoolDay", "noShow",
    "stateExclude", "active", "nonInstructional", "locked", "archive",
    "autoEnded", "violenceIndicator",
})
NUMBERS = frozenset({
    "scheduledMinutes", "absentMinutes", "unexcusedAbsentMinutes", "tardies",
    "absentPeriods", "presentMinutes", "studentDay", "wholeDayAbsence",
    "halfDayAbsence", "duration", "seq", "periodMinutes", "schooldaysDuration",
})

REQUIRED = {
    "school.csv": ("schoolID", "name"),
    "calendar.csv": ("calendarID", "schoolID", "endYear"),
    "enrollment.csv": ("enrollmentID", "personID", "calendarID", "endYear", "grade", "startDate"),
    "person.csv": ("personID",),
    "identity.csv": ("identityID", "personID"),
    "day.csv": ("calendarID", "date"),
    "attendance.csv": ("attendanceID", "personID", "calendarID", "date"),
    "att_day_aggregation.csv": ("calendarID", "personID", "date"),
    "attendance_excuse.csv": ("excuseID",),
    "behavior_event.csv": ("eventID", "incidentID"),
    "behavior_incident.csv": ("incidentID",),
    "behavior_resolution.csv": ("resolutionID",),
    "behavior_role.csv": ("roleID", "eventID", "personID"),
    "behavior_res_type.csv": ("typeID",),
    "behavior_type.csv": ("typeID",),
    "campus_attribute.csv": ("attributeId",),
    "campus_dictionary.csv": ("attributeId", "code"),
    "identity_race_ethnicity.csv": ("identityId", "raceId"),
    "period.csv": ("periodID",),
    "plan.csv": ("planID", "personID"),
    "plan_type.csv": ("typeID",),
    "program.csv": ("programID",),
    "program_participation.csv": ("participationID", "programID", "personID"),
    "race_ethnicity.csv": ("raceId",),
}


def kind(column):
    if column in YEARS:
        return "year"
    if column in BOOLEANS:
        return "bool"
    if column in NUMBERS:
        return "num"
    if column.endswith("timestamp") or column.endswith("Stamp"):
        return "stamp"
    if column.endswith("Time"):
        return "time"
    if column.endswith("ID") or column.endswith("Id"):
        return "id"
    if column == "date" or column.endswith("date") or "Date" in column:
        return "date"
    return "text"


def assert_contract():
    columns = {column for group in FILES.values() for column in group}
    if YEARS & BOOLEANS or YEARS & NUMBERS or BOOLEANS & NUMBERS:
        raise RuntimeError("YEARS, BOOLEANS, and NUMBERS overlap")
    if (YEARS | BOOLEANS | NUMBERS) - columns:
        raise RuntimeError("a typed column set names a column that is not in FILES")
    if set(REQUIRED) != set(FILES):
        raise RuntimeError("REQUIRED files are not in FILES")
    for filename, required in REQUIRED.items():
        if not required or any(column not in FILES[filename] for column in required):
            raise RuntimeError("REQUIRED columns are not in FILES")


assert_contract()
