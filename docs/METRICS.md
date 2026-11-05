# Metrics

Exact definitions for the v1 dashboard list in [PLAN.md](PLAN.md). Each metric names its formula, its denominator, the edge cases, the reporting view that owns the logic, and the Superset chart that shows it. In v1 every number is a plain Superset chart: a big-number chart for a headline, a table chart for a list of students.

The body uses one working proposal for each choice so later steps have a single target. Those choices are **not approved yet**. They are listed again under [Decisions for Austin](#decisions-for-austin), which are deferred and do not block step 0. If Austin approves this document without changing an item, that item's proposal becomes the definition. Until then, do not treat the list as settled.

Views do the classifying. A chart may only sum, count, average, or divide columns the view already computed. Filter columns are `school_year`, `school_id`, `grade`, and `gender` unless a metric says otherwise. Those, and the other snake_case names below, are view column names. The views read the typed copy in schema `ic`, which keeps the Infinite Campus table and column names. [Source columns in `ic`](#source-columns-in-ic) says where each input comes from. "The filter" means the four Superset native filters, after row-level security has already limited the schools.

The preview's sparklines and the "versus last year" text on the headline numbers are parked. They are not metrics in v1. The absence number does name the day it counts. That part is in scope.

A hand-checked test, when the views are built, uses the Infinite Campus training extracts Austin supplies and a known answer for each formula below. The test reads the view. It does not reimplement the formula in Python.

## Shared rules

**Who is enrolled on a date.** A student is enrolled at a school on a date when a primary enrollment covers that date: `ic.enrollment."startDate"` is on or before the date, and `"endDate"` is blank or on or after the date. Non-primary enrollments do not create membership and do not count in any denominator.

**Membership day.** An enrolled student on a school day: an `ic.day` row with `instruction` true, not `schoolDay` (Austin, relayed by CampusView Engineer, 2026-11-03). The day's weight is `day_value`. For now, every instruction day counts as 1 day, so every weight is 1, and a half-day absence code has `absence_portion` 1, so it counts as a full day absent (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET). The formulas below still accept other values in case half days are counted as half later.

**No calendar days.** A school with enrollments but no calendar days in the year loads with a warning on the load report. Its students have no membership days there, so they add nothing to any rate until calendar days arrive.

**Present and absent portions.** For a membership day:

- If there is an attendance row, `absence_portion` comes from that code's map, and `present_portion` is `1 - absence_portion`.
- If there is no attendance row, the working proposal counts the day as present: `absence_portion` 0, `present_portion` 1.
- A tardy adds 1 to the tardy count. It changes the portions only when its mapped `absence_portion` is greater than 0.

**This district's daily rule** (Austin, relayed by CampusView Engineer, 2026-11-03). A student counts present for the day when marked present in homeroom, even if they leave during homeroom. Tardies come from Infinite Campus's overnight attendance calculation. CampusView does not recompute them. It maps the codes that calculation produces.

**Year to date.** Membership days in the selected school year whose date is on or before today. Today is the current date in the district time zone from the district config. A future day in the calendar is not in the rate. When the selected year is entirely in the past, every membership day in that year is included.

**Cancelled referrals.** A status mapped `is_cancelled` is dropped inside the behavior views. It appears in no count, list, average, or equity numerator.

**Grade and gender.** Grade is the enrollment grade. Gender is the mapped label. A blank gender is kept, stays in "All", and matches no specific gender filter. Within one student, one school, and one school year, the contract allows only one grade.

**One school year at a time.** The filter always has a single school year. Comparison to last year is a second pass over the prior year with the same school, grade, and gender filters. It is not a second definition of the rate.

**Pooled rates.** A rate that covers several schools is total numerator divided by total denominator. It is not the average of the school rates, and it is not the average of the student rates.

### Source columns in `ic`

The views read `ic`, not `raw`, and use the Infinite Campus names (PR #14). Each table below is in `loader/contract.py`. Quote the mixed-case names in SQL, for example `ic.enrollment."startDate"`. Items marked TO CONFIRM are open in [DATA_CONTRACT.md](DATA_CONTRACT.md).

| Meaning in this document | Table and columns in `ic` | Notes |
| --- | --- | --- |
| Student | `ic.person`, key `personID` | Every student join uses `personID`. The id staff see is `studentNumber` (TO CONFIRM 3). |
| Name, gender, race | `ic.identity` (`firstName`, `lastName`, `gender`, `raceEthnicity`, `raceethnicityFed`), from `ic.person."currentIdentityID"`; also `ic.identity_race_ethnicity` and `ic.race_ethnicity` | Which race field feeds equity is TO CONFIRM 16. |
| School (`school_id`) | `ic.school."schoolID"`, reached through `ic.calendar."schoolID"` | TO CONFIRM 4. |
| School year (`school_year`) | `ic.calendar."endYear"` and `ic.enrollment."endYear"`, integers | The view turns the end year into `YYYY-YYYY` (TO CONFIRM 5). |
| Enrollment and grade | `ic.enrollment` (`personID`, `calendarID`, `grade`, `serviceType`, `startDate`, `endDate`) | Which `serviceType` value is primary is TO CONFIRM. `grade` stays text. |
| School day | `ic.day` (`calendarID`, `date`, `instruction`) | `day_value` has no column. It is 1 for now. |
| Attendance mark and code | `ic.attendance` (`personID`, `calendarID`, `date`, `excuseID`, `status`), `ic.attendance_excuse` (`code`), `ic.att_day_aggregation` | Which columns carry the homeroom mark is open in DATA_CONTRACT. |
| Referral (incident) | `ic.behavior_incident` (`incidentID`, `calendarID`, `location`, `status`, `timestamp`) | The student is `ic.behavior_role."personID"`, through `ic.behavior_event`. |
| Behavior label | `ic.behavior_event."typeID"` to `ic.behavior_type` (`code`, `name`) | |
| Consequence and action date | `ic.behavior_resolution` (`roleID`, `typeID`, `discassignDate`) to `ic.behavior_res_type` | |
| 504 plan | `ic.program_participation` with `ic.program` | |
| IEP | Probably `ic.plan` with `ic.plan_type` | TO CONFIRM 15. |
| Incident date and time | `ic.behavior_incident.timestamp` | When the incident occurred (Austin, 2026-11-05). Not when a person logged the entry. The extract has no entry-time column. |
| Plan review date | No column in today's contract | Open. |

Every date and time column in `ic` is a `timestamp`. A time-only value, such as `ic.period."startTime"`, is stored on a placeholder date such as 1900-01-01. Compare times of day with `::time`, for example `"startTime"::time`, never the whole timestamp. Compare calendar days with `::date`.

### Worked attendance example

For now, every instruction day counts as 1 day, and a half-day absence counts as a full day absent (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET).

A student has 101 membership days, each of weight 1. One of them was a half instructional day, and the student was absent that day. The student also has 4 full-day absences and one half-day absence code on another day.

- Membership = 101
- Absence equivalents = 4 + 1 (the half-day absence code counts as a full day) + 1 (the absence on the half instructional day counts as a full day) = 6
- Present equivalents = 101 - 6 = 95
- Attendance rate = 95 / 101 = 94.1%

The half instructional day counts as a whole membership day, and each half-day absence counts as a whole day absent.

## Overview headline numbers

Six headline numbers, each a Superset big-number chart on its view. The rows behind a number can be a Superset table chart on the same view, with the same filters. A table of named students has no race column. The first draft's clickable cards that open a modal table, with CSV export and print, are parked.

### Year-to-date attendance rate

| | |
| --- | --- |
| Shows | A percent, one decimal. |
| View | `reporting.v_attendance_student_day` |
| Formula | Sum of `present_portion × day_value`, divided by sum of `day_value`, among rows in the filter and in the year-to-date window. Multiply by 100 for display. |
| Denominator | Sum of `day_value` for those membership days. If the denominator is 0, the chart shows no number, not zero percent. |
| Table columns | Student id, name, school, grade, membership days, absence-day equivalents, attendance percent. One row per student. Days are the sums of that student's filtered day rows. |

Mid-year enrollment: days before `ic.enrollment."startDate"` and after `"endDate"` are not membership. A student who arrives in October is rated only on days from October on. A student enrolled at two schools in the year contributes days to each school; a single-school filter sees only that school's days.

### Absent on the last school day

| | |
| --- | --- |
| Shows | A count of students. The chart title names the day, for example the weekday and date, when every selected school shares one last day. When the schools differ, the title says that each school uses its own last day. |
| View | `reporting.v_last_school_day_absence` |
| Last school day | For each school, the latest `ic.day` date with `instruction` true in the selected year that is on or before today. Schools with different calendars can have different dates. |
| Who counts | A student enrolled on that school's last day whose `absence_portion` that day is 0.5 or greater. |
| Denominator | None. This is a headcount. |
| Table columns | Student id, name, school, grade, the date counted, absence portion. |

The view is an ordinary view, because the date depends on today. No attendance row on that day means present, so the student is not in the list (same unmarked-day rule as the rate).

### Referrals not yet processed

| | |
| --- | --- |
| Shows | A count of referrals. |
| View | `reporting.v_incident`, rows with `is_processed` false. Cancelled rows are already gone. |
| Formula | Count of those rows in the filter. The incident's school, year, grade, and the student's gender are the filter columns. Grade is the student's grade on their primary enrollment at that school in that year. |
| Denominator | None. |
| Table columns | Student id, name, school, grade, behavior labels, days open. No race. |

"Not yet processed" is narrower than "open". A referral that has been acted on and is still open is not in this count. It is on the open list.

### Average days to action

| | |
| --- | --- |
| Shows | A number, one decimal. The plan's name for this number is average days to resolve or action. The working definition uses the first action. |
| View | `reporting.v_incident`, rows where `days_to_action` is not null. |
| Formula | Average of `days_to_action`. The clock starts when a person logged the entry, not when the incident occurred (Austin, 2026-11-03, 12:55 PM ET). `ic.behavior_incident.timestamp` is when the incident occurred, not that log time (Austin, 2026-11-05). The extract has no entry-time column, so this metric stays unbuilt. Do not substitute `timestamp`. The action date, once the metric is built, is `ic.behavior_resolution."discassignDate"`. |
| Denominator | The count of referrals in the filter that have an action date. Referrals with no action yet are excluded, not treated as still running. |
| Edge | Same-day action is 0, once an entry-time column exists. The loader does not flag an action date before `behavior_incident.timestamp`. |
| Table columns | Student id, name, school, incident date, action date, days. |

### Active 504 plans

| | |
| --- | --- |
| Shows | A count of plans, plus a second count expiring in 30 days. |
| View | `reporting.v_plan`, rows with `plan_type` `504` and `is_active` true. |
| Active | Status maps to active, `startDate` is on or before today, and `endDate` is blank or on or after today (`ic.program_participation` for a 504). |
| School | The school of the student's primary enrollment in the selected year. A plan whose student has no primary enrollment in that year is not on the view. |
| Expiring | Among the active rows, the review due date falls from today through the next 30 days, including today. If the review due date is blank, `endDate` is used the same way. No file in `loader/contract.py` has a review-date column today. If both are blank, the plan is not expiring. |
| Denominator | None. Two active 504s for one student count as two. |
| Table columns | Student id, name, school, grade, plan type, review due date, end date, and whether it expires in 30 days. |

### Active IEPs

Same definition as active 504 plans, with `plan_type` `IEP`. It is its own number and its own expiring count.

## Overview charts

These are Superset charts on the dashboard. They read the view named here and use the same native filters and the same row-level security.

### Top 10 referred students

| | |
| --- | --- |
| View | `reporting.v_referrals_by_student` |
| Formula | `referral_count` is the count of incident rows for that student, school, and year. The chart sorts by `referral_count` descending, then `student_id` ascending, and keeps 10 rows. |
| Ties | Stop at 10. The student id breaks ties so the list does not change between loads. |
| Columns on the chart | Name, school, referral count. No race. |

### Top 10 behavior types

| | |
| --- | --- |
| View | `reporting.v_behavior_event` |
| Formula | Count of rows per behavior label. Horizontal bars, largest first, 10 labels. Tie-break is the label, A to Z. |
| Grain | One coded behavior, not one referral. A referral with two codes adds one to each bar. A referral with no behavior row adds to neither. |

### Open referrals

| | |
| --- | --- |
| View | `reporting.v_open_referral` |
| Who is on it | Incident rows with `is_open` true. That includes not-yet-processed referrals and referrals that have an action and are not closed. |
| Days open | Calendar days from when a person logged the entry through today (Austin, 2026-11-03, 1:16 PM ET). `behavior_incident.timestamp` is when the incident occurred, not that log time (Austin, 2026-11-05). The extract has no entry-time column, so this column stays unbuilt. |
| Color | Under 18 days, plain. 18 through 29, warning. 30 or more, strong warning. Cutoffs are a display rule from the approved preview. |
| Sort | Days open descending, then student id. |
| Columns | Name, school, grade, behavior labels, days open. No race. |

## Behavior dashboard

### Trends by month, grade, and location

| | |
| --- | --- |
| View | `reporting.v_behavior_event` |
| Formula | Count of behavior rows. By calendar month of `ic.behavior_incident.timestamp`, when the incident occurred (Austin, 2026-11-05; see [Source columns in `ic`](#source-columns-in-ic)). By grade. By location label. A blank location is its own bar, labeled unknown, not dropped. |
| Denominator | None. These are counts. |

### Heatmap of location by time of day

| | |
| --- | --- |
| View | `reporting.v_behavior_event` |
| Formula | Count of behavior rows by location label (`ic.behavior_incident.location`) and hour of `ic.behavior_incident.timestamp` (0 through 23) in the district time zone. That column is when the incident occurred (Austin, 2026-11-05). |
| Missing time | Rows with no time are left off the heatmap. They remain on the month, grade, and location charts. |

### Consequences

| | |
| --- | --- |
| View | `reporting.v_consequence` |
| Formula | Count of consequence rows by consequence label, in the filter. `is_exclusionary` is a column so the chart can split suspension-style consequences from the rest without a second definition. |
| Link | A consequence counts even when its referral is closed. Cancelled referrals never reach this view. |

### Repeat referrals

| | |
| --- | --- |
| View | `reporting.v_referrals_by_student`, column `is_repeat` |
| Formula | `is_repeat` is true when `referral_count` is 2 or more. The chart shows how many students fall in each count bucket: 1, 2, 3, 4, and 5 or more. |
| Grain | Incident rows, so a referral is counted once even if it has two behavior codes. |

### Equity

| | |
| --- | --- |
| View | `reporting.v_equity_referral_rate` |
| Shows | Rate per 100 students, one bar or row per equity group. Totals only. |
| Formula | For each group, `incident_count / student_count × 100`. |
| Numerator | Incident rows (referrals), not behavior rows, for students in that group. |
| Denominator | Distinct students with any primary enrollment at that school during the selected year, in that grade and gender cell. A student enrolled for one week counts once. They are not weighted by days. |
| Columns | `school_id`, `school_year`, `grade`, `gender`, `equity_group_label`, `student_count`, `incident_count`. No student id, no name, no raw race code. |
| Combining cells | When the gender filter is All, the chart sums `incident_count` and sums `student_count` across genders, then divides. It does not average the rates. Same for several schools or several grades. |
| Small groups | v1 shows every group. Hiding small groups is parked. |
| Grade on this view | The grade on the student's primary enrollment at that school in that year. The contract already allows only one such grade. |

## Attendance dashboard

The year-to-date rate number lives on Overview. The Attendance dashboard uses the same rate definition for its trend.

### Monthly trend versus last year

| | |
| --- | --- |
| View | `reporting.v_attendance_month` |
| Formula | For each month, sum of present-day equivalents divided by sum of membership-day equivalents. Same portions and the same unmarked-day rule as the year-to-date rate. The month is bounded by that calendar month, not by "today", except the current month, which stops at today. |
| Last year | The same months in the previous school year, same school, grade, and gender filters, using whoever was enrolled then. This is not a follow-up of this year's students. |
| Missing history | If the warehouse has no rows for the prior year, for example in the first school year after the district cutoff date, the prior-year line has no rows. The chart shows the current year alone. |
| Columns | `school_id`, `school_year`, `month`, `grade`, `gender`, `membership_days`, `present_days`. The chart divides. It does not redefine a day. |

### Chronic absenteeism rate by grade

| | |
| --- | --- |
| View | `reporting.v_chronic_student_school` |
| A student is chronic | At that school, in that year, absence-day equivalents are at least 10% of membership days, and membership days are at least 10. Excused and unexcused absences both count. Tardies count only through their absence portion. |
| Rate | Students with `is_chronic` true, divided by students on the view in that grade, within the filter. The 10-day minimum means a student with fewer than 10 membership days at that school is not in the denominator. |
| Across schools | Status is judged inside one school. When the filter includes two schools, a student who is chronic at both is counted in each school's students and can appear twice in a district total. |
| Table of students, if added later | This v1 chart has no headline number. If a table of students is added, it uses this view and has no race column. |

### Unexcused absences

| | |
| --- | --- |
| View | `reporting.v_attendance_student_day`, column `unexcused_absence_portion` |
| Formula | Sum of `unexcused_absence_portion × day_value` in the filter and the year-to-date window. |
| What counts | Only codes mapped `ABSENT_UNEXCUSED`, plus a `PARTIAL` code does not count here unless the district maps it as unexcused. The working proposal: only `ABSENT_UNEXCUSED` fills `unexcused_absence_portion`. Partial absences still affect the attendance rate through `absence_portion`. |
| Denominator | Not used for the headline total. The column `day_value` is on the same view if a rate is charted later, and that rate would use the year-to-date membership denominator. v1 shows the day total, by month, from `v_attendance_month`'s unexcused column as well. |

`v_attendance_month` carries `unexcused_absence_days` computed with the same rule, so the monthly chart does not rebuild it.

### Tardies

| | |
| --- | --- |
| View | `reporting.v_attendance_student_day`, columns `unexcused_tardy_count` and `excused_tardy_count` |
| Headline | Sum of `unexcused_tardy_count`. One attendance row mapped `TARDY_UNEXCUSED` adds 1. This is a count of days with an unexcused tardy, not a rate. |
| Excused | `excused_tardy_count` is on the view and is not in the headline. |
| Rate effect | None, unless that code's `absence_portion` is greater than 0, in which case the attendance rate already reflects the portion. |

## Student profile (deferred)

**Deferred 2026-11-01:** student profile pages are parked with the other custom Django pages. This section is kept for when the item is revisited.

The profile is not its own formula. For the selected year it shows, through the shared query path:

- From `v_attendance_student_day`, that student's membership, absences, rate, unexcused absences, and tardies.
- From `v_incident`, `v_behavior_event`, and `v_consequence`, that student's referrals, behaviors, and consequences.
- From `v_plan`, that student's plans, review date, and expiring flag.

Opening the profile would write a view log (also parked). A student with no primary enrollment in a granted school, in the selected year, is not shown.

## What each view computes

Short form of the columns that carry decisions. Filter columns are omitted here.

| View | Decision columns |
| --- | --- |
| `v_attendance_student_day` | `day_value`, `absence_portion`, `present_portion`, `unexcused_absence_portion`, `unexcused_tardy_count`, `excused_tardy_count`, `has_mark` |
| `v_attendance_month` | Sums of those day columns by month |
| `v_chronic_student_school` | `membership_days`, `absence_days`, `is_chronic` using the 10% and 10-day rules |
| `v_last_school_day_absence` | The per-school last day, and only students at or above portion 0.5 |
| `v_incident` | `is_processed`, `is_open`, `days_to_action`, `days_open`. Cancelled omitted |
| `v_behavior_event` | One row per behavior code, with location and hour. Cancelled omitted |
| `v_referrals_by_student` | `referral_count`, `is_repeat` (2 or more) |
| `v_open_referral` | Open incidents only, with `days_open` |
| `v_consequence` | Mapped label and `is_exclusionary`. Cancelled omitted |
| `v_plan` | `is_active`, `expires_in_30_days`, school from the primary enrollment |
| `v_equity_referral_rate` | `student_count`, `incident_count` by equity group. No names |

## Decisions for Austin

**Deferred, not blocking.** Austin will answer these later. They do not block step 0 or the base install. Each needs an answer before the view it affects is built.

Working proposals are in the body above. Each item below is the choice that would change a number or a screen. Extract questions that block the mapping tables and the views are the TO CONFIRM list in [DATA_CONTRACT.md](DATA_CONTRACT.md), not here.

1. **No attendance mark.** When a student is enrolled on a school day and the file has no attendance row, v1 counts that day as present. Confirm, or say the day should be left out of both the numerator and the denominator.

2. **Pooled rate.** The year-to-date attendance rate is total present-day equivalents divided by total membership-day equivalents, so a larger school counts more than a smaller one. Confirm, or say you want the average of each student's own rate.

3. *Answered for now (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET): every instruction day counts as 1 day, and a half-day absence counts as a full day absent, the same as any other absence. Provisional. Whether half days should ever count as half is a follow-up for the SIS person in [DATA_CONTRACT.md](DATA_CONTRACT.md).* The text below is the earlier proposal, set aside for now. **Half days.** A calendar day with day value 0.5 counts as half a membership day. An absence code with portion 0.5 counts as half a day absent. A full absence on a half day counts as 0.5. Confirm this matches how the district records half days.

4. *Partly answered (Austin, relayed by CampusView Engineer, 2026-11-03): tardies come from Infinite Campus's overnight calculation; the effect of each tardy code on the rate is still set in the code map.* **Tardies and the rate.** A tardy does not lower the attendance rate unless that code's absence portion is greater than zero. Confirm.

5. **Last school day.** "Absent on the last school day" uses each school's own latest school day on or before today, in the district time zone. If the selected schools do not share that date, the chart title says so and still counts each student on their own school's date. Confirm, or say you want one shared date for the whole filter.

6. **Who counts as absent that day.** A student counts when that day's absence portion is 0.5 or more. Confirm, or say any portion greater than zero, or a full day only.

7. **Chronic absenteeism.** A student is chronically absent at a school when absence-day equivalents are at least 10% of membership days at that school, excused and unexcused both count, and the student has at least 10 membership days there. Confirm this is the rule you want, including the 10-day minimum.

8. **Chronic across schools.** v1 judges chronic status inside one school. A student who split the year between two schools is judged at each school and can be counted twice when both schools are selected. Confirm, or say a district view must count each student once.

9. **Two referral lists.** "Not yet processed" means the status map says there has been no action. "Open" means the status map says the referral is not closed, including ones already acted on. The overview headline number counts the first. The list shows the second. Confirm these are two different lists in your office, or say they should be the same list.

10. **Days to action.** *Clock answered (Austin, 2026-11-03, 12:55 PM ET): days to action and days open count from when a person logged the entry, not from when the incident occurred. Column corrected (Austin, 2026-11-05): `behavior_incident.timestamp` is when the incident occurred. The extract has no entry-time column, so both metrics stay unbuilt. The loader does not flag an action date before that timestamp.* Still open, once an entry-time column exists: whether the clock should stop on the closed date instead, and whether referrals that are still waiting should count.

11. **Days-open colors.** The open list colors days at 18 and at 30, matching the approved preview. Confirm those cutoffs, or give different ones, or say no color until you choose.

12. **Top 10 ties.** The top 10 lists stop at 10 rows. A tie breaks by student id or by behavior label, A to Z, so the rows do not change between loads. Confirm, or say everyone tied at the cutoff should appear.

13. **What gets counted.** Student referral counts, the open list, days to action, repeat referrals, and the equity numerator count incident rows, so one referral counts once. Behavior-type bars, location, month, grade, and the heatmap count behavior rows, so one referral with two codes counts on two bars. Repeat means 2 or more incidents in the selected year. Confirm.

14. **Cancelled referrals.** A status mapped as cancelled is left out of every behavior metric. Confirm the district has a void or cancelled status to map this way.

15. **Equity.** The rate is incidents per 100 students, by race or ethnicity group from the mapping table. The denominator is distinct students with a primary enrollment at that school at any point in the selected year. Totals only, with no small-group hiding in v1. Confirm the group, the numerator, and the "any point in the year" denominator.

16. **Expiring plans.** "Expiring in 30 days" uses the review-due date when it is present, otherwise the plan end date. The window is today through 30 days from today, in the district time zone. Confirm which date the 504 team and the IEP team each use.

17. **Which school a plan counts at.** An active plan counts at the school of the student's primary enrollment for the selected year. A plan for a student with no primary enrollment in that year is hidden. Confirm.

18. **Two active plans.** A plan is active when its status maps to active, it has started, and it has not ended. Two active plans of the same type for one student count as two. Confirm.

19. **Grade native filter.** The Superset native filter for grade offers All, or one grade (K, 1, 2, and so on through 12), read from the `grade` column on each view. The preview's bands (K-5, 6-8, 9-12) are not in v1. A student may have only one grade per school per year; otherwise the enrollment file is rejected. Confirm a single-grade native filter is enough, and confirm that a mid-year grade change does not need to be represented.

20. **Blank gender.** A gender code that is not in the gender map is a warning on the load report, and loading continues (Austin, relayed by CampusView Engineer, 2026-11-03). A blank gender is allowed, stays inside All, and is not counted under a named gender. Confirm blanks should be allowed.

21. **Unexcused absences and tardies.** The unexcused total sums portions for codes mapped as unexcused absences only. The tardy headline counts unexcused tardies. Excused tardies are stored separately and are not in that headline. Confirm.

22. *Note (Austin, relayed by CampusView Engineer, 2026-11-03): history is 2025-26 and 2026-27. Infinite Campus started in 2025-26, so 2025-26 has no prior-year line.* **Last-year line.** The monthly attendance trend compares each month with the same month in the prior school year, using the students enrolled in each year. It does not follow this year's students backward. If history is set to the current year only, the prior-year line is empty. Confirm.

23. **Heatmap buckets.** The heatmap is location by clock hour. Referrals with no time are left off the heatmap and still count on the other behavior charts. Confirm hourly buckets are the breakdown you want.

24. **Downloads in plain Superset.** In v1, Superset's own CSV download is on for the system admin only. District admins and school admins can view table charts but cannot download them. There is no CampusView view or export log in v1; the custom Django export and its log are parked. Confirm, or say which roles should be able to download from Superset, and whether downloads need to be logged.

25. **One time zone.** A single district time zone, set in the district config, defines today, the last school day, the 30-day window, and the heatmap hour. Confirm one zone is enough.
