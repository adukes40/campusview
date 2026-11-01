# Building and exporting Superset dashboards

Outline only. Step 6 fills this in, when the charts are embedded. Access rules stay in [ACCESS.md](../ACCESS.md). Metric formulas stay in [METRICS.md](../METRICS.md).

## Who builds charts

Only the system admin. SQL Lab and the chart editor are off for everyone else. Charts read the published reporting views, not the raw tables.

## What a chart is allowed to do

Sum, count, average, or divide columns the view already computed. Filter with the shared school year, school, grade, and gender fields. A chart does not re-code attendance or behavior, and a named chart does not add a race column. The equity chart uses the equity view, which has group totals and no student names.

## How a chart gets onto the page

Django reserves the slot and asks for a guest token. The token carries the person's school limits and the current filter bar. The chart uses Superset's built-in theme, with little or no custom CSS, so an upgrade is less likely to break the look.

## Export to the district repo

How the system admin exports a dashboard to files and commits those files in the district repo. Application upgrades do not overwrite them. Agents do not edit the exported files. A change is made in Superset and exported again.

## Downloads

Staff download named rows from the Django modal, which writes the audit log. Superset's own download is off for those roles. The system-admin exception stays as decision 24 in the metrics doc until Austin answers it.

## A new chart, later

The path from the plan: try the query in the testing sandbox, turn it into a reporting view with a hand-checked test, ship the view in a release, then turn the chart on. The sandbox is not production.
