# Assumptions & Edge Cases
**Project:** Real-time Attribution Pipeline & Dashboard
**Dataset:** `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
**Target Dataset:** `luminous-return-502518-t7.ga4_attribution`

---

## Attribution Assumptions

| Decision | Choice Made | Rationale |
|---|---|---|
| **Lookback window** | 30 days | Mirrors GA4's default attribution window; balances data completeness vs. noise from stale sessions. |
| **Conversion event** | `event_name = 'purchase'` with a non-null `transaction_id` | Ensures only confirmed transactions are counted; prevents partial checkouts from inflating metrics. |
| **First-Click tie-breaker** | Earliest `event_time` ASC for a given `user_pseudo_id + transaction_id` | Deterministic; if two touchpoints share the same microsecond timestamp, the first row returned by BigQuery ordering is used. |
| **Last-Click tie-breaker** | Latest `event_time` DESC, preferring non-direct sources | Mirrors GA4's "last non-direct click" convention — `(direct) / (none)` is excluded if any prior non-direct touchpoint exists within the window. |
| **Identity resolution** | `user_pseudo_id` (cookie-based) only | No cross-device stitching. A user on mobile and desktop is treated as two separate users. In production, a `user_id` (logged-in) join would be the first upgrade. |
| **Revenue attribution** | 100% of `purchase_revenue` credited to the single attributed channel | Single-touch models by definition. No fractional revenue splitting. |

---

## Data & Pipeline Edge Cases

### Duplicate Events
- **Risk:** The streaming insert script or any upstream replay could insert the same event twice.
- **Handling:** Two-layer defence:
  1. `row_ids` passed to `insert_rows_json` trigger BigQuery's best-effort streaming deduplication.
  2. `stg_events.sql` applies `ROW_NUMBER() OVER (PARTITION BY user_pseudo_id, event_timestamp, event_name)` and keeps only `row_num = 1`.

### Events Arriving Out of Order
- **Risk:** A touchpoint timestamp could arrive after the conversion timestamp due to network delays.
- **Handling:** The attribution CTAs join on `e.event_time <= c.conversion_time`. Late-arriving touchpoints that technically fall before a past conversion will only be captured on the next full `dbt build` refresh. Accepted trade-off for a batch/near-real-time model.

### NULL or Missing Channel Data
- **Risk:** GA4 direct traffic has `source = NULL` and `medium = NULL`.
- **Handling:** `stg_events.sql` applies `COALESCE(source, '(direct)')` and `COALESCE(medium, '(none)')` so no nulls propagate to the marts. These values follow GA4's own convention.

### Purchases with No Prior Touchpoint
- **Risk:** A user converts with no touchpoint in the 30-day lookback window (e.g., first-ever session is a purchase).
- **Handling:** The `JOIN` in both mart models is an `INNER JOIN` — conversions with zero qualifying touchpoints are excluded from the attribution output rather than attributed to `(direct)`. This is intentional: an unattributable conversion is better excluded than incorrectly attributed.

### GA4 Public Dataset Date Range
- **Risk:** The `events_*` wildcard table spans `20201101` to `20210131`. Querying without a suffix filter scans ~1 GB+ unnecessarily.
- **Handling:** `_TABLE_SUFFIX BETWEEN '20201201' AND '20210131'` in `stg_events.sql` limits scans to 2 months of data, keeping each `dbt build` under ~100 MB processed.

### Streaming Table Not Existing
- **Risk:** Dashboard queries `streamed_events` before the streaming script has ever been run.
- **Handling:** `streaming_demo.py` calls `create_table_if_not_exists()` on startup. The Streamlit dashboard wraps the live-events query in a `try/except` and falls back to mock data silently, keeping the UI functional.

### dbt Test Failures
- **Risk:** A re-run or bad streaming insert creates a duplicate `transaction_id` in a mart.
- **Handling:** `dbt build` (not `dbt run`) is the prescribed command. Tests run alongside models — a uniqueness failure on `transaction_id` halts the build before corrupted data is written to the mart table.

---

## Out of Scope (Noted for Production Roadmap)

- **Cross-device identity resolution** via `user_id` join
- **Multi-touch attribution** (Linear, Time-Decay, Data-Driven)
- **Incremental dbt materialisation** to avoid full table refreshes
- **Pub/Sub + Dataflow** for true sub-second event ingestion
- **Dead Letter Queue (DLQ)** for failed streaming inserts
- **dbt Cloud** for scheduled refreshes and Slack failure alerting
