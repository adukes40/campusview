# Building and exporting Superset dashboards

Outline. Step 2 fills this in, with the first dashboard. In v1, Superset dashboards are the whole screen staff use. Access rules stay in [ACCESS.md](../ACCESS.md). Metric formulas stay in [METRICS.md](../METRICS.md).

## Who builds charts

Only the system admin. SQL Lab and the chart editor are off for everyone else. Charts read the published reporting views, not the raw tables.

## What a chart is allowed to do

Sum, count, average, or divide columns the view already computed. A chart does not re-code attendance or behavior, and a table chart of named students does not add a race column. The equity chart uses the equity view, which has group totals and no student names.

A single headline number is a big-number chart. A list of students is a table chart.

## Native filters

Every dashboard gets the same native filters: school year, school, grade, and gender. Filters only narrow what the person's row-level security already allows. Charts use Superset's own theme settings, with no custom CSS.

## Export to the district repo

How the system admin exports a dashboard to files and commits those files in the district repo. Application upgrades do not overwrite them. Agents do not edit the exported files. A change is made in Superset and exported again.

## Downloads

Superset's own CSV download is on for the system admin only. Whether district admins and school admins may download from a table chart, and whether downloads need to be logged, is decision 24 in [METRICS.md](../METRICS.md). The custom Django export with a view log is parked.

## A new chart, later

The path from the plan: try the query in the testing sandbox, turn it into a reporting view with a hand-checked test, ship the view in a release, then build the chart. The sandbox is not production.
