# Architecture

## Flow

```
Firestore (production NoSQL)
      |  allowlisted collections, field masks
      v
extract.py  --> scrub()  --> privacy_scan() hard gate
      |  pseudonymized CSVs (no PII)
      v
Power BI semantic model  (40 tables, 104 DAX measures, Power Query M, TMDL)
      |  scheduled refresh every 6 hours
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

- A Windows scheduled task runs `extract.py` every six hours with disk, battery, and quiet hour guards, then refreshes the model.
- Test events and test registrations are excluded at the measure level (`isTest <> TRUE()`), so one operator cannot distort the numbers.

## Definitions that keep the numbers honest

- **Activated player** - completed onboarding and entered at least one tournament.
- **Completed event** - a non test tournament that reached `complete` status.
- **Check in rate** - checked in registrations divided by total registrations.
- **Return (first event cohort)** - a player who checked into a second event after their first.

Every KPI is defined in DAX, not computed ad hoc, so each headline number on the portfolio is auditable back to a measure.
