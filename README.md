# Konnect Gaming analytics stack

End to end analytics for [Konnect Gaming](https://portfolio.konnectgaming.net/), a competitive gaming platform: a Python ETL that pulls production Firestore data, a privacy fence that pseudonymizes every person before anything lands, and a Power BI semantic model of **40 tables and 104 DAX measures** that drives the dashboards and the retention analysis behind real product decisions.

This repository is a **sanitized** view of that stack. It carries the real structure and logic (the DAX measures, the date dimension, the ETL and privacy pattern) with every secret, credential, salt, and row of data removed. It is here so the engineering is verifiable, not just the finished dashboards.

**Live portfolio and dashboards:** https://portfolio.konnectgaming.net/

## What is in here

```
etl/
  extract.py          Allowlisted Firestore REST extract -> field mask -> scrub -> CSV
  privacy.py          HMAC pseudonymization, PII drop, and the privacy_scan() hard gate
  config.example.py   The collection/field allowlist (copy to config.py, gitignored)
powerbi/
  measures.dax        All 104 DAX measures, grouped by display folder
  Calendar.tmdl       The date dimension (TMDL), capped to the data window
docs/
  architecture.md     Pipeline, model, and refresh overview
```

## The privacy model (why this is safe to publish)

The whole pipeline is built around one rule: **no person leaves the database.**

1. **Allowlist.** `config.ALLOWLIST` names the exact fields pulled per collection. A field that is not listed is never fetched, so it can never reach the model. There is no email, display name, or token field in the allowlist at all.
2. **Scrub.** Every document passes through `scrub()`. Known PII keys are dropped; direct identifiers are replaced with a **salted HMAC pseudonym** (`p_...`), stable across runs but not reversible without the salt.
3. **Hard gate.** `privacy_scan()` re-checks the finished rows for anything that looks like an email, a phone number, or an un-pseudonymized id. If it finds anything, the export aborts and nothing is written.

Secrets (the salt, the GCP token, the project id) are read from environment variables at runtime. They are never committed, logged, or shipped to the model. The public Power BI report is built from the pseudonymized output, so it is a snapshot of structure and behavior, never of people.

## The analysis this supports

The measures and model back three case studies on the portfolio:

- **Data engineering** - the pipeline above, refreshed every six hours.
- **Business intelligence** - the semantic model, KPIs defined explicitly (activation, check in, repeat entrant), seven report pages.
- **Player retention** - a first event cohort showing players whose first live event drew 8+ entrants returned at 43% (n=273) versus 29% (n=97), which drove a schedule consolidation.

## Tech

Python, Firestore REST API, Power BI (DAX, Power Query M, TMDL), SQL / HogQL (PostHog), scheduled refresh.

---

Built and maintained by Jonathan Williams. Data Analytics and Business Intelligence, independent portfolio project.
