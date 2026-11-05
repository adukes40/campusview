# Decisions

Dated log of decisions already made. The plan of record is [PLAN.md](PLAN.md). Newest decisions are at the top. When a newer entry replaces an older one, the older entry stays here, marked **Superseded**, so the history is readable.

Open metric questions are not listed here. They are the Decisions for Austin list in [METRICS.md](METRICS.md). Open extract questions are the TO CONFIRM list in [DATA_CONTRACT.md](DATA_CONTRACT.md). Both lists are deferred for now and do not block step 0.

## 2026-11-05 — Nightly pull moves to 05:00, and the remote folder holds only the contract files

**What:** The one nightly pull moves from 02:00 to 05:00 in the district time zone. There is still one timer and one full pull of every contract file. Austin chose that over a second, later job for attendance alone. Reason: Infinite Campus finishes `att_day_aggregation.csv` around 3:45 AM. The other extracts export at 1:00 AM. A 05:00 run gets a fresh attendance rollup with the rest.

A full `install.sh` run writes `OnCalendar=*-*-* 05:00:00` on `cv-nightly.timer`, with `Persistent=true`. The service still runs as `CV_RUN_USER`. `install.sh --update` does not rewrite systemd units. A server that already has the timer keeps the `OnCalendar` line on disk until a full `install.sh` run, or until that line is `*-*-* 05:00:00`, followed by `systemctl daemon-reload` and `systemctl restart cv-nightly.timer`. Restarting the timer does not run the load.

The remote SFTP folder CampusView pulls from must hold only the 24 contract CSV files. Austin already pointed his district export at a clean folder like that on his fresh LXC, so no product change for filtering or pull-by-name is needed. The loader already fails a drop that has unexpected files. Filtering extras in CampusView stays out of scope while that config works.

**Why:** Austin, relayed by CampusView Engineer, 2026-11-05 about 3:36 PM ET. He picked option (a) from the scope check: move the one job to about 5:00 AM. On extras: he uses a clean remote folder with only the contract files.

**Amends:** the 02:00 timer time in 2026-11-03 "CampusView pulls extracts over SFTP, and the nightly timer is built" and in the Proposed timer detail under 2026-11-03 "The nightly timer and the drop cleanup move into step 1". A full `install.sh` run writes `OnCalendar=*-*-* 05:00:00`. `install.sh --update` does not rewrite an existing unit.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-05 about 3:36 PM ET.

**Status:** Decided. This change writes the 05:00 timer. Mark Built/Settled when Austin merges it. The six Proposed items in the 2026-11-03 SFTP entry stay Proposed; this entry does not confirm them.

**Builds on:** 2026-11-03 "CampusView pulls extracts over SFTP, and the nightly timer is built".

## 2026-11-03 — CampusView pulls extracts over SFTP, and the nightly timer is built

**What:** CampusView is an SFTP client. On the nightly timer it pulls the extracts from an SFTP server the district runs into a dated folder under `/var/lib/campusview/drop`, then validates and loads them, then deletes dated drop folders older than 7 nights. CampusView has no built-in SFTP server. PR #20, which added one, is closed unmerged. A full `install.sh` installs the nightly timer. *Amended 2026-11-05 (Austin, relayed by CampusView Engineer): the product time is 05:00. A full `install.sh` run writes `OnCalendar=*-*-* 05:00:00`. See "Nightly pull moves to 05:00" above. `install.sh --update` does not rewrite an existing unit.* Details are in [sftp-and-extracts.md](guides/sftp-and-extracts.md).

**Why:** Austin's words (Austin, relayed by CampusView Engineer, 2026-11-03 8:53 to 8:54 PM ET): "sftp will be happening on my own terms. and all this server will need to do at the omment is pull in data from an sftp server, drop the files in a fodler, then run the validotr and pull in the data." On an optional built-in SFTP server: "it does not need a built in one". On sign-in (8:56 PM ET): "ask if using pub key or password.. i do not have control over the sftp server.. so i will ahve to use a password".

**Amends:** the Proposed timer detail in 2026-11-03 "The nightly timer and the drop cleanup move into step 1" (below), "It loads from the SFTP drop folder that PR #20 settles." The timer loads from the local drop folder that the pull fills.

**Sign-in, built:** the installer asks whether the SFTP sign-in uses a key or a password, because the district may not control the SFTP server. A password is kept only in `/etc/campusview/campusview.env` (mode 600), never in git. With a key, the server generates the key pair and prints the `.pub` for the SFTP server's admin to install. The password-or-key question and the password kept only in the env file are Austin's decision.

**Proposed — built in PR #24, awaiting Austin's explicit confirmation** (CampusView Engineer's build choices; merging PR #24 did not settle them):

- The SFTP host, port, user, folder, and sign-in choice are kept in the district repo's `settings` file (`sftp_host`, `sftp_port`, `sftp_user`, `sftp_folder`, `sftp_auth`), not in the env file.
- The SFTP server's host key is pinned on the first connection (`StrictHostKeyChecking=accept-new`, saved in `/etc/campusview/sftp_known_hosts`) and checked strictly after that.
- 7 nights is a fixed product value in `nightly.sh`, not a district setting.
- A server that uses `start.sh` instead of systemd gets one printed command to run nightly, with no timer and no cron job.
- The timer and service units are written only by a full `install.sh` run, never by `install.sh --update`.
- A missing or bad map file or `cutoff_date` is recorded in `ops.load_batch` as `fault=extract`, because the column allows only `extract` or `server`. A missing district folder is recorded as `fault=server`.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03 8:53 to 8:56 PM ET, for the SFTP client, no built-in server, and key or password. CampusView Engineer for the Proposed items.

**Status:** Built (PR #24, merged by Austin 2026-11-03 11:08 PM ET). The items above are Proposed.

## 2026-11-03 — The nightly timer and the drop cleanup move into step 1, and the warehouse keeps a cutoff date

**What:** Austin moved two later-step items into step 1: "Move the nightly timer and old-data cleanup into Step 1." (Austin, relayed by CampusView Engineer, 2026-11-03 7:04 PM ET.) The loader will run nightly from a timer, and the cleanup is built with it. The email alert on a failed import stays parked.

Austin then answered the cleanup questions (Austin, relayed by CampusView Engineer, 2026-11-03 7:30 PM ET):

- (a) Keep everything dated on or after 2025-07-01. That is a fixed date, not a rolling window of school years.
- (b) If a rolling window is used later, it counts back from today's school year.
- (c) The cleanup removes old extract files from the SFTP drop. It does not remove old school years from the warehouse or the reports, and it does not remove old `ops.load_batch` rows. `ops.load_batch` keeps every row, as it does today.
- (d) Each nightly drop is a full copy, not a file of changes.
- (e) No records-retention rule applies.

The cutoff date is a district setting kept in the district repo, not a value in the product code (CampusView Engineer, following PLAN.md: "Names, schools, code values, branding, and years are supplied at install time or kept in the district repo."). This district's value is 2025-07-01. Superseded by the entry above: the loader reads `cutoff_date` from the district `settings` file and uses it only for the calendar warning.

**Amends:** the 2026-11-01 "Also decided" row "History defaults to the current school year plus one prior year, then purges." The warehouse now keeps data dated on or after the district cutoff date, set in the district repo, and is not purged by school year. Because each drop is a full copy, each good load replaces the warehouse with the drop. ARCHITECTURE.md's loader interface is updated to match.

**Proposed by CampusView Engineer (build plan, superseded by the entry above):**

- A systemd timer that `install.sh` installs, with no new components.
- It runs as the installer's run account (`CV_RUN_USER`), and the loader connects to the database as `campusview_owner`.
- It runs nightly at 02:00 in the district time zone, with `Persistent=true` so a missed night runs when the server comes back. *Amended 2026-11-05 (Austin, relayed by CampusView Engineer): the decided time is 05:00. A full `install.sh` run writes `OnCalendar=*-*-* 05:00:00`. See "Nightly pull moves to 05:00" above.*
- It loads from the SFTP drop folder that PR #20 settles. *Amended 2026-11-03: it loads from the local drop folder that the SFTP pull fills. PR #20 is closed unmerged. See "CampusView pulls extracts over SFTP, and the nightly timer is built" above.*
- An existing server gets the timer through one full `install.sh` run, because `install.sh --update` does not install systemd units.
- The timer applies only when `CV_SYSTEMD=yes`. A `start.sh` server gets one command on the done screen and no cron. See the entry above.

Austin then picked how long drop files are kept (Austin, relayed by CampusView Engineer, 2026-11-03 7:33 PM ET): "Keep 7 nights of drop files, then delete older ones." 7 as a fixed product value, not a district setting, is Proposed in the entry above.

7 nights as a fixed product value is Proposed in the entry above. The loader does not drop rows dated before the cutoff. The extract is capped at the source, and the date is used for the calendar warning.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03 7:04 PM, 7:30 PM, and 7:33 PM ET. The timer details are CampusView Engineer's proposal.

**Status:** (a) to (e) and the 7 nights decided by Austin (relayed by CampusView Engineer); confirmed when he merges this pull request. The timer details are Proposed.

**Builds on:** 2026-11-01 "No Celery for loads", and "Years kept, the Day table, and SFTP for now" (below).

## 2026-11-03 — The typed copy takes its types from column names, and every date and time is a timestamp

**What:**

- `kind` in `loader/contract.py` picks each `ic` column's type from its name. A name that ends in `timestamp`, `Stamp`, `Time`, or `date`, is `date`, or contains `Date` is a `timestamp`. A name that ends in `ID` or `Id` is an id. Three lists name the rest: `YEARS` (`endYear`, an integer), `BOOLEANS`, and `NUMBERS` (numeric). Every other column stays text.
- Every date and time column is a `timestamp`, including time-only columns such as `period.startTime`. There is no separate `date` or `time` type. Time-of-day comparisons use `::time`.
- Ids and codes stay text. An id must be 1 to 64 letters, digits, hyphens, or underscores, or it becomes NULL and warns.
- A boolean, number, year, or timestamp is valid when PostgreSQL's `pg_input_is_valid` accepts it for that type.
- Only three keys warn when blank: `school.schoolID`, `calendar.calendarID`, and `enrollment.enrollmentID` (`REQUIRED`).
- Each `ic` table is dropped and rebuilt with `CREATE TABLE ... AS` on every load, so it has no keys, indexes, or constraints.

**Who:** Recorded by CampusView Keeper from PR #14 (head 73b2651, merge commit e06c651), which Austin merged into `dev` on 2026-11-03 at 4:54 PM ET. The code is `kind` in `loader/contract.py` and `_cast` and `_rebuild` in `loader/typed.py`.

**Status:** Proposed, confirmed by merging.

**Builds on:** 2026-11-03 "The typed layer keeps the Infinite Campus names" (below).

## 2026-11-03 — Servers pin `dev` or a release tag, and updates only move forward

**What:**

- Each server's install folder is a checkout of the product repo. `CV_REF` in `/etc/campusview/campusview.env` names the branch or tag it follows: `dev` on the dev server, a release tag on production. The installer refuses `main`.
- `install.sh --update` updates a server. A branch only fast-forwards. A tag cannot move back to an older one unless the command is run with `--allow-downgrade`. The district repo is pulled fast-forward only, and if that pull fails the product does not move.
- The update refuses a checkout with local edits. It does not rewrite the server's config files, the password file, or the SFTP drop.

**Who:** Recorded by CampusView Keeper from PR #12 (commit d5b6890), which Austin merged into `dev` on 2026-11-03 at 2:52 PM ET. The code is `valid_ref`, `update_main`, and `pull_district` in `install.sh`.

**Status:** Proposed, confirmed by merging.

**Builds on:** 2026-11-03 "Release plumbing moves into step 1" and "Release flow" (below).

## 2026-11-03 — Days to action and days open start when the referral is entered

**What:** discipline days to action and days open count from the date the referral was entered into Infinite Campus, not from the incident date. That date is `behavior_incident.timestamp`. This is Austin's understanding ("I do believe"); the SIS person is asked to confirm it, and the work does not wait on that. The action-date check compares against `behavior_incident.timestamp`. A negative span is flagged on the load report, and the row is kept and counted (see the next entry).

**Who:** Austin, 2026-11-03, 12:55 PM ET, in his words: "discipline actions count from the time that they are entered into the system, not when the incident occurred. It's whenever the person or the referee put it in the system, not when the incidents took place." Then Austin, 2026-11-03, 1:16 PM ET, on the column and on days open: "I do believe that's the date it was entered. No, you would use the timestamp from the first question because that's when it was entered. Yes, I should count from the same timestamp."

**Status:** Decided by Austin; confirmed by merging PR #11.

## 2026-11-03 — The typed layer keeps the Infinite Campus names

**What:**

- The standard layer is a typed, checked copy of each `raw` table.
- It keeps the Infinite Campus table and column names. Nothing is renamed to a vendor-neutral standard layout.
- It stores real dates and numbers.
- It lives in schema `ic`, with the same owner and permissions as `raw`. For example, `raw.enrollment` becomes `ic.enrollment` (Austin, relayed by CampusView Engineer, 2026-11-03, 12:43 PM ET: "Call the schema ic.").
- Bad keys and unknown codes only warn on the load report, and loading continues. Header and column problems, missing files, and unexpected files still fail the whole batch (Austin, relayed by CampusView Engineer, 2026-11-03, 12:43 PM ET: "Bad keys or unknown codes only warn on the load report and keep loading.").
- Bad values warn. A cell with a wrong id character, a bad date, time, boolean, or decimal, a bad school year, a blank required value, or a control character in text is stored as NULL in `ic`, and the load report lists the problem. Cross-row problems also warn: two grades for one student, school, and year; an attendance date outside an enrollment; an action date before the incident date; and an impossible referral flag combination (Austin, relayed by CampusView Engineer, 2026-11-03, 12:47 PM ET: "Go with your recommendation: bad values and cross-row problems warn; empty files and bad district mapping codes stop the load.").
- A row that fails a cross-row check stays as it is in `ic`, still counts in the metrics, and is listed on the load report (Austin, 2026-11-03, 12:56 PM ET, picked on a card: "Keep the row and flag it on the load report.").
- These fail the whole load: header and column problems, missing or unexpected files, a row PostgreSQL rejects when loading `raw`, an empty `school.csv` or `calendar.csv` (zero data rows), and a bad district code-mapping file (header problem or bad code) (same answer, 12:47 PM ET).
- Only `school.csv` and `calendar.csv` stop the load when they arrive with zero data rows. Every other file, including `day.csv`, `person.csv`, and `enrollment.csv`, warns on the load report when empty, and loading continues (Austin, 2026-11-03, 1:05 to 1:13 PM ET: "day matters, but only for attendance, so it goes in the second tier, not with school and calendar. An empty school or calendar blanks every card. An empty day would blank the attendance cards and leave behavior untouched."). This replaces the earlier four-file rule. Decided by Austin; confirmed by merging PR #11.
- It is built as the next step 1 pull request after the update command.
- Superset reads it only through the reporting views.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03, 12:31 PM ET: "Yes, build the cleaned copies with the same IC names next."

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #11. The 12:56 PM ET answer on cross-row rows: Decided by Austin; confirmed by merging PR #11.

**Amends:** 2026-11-01 "Files are the only ingest" (below). Its mapping step to vendor-neutral standard layouts is replaced.

## 2026-11-03 — The raw schema holds the Infinite Campus files as they arrive

**What:** The step 1 loader (PR #10, commit 2f21b49) loads the Infinite Campus CSV files themselves, before any mapping. Each of the 24 files in `loader/contract.py` gets its own table in `raw`, named after the file (for example `raw.enrollment`), with every column stored as text. A column added to the list is added to the table. A column is never dropped. The loader creates the `ops` schema and `ops.load_batch` itself, owned by `campusview_owner`, with no grant to `campusview_reader`. The earlier design, in [ARCHITECTURE.md](ARCHITECTURE.md) and 2026-11-01 "Files are the only ingest" below, maps the vendor files to standard files first and loads those into `raw`.

**Follow-up:** 2026-11-03 "The typed layer keeps the Infinite Campus names" (above) settles what sits on top of `raw`: a typed, checked copy with the same names, where the type, key, and code checks run. It lives in schema `ic`.

**Who:** Recorded by CampusView Keeper from the code on `dev`, 2026-11-03.

**Status:** Proposed, confirmed by merging.

## 2026-11-03 — Plain HTTP on the dev server during early testing

**What:** The on-prem dev server may use plain HTTP during early testing, even though it holds real production data. It moves to HTTPS before production gets Google sign-on or real users. Production always uses HTTPS. Plain HTTP on test machines with fake data is unchanged.

**Why:** Austin's choice. He wants plain HTTP for early testing, and will move the dev server to HTTPS when production gets Google sign-on and real users.

**Tradeoff:** Plain HTTP sends logins, and the real data on the dev server, unencrypted across the district network. The CampusView Engineer flagged this risk to Austin once, and Austin accepted it.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

**Amends:** the tradeoff in 2026-11-02 "Offer nginx with HTTP or HTTPS" (below).

## 2026-11-03 — Day table rules for attendance

**What:**

- Attendance counts Day rows with the `instruction` flag set, not `schoolDay`.
- For now, every instruction day counts as 1 day (weight 1), and a half-day absence counts as a full day absent, the same as any other absence (Austin, relayed by CampusView Engineer, 2026-11-03, 10:32 AM ET). The half-day absence codes map to `absence_portion` 1. This is provisional; whether half days should ever count as half is a follow-up for the SIS person.
- A calendar with enrollments but no Day rows loads with a warning on the load report. It does not fail the file. This replaces the earlier rule that every school with an enrollment must have a calendar day.

**Not decided:** the CampusView Engineer suggests adding `dayID` and `structureID` to the Day extract query (`day.sql`), because a calendar with more than one schedule structure repeats dates.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8. The SIS person still has three follow-ups, listed in [DATA_CONTRACT.md](DATA_CONTRACT.md).

## 2026-11-03 — Release flow: dev branch, dev server, then a tag for production

**What:**

1. The builder builds and tests on its own computer and shows Austin screenshots. Screenshots never go in the public repo.
2. Changes go to the `dev` branch (`main` plus the new changes).
3. The dev server follows `dev`. It holds real district data, so Austin can see how a change will look. It follows production rules for data and access: no sandbox user, no training files, no agent access. The testing install is the builder's computer, or a separate fake-data server if Austin sets one up.
4. If it looks good, Austin merges `dev` into `main`.
5. A release tag is cut from `main`, and production moves to that tag. After each merge, the CampusView Engineer reminds Austin to cut a tag.

**Why:** Austin's words on the dev server: "ideally the dev server is going to run production data, because I need to see how it will look... If need be, I can always set up like a different server that has just the fake data in it." On tags, the CampusView Engineer explained tags against `main` and recommended tags. Austin replied: "that sounds fine, as long as you can remind me about it."

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03. Production pinning tags is the CampusView Engineer's reading of Austin's reply.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

**Amends:** 2026-11-01 "Tag-based releases" (below).

## 2026-11-03 — Release plumbing moves into step 1

**What:** Austin moved these into current work, as step 1: a product checkout on each server with a setting for the branch or tag it follows; an update command that pulls the product ref and the district repo fast-forward only, runs migrations, restarts, and leaves the env file and the SFTP drop alone; and a `dev` branch with basic CI that runs only the tests that need no data. The district folder on each server and the mappings layout in the district repo are step 1 work too. Three smaller items from the same scoping are parked in [FEATURES.md](../FEATURES.md#parking-lot).

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03 ("that sounds fine, as long as you can remind me about it").

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — Answers to the open questions on PR #8

**What:**

- **Training data is fake data.** The IC training database is completely fictional, so no PII or PHI removal is needed.
- **Training files never go in the public repo.** They are only for building, they stay on the builder's computer, and Austin can pull them again.
- **Workflow and CI.** Build and test on the builder's computer, push to Austin's test VM, then Austin updates production to `main` (*amended by "Release flow" above: the dev server holds real data, data tests run on the builder's computer, and production pins a tag*). CI on GitHub cannot use the training files, so it runs only the tests that need no data files. Data tests, including every hand-checked metric answer, run on the builder's computer and the test VM. **Rule change:** "CI must pass" and "Every metric has a test with a hand-checked answer" in the house rules, PLAN, and FEATURES are reworded to say this.
- **Keep everything he pulls in,** including SSN, medical, email, and notes if he ever sends them. None of it goes in the public repo.
- **Validated imports.** Every column the contract lists is kept, and nothing is dropped. An unknown or misspelled header fails the file with a clear report. A new column goes through the contract's change process. An email alert on a failed import is parked in [FEATURES.md](../FEATURES.md#parking-lot) for Austin to promote.
- **State id and birthdate** may appear in reporting views for now.
- **Plain HTTP** is OK on Austin's test VM, which is on-prem and not on the internet. *See also "Plain HTTP on the dev server during early testing" above.*
- **District specifics** (IC start year, extract cutoff, homeroom rule) stay in the product docs.
- **No screenshots** go in the public repo.
- **The jump box stays parked.**

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — First dashboard is an Overview

**What:** Step 2's first Superset dashboard is an Overview, modeled on screenshots of Austin's current overview page. Attendance and Behavior dashboards come later.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — Fixed contract, with a change process still to write

**What:** CSV file names, header names, and date formats stay fixed. Adding a new column or table to the contract needs a documented process. That process is not written yet. See "Changing the contract" in [DATA_CONTRACT.md](DATA_CONTRACT.md).

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — 504 status from program participation

**What:** 504 status comes from Infinite Campus `program_participation`, using the 504 program. Column details are set when the file arrives.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — Daily attendance is the homeroom mark

**What:** A student counts present for the day when marked present in homeroom, even if they leave during homeroom. Tardies come from Infinite Campus's overnight attendance calculation; CampusView does not recompute them. See [METRICS.md](METRICS.md).

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — Years kept, the Day table, and SFTP for now

**What:** Infinite Campus started in the 2025-26 school year. Keep 2025-26 and 2026-27, which matches the default history of the current year plus one prior year. Extracts are capped to dates on or after 2025-07-01. Austin will upload the Infinite Campus Day table as the calendar source; column details are set when the file arrives. Delivery is SFTP for now. A later jump box that queries Infinite Campus is logged in the [parking lot](../FEATURES.md#parking-lot), not built.

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

## 2026-11-03 — nginx shares the server, and the load report hides file text

**What:**

- **nginx (built in PR #18, merged by Austin 2026-11-03 at 9:37 PM ET).** The installer no longer takes over a server that already runs nginx sites. On a new server it removes only the untouched distro welcome page, and CampusView answers at the server's IP. If another site is enabled in `sites-enabled`, that site stays and keeps the IP. CampusView then answers only at the DNS name entered, or at this machine's hostname when the answer was an IP. If another file in `sites-enabled` or `conf.d` already owns 443 as the default, CampusView does not claim it and answers by name. The installer stops when it has no name other machines could use. `localhost` is never accepted as the server name. If `nginx -t` fails, the installer puts back its own previous CampusView site file, or removes the new one, and stops. Other sites' files are not changed. The install prints the address CampusView really answers at. A re-run with the same access mode and name keeps the earlier choice while the saved name is still the one entered or this machine's hostname.
- **Load report (built in PR #23, merged by Austin 2026-11-03 at 9:37 PM ET).** The report does not repeat file contents. An unknown or repeated header is named only when it looks like a column name: a letter or underscore, then letters, digits or underscores, 64 characters at most. Other header text is counted, not shown. A listed extract file that is a link fails with "The file is a link. Remove it." and is not read. Other links in the drop folder are ignored. A PostgreSQL row error keeps the database's one-line message unless it quotes something that is not a column of that file. A message that quotes nothing is kept. Otherwise the report says "The database rejected the file." with the line number. This fixes a headerless file printing its first line.

**Who:** Built by CampusView Engineer; Austin merged both PRs.

**Status:** Built. Merged to `dev` in PRs #18 and #23.

## 2026-11-03 — Test with IC training data and keep every column

**What:** Two changes.

- **No fake-data generator.** Tests, fixtures, and the testing install use Infinite Campus (IC) training-database extracts that Austin supplies. The first sample is 23 CSV files, each with at most 1,000 rows; that cap came from the DB Hub plugin Austin used to pull them, not from the extract. They never go in the public repo.
- **Keep every table and column.** Nothing Austin pulls in is banned or dropped, including a state student id (`stateID`), birthdate, staff names (`referralName`), a school's address, phone, and principal, and SSN, medical, email, or notes columns if he ever sends them. Each is added to the contract and kept. (Refined below: an unknown header fails the file.)

**Why:** Austin's words: "You don't need to build a fake data generator, because I can just get you whatever you need from the training database... I'd rather use actual data from the training database... do not drop any columns that I'm bringing in, please... in my production build, I will have that information in there because there will be tables and stuff that are built off of it."

**Who:** Austin, relayed by CampusView Engineer, 2026-11-03. The training database is completely fictional.

**Status:** Decided by Austin (relayed by CampusView Engineer); confirmed by merging PR #8.

**Student ids in views:** Student ids, including the state id, do not need to be excluded from reporting views, though charts usually won't show them (Austin, relayed by CampusView Engineer, 2026-11-03).

State id and birthdate may appear in reporting views for now (Austin, relayed by CampusView Engineer, 2026-11-03).

**Replaces:** "Fake data only, from one deterministic generator" in the 2026-11-01 list below, and the data contract's ban on highly sensitive identifiers.

## 2026-11-02 — Two warehouse accounts, and the schema name `ref`

**What:** The installer creates two accounts for the report database, `campusview_data`:

- **`campusview_owner`** owns the database and its schemas `raw`, `ref`, and `reporting`. The loader writes as this account in step 1.
- **`campusview_reader`** can log in and connect, and can read the `reporting` schema only. Tables and views added there later are readable automatically. It cannot see `raw` or `ref`, cannot write, and cannot create anything. Superset's data connection should use it. The installer does not create that connection.

`superset_user` now owns only `superset_meta`, and cannot connect to `campusview_data`. `django_user` owns `django_app`. The passwords are in `/etc/campusview/campusview.env`.

The middle schema is named `ref`. Upgrades rename an existing `mapping` schema to `ref` automatically.

**Why:** Superset should read finished report views, not raw loaded data. A separate owner for the loader keeps writing rights away from Superset. "Mapping" already names the step that turns vendor files into CampusView's standard files, so a schema with the same name would be confusing.

**Who:** Austin asked for the read-only account, through the CampusView Engineer's scope check. The docs keeper chose the name `ref`.

**Status:** Built and merged in the installer (PR #3).

**Alternatives:** Keep `superset_user` as the owner of `campusview_data` until step 1. Set aside: Superset would have more than read access to student data. Keep the name `mapping`. Set aside: it clashes with the transform step.

**Resolves:** Open question 5, "Warehouse database users", in [PLAN.md](PLAN.md).

## 2026-11-02 — Offer nginx with HTTP or HTTPS

**What:** `install.sh` gets an optional nginx step. nginx is a web server that sits in front of the apps and is the one thing staff connect to. The wizard offers three choices:

- **Local only.** Today's behavior. Nothing listens on the network. You reach the pages through an SSH tunnel.
- **HTTP on port 80.** Plain, unencrypted web traffic.
- **HTTPS on port 443.** Encrypted, with a self-signed certificate or one you supply. Port 80 only redirects to 443.

nginx comes from the distro's own apt repo. Superset is at `/` and Django is at `/app/`. gunicorn (Superset on 127.0.0.1:8088, Django on 127.0.0.1:8000) and PostgreSQL stay on 127.0.0.1. PostgreSQL is never exposed, and DBeaver keeps using an SSH tunnel. nginx is the only thing listening on the network. Nothing else is added: no Redis, no Docker.

A re-run shows the saved choice and asks whether to change it. The default is HTTPS on port 443 with a self-signed certificate, so pressing Enter gives a server reachable by its address. Austin accepted that default when he merged PR #5 on 2026-11-02.

**Why:** Austin wants to open CampusView by the server's address from his own computer, without an SSH tunnel. His words: "build the install to allow http or https, I will reset the ct, and rerun the new installer once you have it complete."

**Who:** Austin's decision, relayed by the CampusView Engineer.

**Tradeoff:** Plain HTTP sends logins and passwords unencrypted across the network. Austin accepted that for test machines because all data there is fake ("all data would be fake"). HTTP is for test machines with fake data only. Real student data needs HTTPS. *Amended 2026-11-03: Austin accepted plain HTTP on the on-prem dev server during early testing. See "Plain HTTP on the dev server during early testing" above.*

**Status:** Built. The installer step merged to `main` in PR #5. *Amended 2026-11-03: on a server that already runs nginx sites, CampusView no longer takes the default site. See "nginx shares the server, and the load report hides file text" above.*

**Alternatives:** Local only with an SSH tunnel for everyone. Still available as one of the three choices. Deferring the proxy until later. Set aside because Austin wants network access on his test machine now.

**Resolves:** Open question 4, "Reaching it from the network", in [PLAN.md](PLAN.md).

## 2026-11-02 — Standardize on Python 3.12 for Superset and Django

**What:** Superset 6.1.0 and Django 6.1.2 both run on Python 3.12, installed and managed with `uv`. One Python version for the whole stack. Each still has its own Python environment.

**Why:** Superset 6.1.0 supports Python 3.10 through 3.12. Django 6.1 needs Python 3.12 or newer. 3.12 is the one version both accept, so the server needs only one.

**Who:** Austin's decision, relayed by the CampusView Engineer.

**Status:** Verified. Clean installs on Debian 12, Ubuntu 24.04, and Ubuntu 22.04 ran on Python 3.12.16.

**Alternatives:** Superset on Python 3.11 with Django on Python 3.13 in a separate environment. Set aside: two Python versions to install and keep patched.

## 2026-11-02 — No Redis or Celery in v1

**What:** The v1 install has no Redis server, no Celery, and no Superset worker or beat process. The `celery` and `redis` Python libraries are installed only because Superset's package list pulls them in. Nothing starts or uses them.

**Why:** Austin wants the bare-bones install first. Plain Superset runs without them. Fewer moving parts means less to install, watch, and fix.

**What this gives up for now:** Superset features that need a worker or a cache server: async queries, scheduled alerts and reports, and a shared results cache. They are in the [parking lot](../FEATURES.md#parking-lot).

**Alternatives:** Running Redis plus a Superset worker and beat from the start, as the 2026-11-01 draft did. Set aside until the base install shows a need.

## 2026-11-02 — CampusView Engineer owns engineering

**What:** The CampusView Engineer agent builds and tests the install and the code, starting with the `install.sh` setup wizard. The docs follow what the Engineer builds and tests.

**Why:** Austin asked for one owner for engineering work so two agents don't build the same thing.

## 2026-11-01 — v1 is plain Apache Superset, with no Django customizations

**What:** Staff use plain Apache Superset: its own dashboards, charts, native filters, theme settings, roles, and row-level security. There are no custom Django pages in v1. The custom filter bar, clickable cards, modal tables with export and print, student profile pages, card admin screens, per-user preferences, and the custom view log are deferred. They come back only if using the base install shows a real need.

For each reporting page, the metric logic is a PostgreSQL view whose SQL is in this repo, and the dashboard is built in Superset. Django is installed as a default project (`startproject campusview_base`) on its own database and has no part in v1 features. Later it may be, at most, a thin front door.

**Why:** A small team should own as little custom AI-written code as possible, because custom code is what breaks and has to be maintained. Superset's roles, row-level security, and no-code dashboards are already well tested by many other users.

**Alternatives:** Django-owned pages with embedded Superset charts and guest tokens, as approved earlier the same day. Set aside for now; the deferred pieces are in the [parking lot](../FEATURES.md#parking-lot).

**Supersedes:** "Django owns the pages", the Superset-only rejection inside "Keep Superset, rather than hand-built charts", the Django-to-Superset sync and one shared query path in "Also decided", and "On-premises, in containers" (the install is now native on Ubuntu or Debian).

## 2026-11-01 — Keep Superset, rather than Metabase

**What:** Charts run in Apache Superset.

**Why:** Staff must be limited to their own schools, and the install cannot add a license fee. Superset can do row-level security on a school id without a paid tier. The platform stays on-premises.

**Alternatives:** Metabase. Rejected because row-level security there is a paid feature.

## 2026-11-01 — Keep Superset, rather than hand-built charts

**What:** The system admin builds charts in Superset. Dashboards are exported as files into the district repo.

**Why:** A new chart should not require a code release. The admin can change a chart and export it again.

**Alternatives:** Hand-built charts inside Django. Rejected because every chart would become application code.

**Partly superseded (2026-11-01, plain Superset):** This entry first said Django embeds the charts and that a Superset-only screen was rejected. The plain Superset decision reverses that: Superset is now the whole screen for v1.

## 2026-11-01 — Django owns the pages (Superseded)

**Superseded by** "v1 is plain Apache Superset" above. Kept for history.

**What it said:** Django renders the pages staff open: the filter bar, the KPI cards, the modal tables, export, print, student profiles, preferences, admin screens, and all page styling. Superset charts are embedded.

## 2026-11-01 — Files are the only ingest

**Amended 2026-11-03:** files are still the only ingest. The mapping step to CampusView's standard layouts is replaced by a typed, checked copy of each raw table that keeps the Infinite Campus names. See 2026-11-03 "The typed layer keeps the Infinite Campus names" above.

**What:** Data arrives as CSV extracts on SFTP. A mapping step turns the vendor files into CampusView's standard layouts. The loader validates every file and loads all or nothing.

**Why:** The district may not allow a direct connection to the student information system. Files work for Infinite Campus now and for another system later, with a new mapping and no change to the warehouse.

**Alternatives:** A live connection to the vendor database, or a vendor API. Rejected because the district may not permit them, and because v1 would then depend on one vendor's connection.

## 2026-11-01 — Tag-based releases

**Amended 2026-11-03:** production still pins tags, now cut after Austin checks `dev` on the dev server and merges it. The dev server follows `dev`. See "Release flow" above.

**What:** Work merges to `main` only when CI passes. A release is a tag such as `v1.3.0`. The live server pulls tags and does not pull raw `main`.

**Why:** Production should move only when a release has been cut, and CI has already installed that release. Day-to-day branch state stays off the server.

**Alternatives:** Deploying `main` directly. Rejected because a merge would reach the server before anyone had called it a release.

## 2026-11-01 — A separate district repo

**What:** Generic code lives in `adukes40/campusview`. Settings, code mappings, branding, and exported dashboards live in the private repo `adukes40/campusview-district`. Upgrades never overwrite the district repo. That repo holds no secrets.

**Why:** Nothing about one district belongs in the product. An upgrade that replaced district files would wipe local codes and dashboards. Secrets belong on the server, not in a repo.

**Alternatives:** A config folder inside the product repo, or district settings stored only on the server with no history. Rejected because the product repo would stop being generic, or because mappings and dashboards would have no history and no review.

## 2026-11-01 — No Celery for loads

**What:** The nightly load is a simple timed job on the server. It does not use Celery. (The first draft said a Django management command. Since Django has no role in v1, the exact form of the job is chosen in the loader step.)

**Why:** The load is one job: read a folder, check the files, write one transaction. A queue does not make that simpler.

**Alternatives:** A Celery task for the load. Rejected because the load would depend on a queue and a worker. As of 2026-11-02 there is no Celery in v1 at all.

## 2026-11-01 — Also decided

These were approved in the same plan. Each is the rule the build follows. Rows changed by the plain Superset decision are marked.

| Decision | Why | Alternative set aside |
| --- | --- | --- |
| Infinite Campus is the only mapping built and tested in v1. Docs explain how to write another. | One real extract is enough to prove the contract. | Building several SIS mappings up front. |
| Google sign-in now. *Open since 2026-11-01: plain Superset does not do this out of the box. **Superseded 2026-11-03:** Austin confirmed Google sign-in is a future item, not in the plan; it is parked in [FEATURES.md](../FEATURES.md#parking-lot).* | The district can use accounts it already has. | ClassLink, which is parked. Local passwords as the main sign-in. |
| History defaults to the current school year plus one prior year, then purges. *Amended 2026-11-03 (Austin, relayed by CampusView Engineer): the warehouse keeps data dated on or after a district cutoff date set in the district repo, and is not purged by school year. See "The nightly timer and the drop cleanup move into step 1" above.* | Attendance needs a last-year comparison. Unbounded history is unnecessary for v1. | Keeping every year, or keeping only the current year. |
| All metric logic lives in PostgreSQL reporting views. Charts only filter and aggregate those views. | A number is defined once. | Computing metrics in Python or inside each chart. |
| Materialize a view only after a query is proven slow. | Ordinary views stay correct for "today" without a refresh job. | Materializing everything at the start. |
| Default deny. SQL Lab and chart building only for system admin. *Changed 2026-11-01: roles and school limits now live in Superset (roles plus row-level security). The Django access list and its sync are deferred.* | Staff see only their schools. | Editing access in two places. |
| *Deferred 2026-11-01:* profile views and named exports go to an append-only log. | Named student data needs a record of who looked. | — |
| A permissions test covers every role on every place data can be reached. *Now that means Superset.* | A school boundary that is only checked by hand will be skipped. | Manual checking before each release. |
| **Superseded 2026-11-03:** no generator; tests use Infinite Campus training extracts. See the entries at the top. Fake data only, from one deterministic generator. The testing install uses the same release as production. | Tests need stable answers, and real student rows must never enter the product repo. | Hand-written spreadsheets of realistic students. |
| The testing install is also the AI sandbox: read raw, write views only in a scratch schema, ship finished views as tested SQL in the repo. | Try queries without touching production. | Letting an assistant write views on the production database. |
| Named working lists have no race column. Equity is a rate per 100 students, totals only. | Staff need equity rates without a named list sorted by race. | A race column on the open-referrals list. Small-group hiding, which is parked. |
| *Deferred 2026-11-01:* card layout as an admin setting, and per-user preferences. | — | Drag-and-drop layout, which is parked. |
| One pull request per build step, merged when CI is green. Docs for a step land in that step's pull request. | The steps in the plan stay reviewable. | Mixing several steps, or documenting them later. |
| New ideas go to the parking lot in FEATURES.md. Only Austin moves one into a step. | A mid-build idea should not change the scope of the pull request that is open. | Building the idea in the current step. |
| Agents do not edit exported Superset dashboards. Those files live in the district repo. | A chart the admin exported should stay as they exported it. | Letting an agent "clean up" a dashboard file. |
