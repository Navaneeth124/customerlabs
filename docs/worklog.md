# Worklog

- **Day 0 / Entry 1 (Project setup)**: Initialized git repository, added `.gitignore`, reviewed requirements, and selected the `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*` dataset. Created the initial project plan.
- **Day 1 / Entry 2 (Architecture)**: Drafted `architecture.md` outlining the pipeline design (BigQuery, dbt, Streamlit) and clarifying assumptions on lookback windows, first-click, and last-click attribution models.
- **Day 1 / Entry 3 (dbt Models)**: Configured `dbt_project.yml` for BigQuery. Wrote staging model `stg_events.sql` extracting critical params and deduping events via window functions.
- **Day 2 / Entry 4 (Data Marts)**: Created two attribution models `mart_attribution_first_click` and `mart_attribution_last_click` adhering to 30-day lookback constraints. Added uniqueness tests in `schema.yml`.
- **Day 2 / Entry 5 (Streaming Demo)**: Developed a Python script `streaming_demo.py` utilizing the BigQuery client to simulate insert streams of fake session & purchase data. Handled idempotency by passing `insertId`.
- **Day 3 / Entry 6 (Dashboard UX)**: Designed Streamlit app `app.py` directly connecting to BigQuery with robust fallback mock data handling in case of missing credentials. Included visualizations for daily trends and a live event log.
- **Day 3 / Entry 7 (Documentation)**: Compiled `README.md` containing run instructions, monitoring strategies, failure handling paradigms, and expected latency/idempotency guarantees. Finalized GitHub repository.
