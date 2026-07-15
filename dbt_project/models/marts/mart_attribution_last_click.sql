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
    -- We only consider events that happened before or exactly at the time of conversion
    WHERE e.event_time <= c.conversion_time
      -- Optional 30-day lookback window filter
      AND TIMESTAMP_DIFF(c.conversion_time, e.event_time, DAY) <= 30
),

-- To avoid the conversion event itself if it doesn't have channel data, 
-- we filter to touchpoints that actually represent marketing channels.
-- We'll rank them by time descending.
ranked_touchpoints AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY user_pseudo_id, transaction_id 
            ORDER BY touchpoint_time DESC
        ) AS touchpoint_rank
    FROM user_touchpoints
    WHERE (source != '(direct)' AND source IS NOT NULL) OR touchpoint_time = conversion_time
    -- Note: Standard GA4 last non-direct click would filter out direct if a prior non-direct exists.
    -- For simplicity in a standard "last click" model, we just take the last recorded touchpoint.
)

SELECT
    transaction_id,
    user_pseudo_id,
    conversion_time,
    purchase_revenue,
    source AS last_click_source,
    medium AS last_click_medium,
    campaign AS last_click_campaign,
    touchpoint_time AS last_click_time
FROM ranked_touchpoints
WHERE touchpoint_rank = 1
