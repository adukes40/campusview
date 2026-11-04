# Data contract

These are the CSV layouts CampusView loads. The columns listed here are the whole layout. Every column the contract lists is kept, and nothing is dropped. An unknown or misspelled header fails the file with a clear report (Austin, relayed by CampusView Engineer, 2026-11-03). Nothing Austin pulls in is banned: a state student id, a date of birth, staff names, a school's address and phone, and SSN, medical, email, or notes columns if he ever sends them. Each new column or table is added through the change process below. None of this data ever goes into the public repo. See [DECISIONS.md](DECISIONS.md), 2026-11-03.

**Amended 2026-11-03:** CampusView keeps the Infinite Campus table and column names. A typed, checked copy of each raw table replaces the planned mapping to vendor-neutral standard files (2026-11-03 "The typed layer keeps the Infinite Campus names" in [DECISIONS.md](DECISIONS.md)). The standard-layout sections below (`schools.csv` through `plans.csv`) are kept for their meanings, types, and rules. Those file and column names are not load targets. The ten code-mapping files are load targets. The table name in schema `ref` is the file name without `.csv`.

The Infinite Campus section says how a typical extract maps onto these files. It is general public knowledge of how that product is organized, not a description of one district's screens. Anything that depends on local setup is marked **TO CONFIRM** and collected at the end for Austin.

## What the loader checks today

The built loader (PR #10) reads the Infinite Campus files themselves, not the standard files below. It also reads the ten code-mapping files from the district directory you pass (PR #17, merge commit 856bf34), never from the drop. It checks:

- The folder holds all 24 files listed in `loader/contract.py`: `att_day_aggregation`, `attendance`, `attendance_excuse`, `behavior_event`, `behavior_incident`, `behavior_res_type`, `behavior_resolution`, `behavior_role`, `behavior_type`, `calendar`, `campus_attribute`, `campus_dictionary`, `day`, `enrollment`, `identity`, `identity_race_ethnicity`, `period`, `person`, `plan`, `plan_type`, `program`, `program_participation`, `race_ethnicity`, and `school`, each ending in `.csv`. A missing file fails the load. A `.csv` file that is not on the list fails the load. Other files and folders are ignored. A listed file that is a link fails the load. The report says to remove it and does not read the link. Any other link is ignored.
- Each file is UTF-8 and has a header row. The headers match the list exactly, with the same spelling and case, in any order. An unknown, missing, repeated, or blank header fails the file. The report names an unknown or repeated column only when that name starts with a letter or an underscore, and the rest is letters, digits, or underscores, 64 characters at most. Any other text on line 1 is not printed. The report says how many of those columns are on line 1.
- PostgreSQL reads the rows as CSV. Any valid CSV quoting works, and the line endings can be LF or CRLF. A row PostgreSQL rejects fails the load, and the report gives the file and the line number. The database message is kept when it only names a column of that file. The cell is not printed.
- Every value in `raw` is stored as text. A blank cell, quoted or not, is stored as NULL. `school.csv` or `calendar.csv` with zero data rows fails the load. Any other header-only file warns and still loads.
- A calendar with enrollments and no Day rows is a warning, not a failure. See [the extracts guide](guides/sftp-and-extracts.md).
- The district directory holds the ten code-mapping files. What fails, what warns, and which extract column each map covers are in [Code-mapping files](#code-mapping-files).

In the same transaction that replaces `raw`, the loader builds schema `ic`. Each raw table is copied to the same table name in `ic`. Date and time columns are timestamps. Infinite Campus writes them as `YYYY-MM-DD HH:MM:SS.fff`, including a time of day on columns whose names end in Date. The tables are dropped and rebuilt on every load, with no keys, indexes, or constraints.

How a column's type is chosen (`kind` in `loader/contract.py`):

- `endYear` is an integer. The columns in `BOOLEANS` are booleans and the columns in `NUMBERS` are numeric.
- A name that ends in `timestamp`, `Stamp`, `Time`, or `date`, is `date`, or contains `Date` is a timestamp. That includes time-only columns such as `period.startTime`. Compare those by time of day with `::time`.
- A name that ends in `ID` or `Id` is an id and stays text. Every other column, including codes, `grade`, and `studentNumber`, stays text.

What the typed copy warns about today. Each warning gives the file, the column, the number of rows, the rule, and the first line. It never gives the value. The first line is counted in the order PostgreSQL stores the raw rows, which is the file order after a fresh load.

- An id that is not 1 to 64 letters, digits, hyphens, or underscores. It becomes NULL.
- Text with a line break or other control character. It becomes NULL.
- A boolean, number, school year, or timestamp that PostgreSQL's `pg_input_is_valid` rejects for that type. It becomes NULL. PostgreSQL also accepts `t`, `yes`, `1`, and `on` (and their opposites) as booleans.
- A blank key in three columns only: `school.schoolID`, `calendar.calendarID`, and `enrollment.enrollmentID` (`REQUIRED` in `loader/contract.py`). No other blank cell warns.

The three cross-row checks warn and keep the row. Each gives the file and the number of rows, with no line number:

- Two grades for the same student, school, and year: `enrollment` rows with the same `personID`, the calendar's `schoolID`, and `endYear`, and more than one `grade`.
- Attendance outside enrollment: an `attendance` row with no `enrollment` for the same person at the same school (matched through each calendar's `schoolID`) whose `startDate` is on or before the date and whose `endDate` is blank or on or after it. Any enrollment counts, not only a primary one.
- An action date before the incident was entered: a `behavior_resolution` whose `discassignDate` falls on an earlier calendar day than its incident's `timestamp`, joined through `behavior_role` and `behavior_event`. A same-day action does not warn.

**Not built yet:** duplicate-key checks on the extracts, foreign-key checks, and the impossible referral-flag check.

## Shared file rules

These rules were written for vendor-neutral standard files, which will not be built. They are the reference for the typed copy's checks. Bad keys and unknown codes are warnings on the load report, and loading continues. Header and column problems, missing files, and unexpected files fail the whole batch (Austin, relayed by CampusView Engineer, 2026-11-03).

- UTF-8, comma-separated, a header row, any valid CSV quoting.
- Header names match this document exactly, lowercase, in any column order.
- An unknown or misspelled header fails the file, and the report names that header (Austin, relayed by CampusView Engineer, 2026-11-03). A missing required header fails the file.
- **Bad values warn** (Austin, relayed by CampusView Engineer, 2026-11-03, 12:47 PM ET). A cell that breaks one of the value rules below is stored as NULL in the `ic` copy, and the load report lists the problem with the file, row number, and rule. Today's report gives the column and the first line for each rule, not every row (see above). Loading continues. The raw table keeps the text as it arrived.
- Character set for every id: letters, digits, hyphen, underscore, length 1 to 64.
- Dates are `YYYY-MM-DD`. Times are `HH:MM` in 24-hour local time. In `ic`, every date and time column is a timestamp (see above).
- Booleans are `true` or `false`. In `ic`, any spelling PostgreSQL accepts is a valid boolean.
- Decimals use a period.
- School year is `YYYY-YYYY` with the second year equal to the first plus one. In `ic`, the school year is the integer `endYear`.
- A blank cell is allowed only where the column says optional. A blank required cell in an extract is a warning. Today only the three keys above warn when blank. A blank in a code-mapping file is covered under [Code-mapping files](#code-mapping-files).
- A duplicate or bad key is a warning on the load report. Loading continues. **Not built yet** for duplicate keys and foreign keys; today only an id with bad characters and the three blank keys warn.
- A code that is not in the matching mapping table warns, and loading continues. The report shape is in [Code-mapping files](#code-mapping-files). There is no silent "other" bucket. The district adds an explicit map row for every code that appears.
- Text fields must not contain line breaks or other control characters. A cell that does is a warning.
- The nightly drop is a full copy, not a list of changes since yesterday (Austin, relayed by CampusView Engineer, 2026-11-03 7:30 PM ET). After a good load, the warehouse matches the drop. The district's cutoff date, set in the district repo, says the earliest date kept.
- Only `school.csv` and `calendar.csv` must contain at least one data row. If either has zero data rows, the whole load fails (Austin, 2026-11-03, 1:05 to 1:13 PM ET). Every other extract file, including `day.csv`, `person.csv`, and `enrollment.csv`, may arrive empty. An empty extract file is a warning on the load report, and loading continues. A header-only code-mapping file is covered under [Code-mapping files](#code-mapping-files).
- Mapping files live in the district directory passed to the loader, not in the SFTP drop. They are required on every load (Austin, relayed by CampusView Engineer, 2026-11-03, 12:47 PM ET). The failure and warning rules are in [Code-mapping files](#code-mapping-files).
- One failed file fails the whole load. The previous snapshot stays. Warnings do not fail a file.
- **What fails the load:** an unknown, missing, repeated, or blank header; a missing or unexpected file; a row PostgreSQL rejects when loading `raw` (raw is all text, so this is a file-format problem, not a bad value); an empty `school.csv` or `calendar.csv` (zero data rows); and a bad code-mapping file. Each of these fails before anything is written to `raw`, `ic`, or `ref`. The failed attempt is still recorded in `ops.load_batch`.
- **What warns and keeps loading:** any other file with zero data rows, bad values (stored as NULL in `ic`), bad or duplicate keys (duplicates not checked yet), extract codes with no map row, and the cross-row checks in the file sections below. Three of those checks are built. The referral-flag check is not built yet. A row that fails a cross-row check stays as it is in `ic` and still counts in the metrics (Austin, 2026-11-03, 12:56 PM ET).
- Error reports name the file, the row number, and the rule. They do not repeat the cell value. Today's loader names the file and the reason, and gives a line number when PostgreSQL rejects a row. A typed-copy warning names the file, column, row count, rule, and first line. A cross-row warning names the file and row count.

## Changing the contract

File names, header names, and date formats stay fixed (Austin, relayed by CampusView Engineer, 2026-11-03). Adding a new column or a new table needs a documented process. Until a column is added, a file that carries it fails with a clear report.

The loader's file list is the Infinite Campus headers in `loader/contract.py`. To add a column or a file, add it there, then add it to the extract. The steps are in [the extracts guide](guides/sftp-and-extracts.md). Until the list includes the new header, the loader fails the file and the report names the header. Do not rename a header that is already in the list.

The standard layouts in this document will not be written as files. The typed copy keeps the Infinite Campus names. Do not change those layouts' meanings or rules without Austin.

*Not built yet:* `raw` and `ic` have no foreign keys today. Planned: load order inside the transaction follows the foreign keys: schools and students, then enrollments and calendar days, then attendance, incidents, incident behaviors, consequences, and plans. The check looks at the whole drop before anything is written.

## schools.csv

One row per school. Key: `school_id`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `school_id` | text | yes | Primary key. The id used on every other file and in Superset's row-level security. |
| `school_name` | text | yes | 1 to 120 characters. |
| `school_level` | text | no | Blank, or one of `ES`, `MS`, `HS`, `K8`, `OTHER`. |
| `is_active` | boolean | no | Blank means `true`. Inactive schools can still appear in history. |

## students.csv

One row per student. Key: `student_id`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `student_id` | text | yes | Primary key. The district student number staff already know. |
| `first_name` | text | yes | 1 to 80 characters. |
| `last_name` | text | yes | 1 to 80 characters. |
| `gender_code` | text | no | If present, must exist in `map_genders.csv`. Blank is allowed and means unknown. |
| `race_code` | text | no | If present, must exist in `map_race_groups.csv`. Used only to build equity totals. Never copied onto a named list. |

## enrollments.csv

One row per enrollment span. Key: `enrollment_id`. Also unique on (`student_id`, `school_id`, `start_date`).

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `enrollment_id` | text | yes | Primary key. |
| `student_id` | text | yes | Must exist in `students.csv`. |
| `school_id` | text | yes | Must exist in `schools.csv`. |
| `school_year` | school year | yes | |
| `grade` | text | yes | Must exist as `grade_code` in `map_grades.csv`. |
| `start_date` | date | yes | |
| `end_date` | date | no | Blank means still enrolled. If set, must be on or after `start_date`. |
| `is_primary` | boolean | yes | `true` if this span is the membership enrollment. |
| `enrollment_status` | text | no | Blank, or one of `ACTIVE`, `WITHDRAWN`, `GRADUATED`, `OTHER`. Dates drive the metrics. Status does not. |

Validation beyond types:

- For one student, primary spans must not overlap in dates.
- For one student, one school, and one school year, every row shares a single `grade`. Two grades in that combination are a warning on the load report. Loading continues. The row stays as it is in `ic`, still counts in the metrics, and is listed on the load report (Austin, 2026-11-03, 12:56 PM ET). This is the working rule in Decisions for Austin, item 19, in [METRICS.md](METRICS.md): v1 does not represent a mid-year grade change unless Austin asks for it.
- A school that has enrollments but no calendar days in that school year does not fail the file. It loads, and the load report shows a warning naming the school and year (Austin, relayed by CampusView Engineer, 2026-11-03). Today's loader checks this on the Infinite Campus files and names the calendar id instead. Its students have no membership days until calendar days arrive.

## calendar_days.csv

One row per school per date. Key: (`school_id`, `calendar_date`).

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `school_id` | text | yes | Must exist in `schools.csv`. |
| `school_year` | school year | yes | |
| `calendar_date` | date | yes | Unique with `school_id`. |
| `is_school_day` | boolean | yes | `true` only when the day counts as membership. From Infinite Campus, this is the Day table's `instruction` flag, not `schoolDay` (Austin, relayed by CampusView Engineer, 2026-11-03). |
| `day_value` | decimal | yes | Greater than 0 and at most 1. A full day is `1`. A half day is `0.5`. Required on every row so a half day is never guessed. For now, every instruction day counts as 1 day, so the Infinite Campus mapping writes `1` on every row (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET). |

Non-school days may be omitted. If they are included, `is_school_day` is `false` and reporting views ignore them. `day_value` on a non-school day is not used.

## attendance.csv

One row per student per school per date, already rolled up to the day. Key: (`student_id`, `school_id`, `calendar_date`).

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `student_id` | text | yes | Must exist in `students.csv`. |
| `school_id` | text | yes | Must exist in `schools.csv`. |
| `school_year` | school year | yes | Must match the calendar day. |
| `calendar_date` | date | yes | Must exist in `calendar_days.csv` for that school, with `is_school_day` true. |
| `attendance_code` | text | yes | Must exist in `map_attendance_codes.csv`. |

The portion of the day, and whether the code is a tardy, live only in the attendance-code map. The extract does not carry a second copy of that decision.

The date must fall inside a primary enrollment for that student and school. A row that does not is a warning on the load report. Loading continues. The row stays as it is in `ic`, still counts in the metrics, and is listed on the load report (Austin, 2026-11-03, 12:56 PM ET). A school day with no attendance row is not an error. How metrics treat that day is a decision in [METRICS.md](METRICS.md).

## incidents.csv

One referral, one student. If the source system records several students on one event, the mapping emits one row per student, each with its own `incident_id`. Key: `incident_id`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `incident_id` | text | yes | Primary key. |
| `student_id` | text | yes | Must exist in `students.csv`. |
| `school_id` | text | yes | Must exist in `schools.csv`. |
| `school_year` | school year | yes | |
| `incident_date` | date | yes | |
| `incident_time` | time | no | Blank if the time was not recorded. |
| `location_code` | text | no | If present, must exist in `map_locations.csv`. |
| `status_code` | text | yes | Must exist in `map_referral_statuses.csv`. |
| `action_date` | date | no | Date of the first action or consequence. Blank if there is no action yet. Must be on or after `behavior_incident.timestamp`, the date the referral was entered into Infinite Campus, when set (Austin, 2026-11-03, 12:55 PM ET; the column per Austin, 2026-11-03, 1:16 PM ET). An earlier date is a warning; the row is kept and still counts (Austin, 2026-11-03, 12:56 PM ET). |

No narrative, participant notes, or victim names.

## incident_behaviors.csv

Coded behaviors on a referral. This is part of the incidents layout, as its own file, so two codes on one referral stay explicit. Key: `incident_behavior_id`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `incident_behavior_id` | text | yes | Primary key. |
| `incident_id` | text | yes | Must exist in `incidents.csv`. |
| `behavior_code` | text | yes | Must exist in `map_behavior_types.csv`. |

A referral may have zero behavior rows. It still counts as a referral. It does not appear on a behavior-type chart.

## consequences.csv

Key: `consequence_id`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `consequence_id` | text | yes | Primary key. |
| `incident_id` | text | yes | Must exist in `incidents.csv`. |
| `student_id` | text | yes | Must equal the student on that incident. |
| `school_id` | text | yes | Must exist in `schools.csv`. |
| `consequence_code` | text | yes | Must exist in `map_consequences.csv`. |
| `start_date` | date | no | |
| `end_date` | date | no | If both dates are set, `end_date` is on or after `start_date`. |
| `consequence_days` | decimal | no | If set, must be 0 or greater. |

## plans.csv

One row per 504 or IEP. Key: `plan_id`. The file has no school column. Reporting attaches the plan to the student's primary enrollment. See [METRICS.md](METRICS.md).

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `plan_id` | text | yes | Primary key. |
| `student_id` | text | yes | Must exist in `students.csv`. |
| `plan_type_code` | text | yes | Must exist in `map_plan_types.csv`. |
| `status_code` | text | yes | Must exist in `map_plan_statuses.csv`. |
| `start_date` | date | yes | |
| `end_date` | date | no | If set, on or after `start_date`. |
| `review_due_date` | date | no | The date used for "expiring in 30 days" when it is present. |

## Code-mapping files

These ten files live in the district directory the loader is given, not in the SFTP drop. The loader puts each one in schema `ref` on every load, in the same transaction as `raw` and `ic`. The table name is the file name without `.csv`. It grants nothing, so `campusview_reader` cannot read `ref`.

A missing file, a bad header, or a bad value fails the load before anything is written. The report says the problem is in the district config folder's map files. A missing district folder says the problem is the district config folder. The report names the map file, the line, and the rule, and it does not repeat the cell value. A file that is not valid CSV fails, and so does a row whose length does not match the header. A blank required cell fails. A duplicate key fails, and so does a duplicate `sort_order`. Labels are 1 to 80 characters with no control characters. Booleans are exactly `true` or `false`. A header-only file replaces that table with zero rows and does not warn.

An extract value with no map row warns, and the load still passes. The warning names the extract file, the column, the number of rows, and the first line. It does not include the value. A blank cell does not warn. Keys are the local codes exactly as they appear in the extracts.

The warning checks these columns. `map_grades` uses `enrollment.grade`. `map_genders` uses `identity.gender`. `map_locations` uses `behavior_incident.location`. `map_referral_statuses` uses `behavior_incident.status`. `map_behavior_types` uses `behavior_type.code`. `map_consequences` uses `behavior_res_type.code`. `map_race_groups` uses `race_ethnicity.code`. `map_plan_types` uses `plan_type.type`. `map_plan_statuses` uses `plan.status`. `map_attendance_codes` counts `attendance.csv` rows whose excuse code, from `attendance_excuse.code`, is missing. The warning says `attendance.csv` excuse code. An excuse code that no attendance row uses does not warn.

### map_attendance_codes.csv

Key: `attendance_code`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `attendance_code` | text | yes | |
| `label` | text | yes | |
| `counts_as` | text | yes | One of `PRESENT`, `ABSENT_EXCUSED`, `ABSENT_UNEXCUSED`, `TARDY_EXCUSED`, `TARDY_UNEXCUSED`, `PARTIAL`. |
| `absence_portion` | decimal | yes | 0 through 1. |

A `PRESENT` code has portion 0. An excused or unexcused absence typically has portion 1. `PARTIAL` is the half-day (or other partial) absence, and the portion says how much. For now, the Infinite Campus mapping gives half-day absence codes portion 1, so a half-day absence counts as a full day absent, the same as any other absence (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET). This is provisional; see the follow-ups for the SIS person below. A tardy code uses portion 0 unless this district has chosen that the tardy also removes part of the day. Views increment the tardy count from `counts_as` and apply `absence_portion` separately, so a tardy with portion 0 does not lower the attendance rate.

### map_behavior_types.csv

Key: `behavior_code`. Columns: `behavior_code`, `label` (both required).

### map_locations.csv

Key: `location_code`. Columns: `location_code`, `label` (both required).

### map_consequences.csv

Key: `consequence_code`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `consequence_code` | text | yes | |
| `label` | text | yes | |
| `is_exclusionary` | boolean | yes | `true` for suspension or expulsion style consequences. |

### map_genders.csv

Key: `gender_code`. Columns: `gender_code`, `label` (both required). The filter shows these labels. Codes the district does not use are simply not in the file.

### map_grades.csv

Key: `grade_code`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `grade_code` | text | yes | The value stored on the enrollment. |
| `label` | text | yes | What the filter shows, such as `K` or `1`. |
| `sort_order` | integer | yes | `K` is 0, then 1, 2, and so on. Unique. |

### map_race_groups.csv

Key: `race_code`. Columns: `race_code`, `equity_group_label` (both required). The equity chart shows `equity_group_label` and nothing finer. Named views never read this file.

### map_referral_statuses.csv

Key: `status_code`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `status_code` | text | yes | |
| `label` | text | yes | |
| `is_processed` | boolean | yes | `false` means not yet processed. |
| `is_open` | boolean | yes | `true` means still open. |
| `is_cancelled` | boolean | yes | `true` means the referral is ignored by every metric. |

A row with `is_cancelled` false, `is_processed` false, and `is_open` false is a warning on the load report. Loading continues. The row stays as it is in `ic`, still counts in the metrics, and is listed on the load report (Austin, 2026-11-03, 12:56 PM ET). **Not built yet.** That combination would make a referral vanish from both lists without being cancelled. Cancelled rows must have the other two flags false.

### map_plan_types.csv

Key: `plan_type_code`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `plan_type_code` | text | yes | |
| `plan_type` | text | yes | `504` or `IEP`. |
| `label` | text | yes | |

### map_plan_statuses.csv

Key: `status_code`. Columns: `status_code` (required), `is_active` (boolean, required).

## How an Infinite Campus extract maps to this

Infinite Campus is the first source system. Districts usually schedule an export (often an Ad Hoc filter or a CSV data extract) onto a folder. CampusView picks that folder up over SFTP. It does not log in to Infinite Campus and it does not read the Infinite Campus database.

There is no file transform. The loader loads the Infinite Campus files as they arrive, and the typed copy keeps their names. The table below says which Infinite Campus field carries each meaning the views need.

What follows is the usual shape of Infinite Campus, from public product knowledge. Table names, screen names, and code lists differ by state edition and by how the district configured the system. Those differences are the TO CONFIRM list. Do not treat a field name below as a column Austin's extract is known to contain.

| CampusView field | Usual Infinite Campus source | Notes |
| --- | --- | --- |
| `students.student_id` | The student number shown on the student record | Use that visible number as `student_id`, not the internal person id or a state identifier. Any other id the extract sends is kept as its own listed column. |
| `students.first_name`, `last_name` | The identity name fields | Which name is the legal name is local. |
| `students.gender_code` | Demographics gender, as stored | Codes are district-defined. Copy them through and map them. |
| `students.race_code` | Federal race and ethnicity fields | Which field feeds equity groups is local. |
| `schools.school_id`, `school_name` | The school record attached to a calendar | Confirm whether the extract uses a number, a code, or an internal id. The same value must appear on enrollments, calendar days, and attendance. |
| `enrollments` | An enrollment tied to a calendar: start date, end date, grade, service type | A primary service type becomes `is_primary` true. Other service types become false so they do not double-count membership. |
| `enrollments.school_year` | The school year on that calendar | Infinite Campus often stores an end year. The mapping converts it to `YYYY-YYYY`. |
| `calendar_days` | The Infinite Campus Day table (the school calendar's day records), which Austin will upload (Austin, relayed by CampusView Engineer, 2026-11-03) | Column details: set when the file arrives. A day counts for attendance when its `instruction` flag is set, not `schoolDay`. For now, every instruction day counts as 1 day, and a half-day absence counts as a full day absent (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET). A calendar with enrollments but no Day rows loads with a warning. *Suggested by the CampusView Engineer, not decided:* add `dayID` and `structureID` to the Day extract query (`day.sql`), because a calendar with more than one schedule structure repeats dates. `day.sql` is not in this repo. |
| `attendance` | The daily attendance result | A student is present for the day when marked present in homeroom, even if they leave during homeroom. Tardies come from Infinite Campus's overnight attendance calculation (Austin, relayed by CampusView Engineer, 2026-11-03). Which columns carry the homeroom mark: set when the file arrives. |
| `attendance.attendance_code` | The district's attendance code | The code's status (present, absent, tardy) and excuse (excused, unexcused) are configured in Infinite Campus. Copy the code. Put the meaning in `map_attendance_codes.csv`. |
| `incidents` | A behavior incident, a behavior referral, or both | Staff in different districts use these words for different records. The mapping has to match Austin's workflow. |
| `incident_behaviors` | The coded offense (behavior event) for the offender role | One event with two codes becomes two rows. Several offenders become several incident rows. |
| `incidents.location_code`, `incident_time` | Location and time on the incident | Both are only as good as local entry. |
| `incidents.status_code` | The referral or incident status in the local workflow | Map each real status to processed, open, and cancelled. |
| `consequences` | The behavior resolution: type, dates, duration | Other resolution columns the extract sends are kept. |
| `plans` for an IEP | The special education plan: start, end, and annual review | Field names differ by state edition. |
| `plans` for a 504 | `program_participation`, rows for the 504 program (Austin, relayed by CampusView Engineer, 2026-11-03) | Column details: set when the file arrives. |

Keep every table and column Austin's extract sends, once the change process adds it to the contract. Tables and columns this table does not map, such as a state student identifier, a date of birth, a referral's staff name, or a school's address, phone, and principal, are kept so later production tables can be built on them.

### Expected Infinite Campus files

What is known so far (Austin, relayed by CampusView Engineer, 2026-11-03):

- Delivery is SFTP for now.
- Extracts are capped to dates on or after 2025-07-01. Infinite Campus started in the 2025-26 school year, so the years kept are 2025-26 and 2026-27.
- The Day table (calendar day records). Column details: set when the file arrives.
- `program_participation`, for 504 status. Column details: set when the file arrives.
- The first sample was 23 CSV files from the training database. Each had at most 1,000 rows because of the DB Hub plugin Austin used to pull them. The real extracts are not capped at 1,000 rows. The loader's list in `loader/contract.py` now has 24 files.

The typed copy does not invent codes and does not decide that a code is excused. It only converts types. Meaning stays in the mapping tables so a code change is a district-repo edit, not a program change.

## TO CONFIRM

**Deferred, not blocking step 0.** For Austin. The typed copy is built (PR #14), and the loader reads the ten code-mapping files. These questions still block the reporting views. The working text above is general product knowledge, not a claim about this district's files.

1. *Partly answered (Austin, relayed by CampusView Engineer, 2026-11-03): delivery is SFTP for now. Which export builds the files is still open.* Which export will actually be scheduled onto SFTP: an Ad Hoc filter CSV, the data-extract utility, or another report. CampusView will not connect to the Infinite Campus database.
2. **Answered** (Austin, relayed by CampusView Engineer, 2026-11-03; full copy confirmed 7:30 PM ET): keep everything dated on or after 2025-07-01, and each nightly drop is a full copy. That each nightly file set is a full snapshot of everything dated on or after the district cutoff date, not a file of changes since the previous night.
3. The student number to use as `student_id`: the number staff see on the student record, not the internal person id or a state identifier.
4. The school identifier to use as `school_id`, so the same value can be used in Superset's row-level security rules.
5. How the calendar's school year is stored, including an end-year number if that is what Infinite Campus shows, so the views can show `YYYY-YYYY`.
6. **Answered** (Austin, relayed by CampusView Engineer, 2026-11-03): the daily result is the homeroom mark. Whether secondary schools record period attendance, elementary schools record daily attendance, or both already have a daily result. The views need one row per student per date.
7. **Answered** (Austin, relayed by CampusView Engineer, 2026-11-03): present for the day if marked present in homeroom, even if the student leaves during homeroom; tardies come from Infinite Campus's overnight calculation. The local rule that turns periods into a full-day or half-day absence, or confirmation that Infinite Campus already calculates a daily attendance value the extract should take instead.
8. The attendance code list, and for each code whether it is present, an excused absence, an unexcused absence, an excused tardy, an unexcused tardy, or a partial day, plus the portion of the day.
9. *Partly answered (Austin, relayed by CampusView Engineer, 2026-11-03): the Day table; attendance counts `instruction` days; for now, every instruction day counts as 1 day and a half-day absence counts as a full day absent (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET). How half days are marked, and whether they should ever count as half, is a follow-up below.* How a half instructional day shows up on the calendar, so `day_value` can be set to `0.5` instead of `1`.
10. Which behavior record is "a referral" here: the behavior referral, the behavior incident, or both. Public material shows incidents, coded events, and resolutions; the referral workflow itself is configured per district.
11. The status values staff really use, and which ones mean not yet processed, still open, closed, or void or cancelled.
12. That one incident with several students should become one CampusView incident row per student.
13. The location code list, and whether incident time is entered often enough to support an hour-of-day heatmap.
14. The consequence code list, and which codes are exclusionary.
15. *Partly answered (Austin, relayed by CampusView Engineer, 2026-11-03): 504 status comes from `program_participation`, 504 program. IEP field names are still open.* Where 504 plans are stored in this district's Infinite Campus. IEP start, end, and annual review field names also need to be confirmed; they vary by state edition.
16. Which race or ethnicity field should feed the equity groups.
17. Grade values as stored, such as `K`, `KF`, `01`, or `1`, so the grade map can match them.
18. *Partly answered (Austin, relayed by CampusView Engineer, 2026-11-03): keep every table and column sent; each one is added through the change process.* The full list of tables and columns the scheduled extracts will carry. The loader keeps all of them; the list tells the docs what lands in the drop folder.

### Open follow-ups for the SIS person

Raised from the Day table rules above (2026-11-03). Ask the district's Infinite Campus (SIS) person:

1. `instruction` or `schoolDay`: which Day table flag is right for counting attendance days? CampusView uses `instruction` for now.
2. Are there half-day, AM, or PM schedules, and how are half days marked in the Day table? Should a half day, or a half-day absence, ever count as half? For now, CampusView counts every instruction day as 1 day and every half-day absence as a full day absent.
3. Should a calendar ever have enrollments but no Day rows? CampusView loads it with a warning for now.
4. Confirm `behavior_incident.timestamp` is the entry date (Austin believes it is, Austin, 2026-11-03, 1:16 PM ET). Days to action and days open count from it.
