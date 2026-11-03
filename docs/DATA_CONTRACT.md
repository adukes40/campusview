# Data contract

These are the CSV layouts CampusView loads. The columns listed here are the ones CampusView checks and uses. The loader also keeps every other column the extract sends, such as a state student id, a date of birth, staff names, or a school's address and phone. It does not drop or reject them. How the raw schema stores those extra columns is set in step 1. See [DECISIONS.md](DECISIONS.md), 2026-11-03.

The Infinite Campus section says how a typical extract maps onto these files. It is general public knowledge of how that product is organized, not a description of one district's screens. Anything that depends on local setup is marked **TO CONFIRM** and collected at the end for Austin.

## Shared file rules

- UTF-8, comma-separated, a header row, quoting when a value contains a comma.
- Header names match this document exactly, lowercase, in any column order.
- A header not listed here is kept as an extra column. A missing required header fails the file.
- Character set for every id: letters, digits, hyphen, underscore, length 1 to 64.
- Dates are `YYYY-MM-DD`. Times are `HH:MM` in 24-hour local time.
- Booleans are `true` or `false`.
- Decimals use a period.
- School year is `YYYY-YYYY` with the second year equal to the first plus one.
- A blank cell is allowed only where the column says optional.
- Duplicate keys fail the file.
- A code that is not in the matching mapping table fails the file. There is no silent "other" bucket. The district adds an explicit map row for every code that appears.
- Text fields reject line breaks and other control characters.
- The nightly drop is a full snapshot of the school years to keep, not a list of changes since yesterday. After a good load, the warehouse matches the drop, minus years outside the history window.
- `schools.csv`, `students.csv`, `enrollments.csv`, and `calendar_days.csv` must each contain at least one data row. The other extract files may be header-only.
- Mapping files live in the district repo, not in the SFTP drop. They are required on every load. A bad mapping fails the load the same way a bad extract does.
- One failed file fails the whole load. The previous snapshot stays.
- Error reports name the file, the row number, and the rule. They do not repeat the cell value.

Load order inside the transaction follows the foreign keys: schools and students, then enrollments and calendar days, then attendance, incidents, incident behaviors, consequences, and plans. The check looks at the whole drop before anything is written.

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
- For one student, one school, and one school year, every row shares a single `grade`. Two grades in that combination fail the file. This is the working rule in Decisions for Austin, item 19, in [METRICS.md](METRICS.md): v1 does not represent a mid-year grade change unless Austin asks for it.
- Every `school_id` that has an enrollment also has at least one calendar day in that school year.

## calendar_days.csv

One row per school per date. Key: (`school_id`, `calendar_date`).

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `school_id` | text | yes | Must exist in `schools.csv`. |
| `school_year` | school year | yes | |
| `calendar_date` | date | yes | Unique with `school_id`. |
| `is_school_day` | boolean | yes | `true` only when the day counts as membership. |
| `day_value` | decimal | yes | Greater than 0 and at most 1. A full day is `1`. A half day is `0.5`. Required on every row so a half day is never guessed. |

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

The date must fall inside a primary enrollment for that student and school. A row that does not is a failed file. A school day with no attendance row is not an error. How metrics treat that day is a decision in [METRICS.md](METRICS.md).

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
| `action_date` | date | no | Date of the first action or consequence. Blank if there is no action yet. Must be on or after `incident_date` when set; an earlier date fails the file. |

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

These live in the district repo. Keys are the local codes exactly as they appear in the extracts. Labels are short display text, 1 to 80 characters, with no line breaks.

### map_attendance_codes.csv

Key: `attendance_code`.

| Column | Type | Required | Rules |
| --- | --- | --- | --- |
| `attendance_code` | text | yes | |
| `label` | text | yes | |
| `counts_as` | text | yes | One of `PRESENT`, `ABSENT_EXCUSED`, `ABSENT_UNEXCUSED`, `TARDY_EXCUSED`, `TARDY_UNEXCUSED`, `PARTIAL`. |
| `absence_portion` | decimal | yes | 0 through 1. |

A `PRESENT` code has portion 0. An excused or unexcused absence typically has portion 1. `PARTIAL` is the half-day (or other partial) absence, and the portion says how much. A tardy code uses portion 0 unless this district has chosen that the tardy also removes part of the day. Views increment the tardy count from `counts_as` and apply `absence_portion` separately, so a tardy with portion 0 does not lower the attendance rate.

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

A row with `is_cancelled` false, `is_processed` false, and `is_open` false is rejected. That combination would make a referral vanish from both lists without being cancelled. Cancelled rows must have the other two flags false.

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

The mapping step is a file transform. It reads whatever files the district scheduled, writes the standard files above, and stops. The loader is the only step that touches PostgreSQL.

What follows is the usual shape of Infinite Campus, from public product knowledge. Table names, screen names, and code lists differ by state edition and by how the district configured the system. Those differences are the TO CONFIRM list. Do not treat a field name below as a column Austin's extract is known to contain.

| CampusView field | Usual Infinite Campus source | Notes |
| --- | --- | --- |
| `students.student_id` | The student number shown on the student record | Use that visible number as `student_id`, not the internal person id or a state identifier. Any other id the extract sends is kept as its own column. |
| `students.first_name`, `last_name` | The identity name fields | Which name is the legal name is local. |
| `students.gender_code` | Demographics gender, as stored | Codes are district-defined. Copy them through and map them. |
| `students.race_code` | Federal race and ethnicity fields | Which field feeds equity groups is local. |
| `schools.school_id`, `school_name` | The school record attached to a calendar | Confirm whether the extract uses a number, a code, or an internal id. The same value must appear on enrollments, calendar days, and attendance. |
| `enrollments` | An enrollment tied to a calendar: start date, end date, grade, service type | A primary service type becomes `is_primary` true. Other service types become false so they do not double-count membership. |
| `enrollments.school_year` | The school year on that calendar | Infinite Campus often stores an end year. The mapping converts it to `YYYY-YYYY`. |
| `calendar_days` | Calendar days flagged as instructional, plus the day's duration | Duration is the clue for `day_value`. A full instructional day becomes `1`. How a half day is flagged is local. |
| `attendance` | A daily attendance result, if the district can export one | Otherwise period rows are rolled up to one row per student per date before they fit this contract. The roll-up rule is local. |
| `attendance.attendance_code` | The district's attendance code | The code's status (present, absent, tardy) and excuse (excused, unexcused) are configured in Infinite Campus. Copy the code. Put the meaning in `map_attendance_codes.csv`. |
| `incidents` | A behavior incident, a behavior referral, or both | Staff in different districts use these words for different records. The mapping has to match Austin's workflow. |
| `incident_behaviors` | The coded offense (behavior event) for the offender role | One event with two codes becomes two rows. Several offenders become several incident rows. |
| `incidents.location_code`, `incident_time` | Location and time on the incident | Both are only as good as local entry. |
| `incidents.status_code` | The referral or incident status in the local workflow | Map each real status to processed, open, and cancelled. |
| `consequences` | The behavior resolution: type, dates, duration | Other resolution columns the extract sends are kept. |
| `plans` for an IEP | The special education plan: start, end, and annual review | Field names differ by state edition. |
| `plans` for a 504 | Whichever place this district stores Section 504 | This is not the same module everywhere. It may be a plan type, a program record, or something configured locally. |

Keep every column Austin's extract sends. Columns this table does not map, such as a state student identifier, a date of birth, a referral's staff name, or a school's address, phone, and principal, are kept so later production tables can be built on them.

The mapper does not invent codes and does not decide that a code is excused. It only reshapes rows. Meaning stays in the mapping tables so a code change is a district-repo edit, not a program change.

## TO CONFIRM

**Deferred, not blocking step 0.** For Austin, before the Infinite Campus mapping is written in step 1. The working text above is general product knowledge, not a claim about this district's files.

1. Which export will actually be scheduled onto SFTP: an Ad Hoc filter CSV, the data-extract utility, or another report. CampusView will not connect to the Infinite Campus database.
2. That each nightly file set is a full snapshot of every school year that should be kept (current year and the prior year, by default), not a file of changes since the previous night.
3. The student number to use as `student_id`: the number staff see on the student record, not the internal person id or a state identifier.
4. The school identifier to use as `school_id`, so the same value can be used in Superset's row-level security rules.
5. How the calendar's school year is stored, including an end-year number if that is what Infinite Campus shows, so the mapping can write `YYYY-YYYY`.
6. Whether secondary schools record period attendance, elementary schools record daily attendance, or both already have a daily result. The standard file is one row per student per date.
7. The local rule that turns periods into a full-day or half-day absence, or confirmation that Infinite Campus already calculates a daily attendance value the extract should take instead.
8. The attendance code list, and for each code whether it is present, an excused absence, an unexcused absence, an excused tardy, an unexcused tardy, or a partial day, plus the portion of the day.
9. How a half instructional day shows up on the calendar, so `day_value` can be set to `0.5` instead of `1`.
10. Which behavior record is "a referral" here: the behavior referral, the behavior incident, or both. Public material shows incidents, coded events, and resolutions; the referral workflow itself is configured per district.
11. The status values staff really use, and which ones mean not yet processed, still open, closed, or void or cancelled.
12. That one incident with several students should become one CampusView incident row per student.
13. The location code list, and whether incident time is entered often enough to support an hour-of-day heatmap.
14. The consequence code list, and which codes are exclusionary.
15. Where 504 plans are stored in this district's Infinite Campus. IEP start, end, and annual review field names also need to be confirmed; they vary by state edition.
16. Which race or ethnicity field should feed the equity groups.
17. Grade values as stored, such as `K`, `KF`, `01`, or `1`, so the grade map can match them.
18. The full list of columns the scheduled extracts will carry. The loader keeps all of them; the list tells the docs what lands in the drop folder.
