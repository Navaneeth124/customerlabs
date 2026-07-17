# Real-time Attribution Pipeline & Dashboard

This repository contains a near-real-time attribution pipeline and dashboard that computes First-Click and Last-Click from a GA4 public dataset using BigQuery + dbt.

## Features

*   **dbt Models**: Staging models for GA4 events and Data Marts for First-Click and Last-Click attribution.
*   **Streaming Demo**: A Python script to simulate real-time event streaming directly into BigQuery.
*   **Realtime Dashboard**: A Streamlit application displaying key attribution metrics and a live stream of incoming events.

## Prerequisites

1.  **Google Cloud Platform (GCP)** account with BigQuery enabled.
2.  **dbt Core** (`pip install dbt-bigquery`).
3.  **Python 3.8+** with dependencies (`pip install streamlit pandas plotly google-cloud-bigquery`).
4.  A Service Account with BigQuery Admin / Data Editor permissions.

## Run Instructions

### 1. Setup Authentication
Ensure your GCP service account key is available in your environment:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/key.json"
```

### 2. Run dbt Models
Navigate to the `dbt_project` directory and build the models:
```bash
cd dbt_project
dbt deps
dbt build
```
This command runs tests, staging models, and attribution marts.

### 3. Run Streaming Demo
Simulate near-real-time events:
```bash
python streaming/streaming_demo.py
```
This script will insert 5-20 events into BigQuery. It uses `event_id` to ensure deduplication (idempotency).

### 4. Run the Dashboard
Launch the Streamlit app:
```bash
streamlit run dashboard/app.py
```
The app will connect to BigQuery and visualize the First-Click vs Last-Click attribution along with live events.

## System Operations & Considerations

### Failure Handling
*   **Streaming API Failures**: If the `streaming_demo.py` fails to insert rows, it captures the error response from `insert_rows_json`. In production, failed inserts should be sent to a Dead Letter Queue (DLQ) like Pub/Sub for retry or manual inspection.
*   **dbt Model Failures**: Since we use `dbt build`, tests are executed alongside models. If a test fails (e.g., uniqueness of `transaction_id`), the pipeline stops, preventing corrupted data from populating the marts. 

### Monitoring Suggestions
*   **dbt**: Monitor `dbt_run_results.json` or integrate with a tool like dbt Cloud for alerting on failed runs or stale data.
*   **BigQuery**: Setup Stackdriver (Google Cloud Monitoring) alerts for anomalous spikes in BigQuery slots usage or storage write API errors.
*   **Dashboard**: Monitor Streamlit app health via health check endpoints if deployed (e.g., Cloud Run).

### Cost Notes
*   **BigQuery Processing**: The GA4 public dataset is partitioned. Ensure date filters (e.g., `_TABLE_SUFFIX BETWEEN ...`) are always used in queries to scan minimal data. Avoid `SELECT *` without limits.
*   **Streaming API**: BigQuery Storage Write API has a cost per GB streamed. For 5-20 events, it's negligible. In a high-throughput scenario, batching events (e.g., via Dataflow or Pub/Sub micro-batching) can optimize costs.
*   **dbt Materializations**: Marts are materialized as `table` to make dashboard reads fast and cheap. For near-real-time updates, `incremental` materialization should be considered in production to reduce full-refresh processing costs.

### Expected Latency & Idempotency
*   **Streaming Latency**: Events sent via the BigQuery streaming insert are available in the streaming buffer for querying almost instantly (< 5 minutes).
*   **Idempotency**: The streaming script assigns a unique `event_id` per record. The `stg_events.sql` dbt model uses a `ROW_NUMBER()` window function partitioned by `user_pseudo_id`, `event_timestamp`, and `event_name` to deduplicate events downstream, ensuring metrics remain accurate even if identical events are streamed twice
