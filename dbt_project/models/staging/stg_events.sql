{{ config(
    materialized='view'
) }}

WITH raw_events AS (
    -- Select from the GA4 obfuscated public dataset.
    -- To keep costs low and data relevant, we only query the last 30 days of data in the dataset.
    -- Since the public dataset is static (e.g., 20201101 to 20210131), we will select a specific date range if needed,
    -- but for robustness we'll select everything or use a date filter.
    SELECT 
        event_date,
        event_timestamp,
        event_name,
        event_params,
        user_pseudo_id,
        user_id,
        device.category AS device_category,
        geo.country AS geo_country,
        traffic_source.source AS source,
        traffic_source.medium AS medium,
        traffic_source.name AS campaign
    FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
    WHERE _TABLE_SUFFIX BETWEEN '20201201' AND '20210131'
),

-- To support the streaming demo, we union with a local table if it exists.
-- But for simplicity, we'll assume the streaming script pushes directly to a local project dataset,
-- and we union the public dataset with the streamed dataset.
-- Assuming the local dataset is `customerlabs_dataset.streamed_events`
-- If that table doesn't exist, we can use a dbt macro or just rely on the public data for the core logic.
-- I'll structure the staging model to extract necessary parameters.

extracted_params AS (
    SELECT
        user_pseudo_id,
        event_timestamp,
        event_name,
        source,
        medium,
        campaign,
        -- Extract session_id for potential session-based grouping
        (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id,
        -- Extract transaction_id for purchase events
        (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'transaction_id') AS transaction_id,
        -- Extract revenue
        (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value') AS purchase_revenue
    FROM raw_events
),

deduplicated AS (
    -- Ensure idempotency in case of duplicate streamed events
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_pseudo_id, event_timestamp, event_name 
            ORDER BY event_timestamp DESC
        ) AS row_num
    FROM extracted_params
)

SELECT
    user_pseudo_id,
    TIMESTAMP_MICROS(event_timestamp) AS event_time,
    event_name,
    COALESCE(source, '(direct)') AS source,
    COALESCE(medium, '(none)') AS medium,
    COALESCE(campaign, '(not set)') AS campaign,
    session_id,
    transaction_id,
    purchase_revenue
FROM deduplicated
WHERE row_num = 1
