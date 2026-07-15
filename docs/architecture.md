# Architecture & Design

## Goal
Build a near-real-time attribution pipeline processing Google Analytics 4 (GA4) event data to compute First-Click and Last-Click attribution, visualized via a live Streamlit dashboard.

## Pipeline Architecture Diagram

```mermaid
flowchart TD
    subgraph Data Sources
        GA4[(GA4 Public Dataset\nbigquery-public-data.ga4_obfuscated_sample_ecommerce)]
        Streaming[Streaming Python Script\n(5-20 live events)]
    end

    subgraph BigQuery Data Warehouse
        GA4 --> STG[Staging: stg_events\n(Cleaned & deduplicated)]
        Streaming -. stream insert .-> STG
        
        STG --> INT[Intermediate Models\n(Sessionization, User mapping)]
        INT --> MART_FC[Mart: First-Click Attribution]
        INT --> MART_LC[Mart: Last-Click Attribution]
    end

    subgraph Transformation & Testing
        DBT((dbt Core))
        DBT -. orchestrates .-> STG
        DBT -. orchestrates .-> INT
        DBT -. orchestrates .-> MART_FC
        DBT -. orchestrates .-> MART_LC
    end

    subgraph Visualization
        ST[Streamlit Dashboard\n(app.py)]
        MART_FC --> ST
        MART_LC --> ST
        STG --> ST
    end
```

## Tools & Technology Stack
- **Data Warehouse**: Google BigQuery (Project: `luminous-return-502518-t7`)
- **Transformation**: dbt (Data Build Tool) Core for SQL modeling, materialization, and testing.
- **Data Source**: GA4 Obfuscated Sample Ecommerce public dataset (`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`).
- **Streaming Pipeline**: Python (simulating near-real-time events via BigQuery Storage Write API / InsertAll).
- **Dashboard**: Streamlit for real-time visualization.

## Assumptions & Business Logic

1. **Identity Resolution**: Users are primarily identified by `user_pseudo_id` (cookie-based). If a `user_id` is present, it can supersede, but for this dataset, we rely on `user_pseudo_id`.
2. **Lookback Window**: A 30-day lookback window is applied for attribution to limit computational cost and maintain relevance, unless specifically filtered down in the dashboard (e.g., 14-day view).
3. **Attribution Definition**: 
   - **First-Click**: 100% of the conversion credit goes to the *first* channel the user interacted with before converting.
   - **Last-Click**: 100% of the conversion credit goes to the *most recent* channel the user interacted with immediately prior to the conversion event.
4. **Conversion Event**: An event where `event_name = 'purchase'` is considered the conversion.
5. **Tie-Breakers**: If multiple events occur at the exact same `event_timestamp` for the same user, we will order them by `event_bundle_sequence_id` or deduplicate using `row_number()` to ensure consistent, idempotent attribution.
6. **Streaming Idempotency**: The streaming script inserts a unique `event_id` (or uses `user_pseudo_id` + `event_timestamp`). The `stg_events` dbt model includes a `row_number()` deduplication step based on this ID so that multiple runs of the script don't artificially inflate counts. Expected latency is < 5 minutes for BQ streaming inserts to be queryable via dbt.
