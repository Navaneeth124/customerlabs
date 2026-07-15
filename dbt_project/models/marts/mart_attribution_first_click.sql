{{ config(
    materialized='table'
) }}

WITH events AS (
    SELECT * FROM {{ ref('stg_events') }}
),

conversions AS (
    SELECT
        user_pseudo_id,
        event_time AS conversion_time,
        transaction_id,
        purchase_revenue
    FROM events
    WHERE event_name = 'purchase'
      AND transaction_id IS NOT NULL
),

user_touchpoints AS (
    SELECT
        e.user_pseudo_id,
        e.event_time AS touchpoint_time,
        e.source,
        e.medium,
        e.campaign,
        c.conversion_time,
        c.transaction_id,
        c.purchase_revenue
    FROM events e
    JOIN conversions c ON e.user_pseudo_id = c.user_pseudo_id
    WHERE e.event_time <= c.conversion_time
      -- Optional 30-day lookback window filter
      AND TIMESTAMP_DIFF(c.conversion_time, e.event_time, DAY) <= 30
      -- We only consider actual traffic sources, exclude direct if needed, but for GA4 we'll just take the earliest
),

ranked_touchpoints AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_pseudo_id, transaction_id 
            ORDER BY touchpoint_time ASC
        ) AS touchpoint_rank
    FROM user_touchpoints
)

SELECT
    transaction_id,
    user_pseudo_id,
    conversion_time,
    purchase_revenue,
    source AS first_click_source,
    medium AS first_click_medium,
    campaign AS first_click_campaign,
    touchpoint_time AS first_click_time
FROM ranked_touchpoints
WHERE touchpoint_rank = 1
