# Architecture

## Flow

```
Firestore (production NoSQL)
      |  allowlisted collections, field masks
      v
extract.py  --> scrub()  --> privacy_scan() hard gate
      |  pseudonymized CSVs (no PII), export scheduled every 6 hours
      v
Power BI semantic model  (40 tables, 104 DAX measures, Power Query M, TMDL)
      |  refreshed from the latest export on demand
      v
Dashboards (7 pages) + Publish to web (public snapshot)
```

## Extract

- Reads the Firestore REST API with a short lived access token from the environment.
- Pulls only the fields in `config.ALLOWLIST` (a field mask on every request), so unlisted fields never leave the database.
- Pages at 300 documents per request and flattens Firestore's typed value wrappers into plain rows.
- Every document is run through `scrub()` before it is kept.

## Privacy fence

- `scrub()` drops `PII_KEYS` and replaces identifier fields with a salted HMAC pseudonym.
- `privacy_scan()` is a final gate over the whole result set. Emails, phone numbers, or un-pseudonymized ids abort the export; no clean scan, no file.
- The pseudonym salt is HMAC keyed and lives only in the environment. Pseudonyms are stable across runs (so joins still work) but not reversible.

## Semantic model

- 40 tables in a star schema around the core facts (users, tournaments, registrations, matches) plus daily/weekly rollups (product metrics, feature usage, social).
- 104 measures live in a single measures table (`KPIs`), grouped into 10 display folders: Players, Events, Matches, Notifications, Product Health, Scene, Features, Social, Social Graph, DMs.
- Transforms are standardized through one shared Power Query M function; the whole model is versioned as TMDL text, so changes are diffable and code reviewable.
- `Calendar` is a calculated date dimension capped to the data window, so continuous date axes do not trail past the last real day.

## Refresh

- A Windows scheduled task is set to run the production version of `extract.py` every six hours. It does not start on battery, and it skips a run in the evening event window (17:30 to 22:00 Eastern) or when free memory is low, logging each of those skips. In practice a full export lands about once a day, with gaps of a few days at times.
- The Power BI model is refreshed from the latest export on demand in Power BI Desktop, and the published report is a snapshot of that refresh.
- Events and registrations flagged as tests are excluded at the measure level (`isTest <> TRUE()`). An event that is not flagged at the source is still counted.

## Definitions that keep the numbers honest

- **Activated player**: completed onboarding and entered at least one tournament.
- **Completed event**: a non test tournament that reached `complete` status.
- **Check in rate**: checked in registrations divided by total registrations.
- **Return (first event cohort)**: a player who checked into a second event after their first. Players count once their first event is at least 14 days old, and test events and staff accounts are excluded.

Every dashboard KPI is defined in DAX, not computed ad hoc, so each dashboard number is auditable back to a measure. The first event cohort is a separate analysis run on the same pseudonymized export; it is not one of the 104 measures.
