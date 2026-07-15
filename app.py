import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from google.cloud import bigquery
import os
from datetime import datetime, timedelta

# Configuration
st.set_page_config(page_title="Real-time Attribution Dashboard", layout="wide")
PROJECT_ID = "luminous-return-502518-t7"

# Function to get BigQuery client
@st.cache_resource
def get_bq_client():
    try:
        return bigquery.Client(project=PROJECT_ID)
    except Exception as e:
        st.warning(f"Failed to initialize BigQuery client: {e}. Using mock data for demonstration.")
        return None

# --- Mock Data Generation (Fallback) ---
def get_mock_data():
    today = datetime.now()
    dates = [today - timedelta(days=i) for i in range(14)]
    channels = ["google / cpc", "facebook / cpc", "(direct) / (none)", "newsletter / email"]
    
    # 14-day time series mock
    ts_data = []
    for d in dates:
        for c in channels:
            ts_data.append({
                "date": d.strftime("%Y-%m-%d"),
                "channel": c,
                "conversions": np.random.randint(1, 20),
                "revenue": np.random.uniform(50, 500)
            })
    ts_df = pd.DataFrame(ts_data)
    
    # Channel breakdown mock
    channel_df = pd.DataFrame({
        "channel": channels,
        "first_click_conversions": np.random.randint(50, 200, size=len(channels)),
        "last_click_conversions": np.random.randint(50, 200, size=len(channels))
    })
    
    # Live events mock
    live_events = []
    for _ in range(10):
        live_events.append({
            "event_time": (today - timedelta(minutes=np.random.randint(1, 60))).strftime("%Y-%m-%d %H:%M:%S"),
            "event_name": np.random.choice(["page_view", "add_to_cart", "purchase"]),
            "user": f"user_{np.random.randint(1000, 9999)}",
            "channel": np.random.choice(channels)
        })
    live_df = pd.DataFrame(live_events).sort_values("event_time", ascending=False)
    
    return ts_df, channel_df, live_df

# --- Data Fetching from BigQuery ---
def fetch_bq_data(client):
    try:
        # Time Series (Last 14 days)
        ts_query = f"""
            SELECT 
                DATE(conversion_time) as date,
                CONCAT(first_click_source, ' / ', first_click_medium) as channel,
                COUNT(transaction_id) as conversions,
                SUM(purchase_revenue) as revenue
            FROM `{PROJECT_ID}.customerlabs_dataset.mart_attribution_first_click`
            WHERE conversion_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
            GROUP BY 1, 2
        """
        ts_df = client.query(ts_query).to_dataframe()
        
        # Channel Breakdown (First vs Last)
        channel_query = f"""
            WITH fc AS (
                SELECT 
                    CONCAT(first_click_source, ' / ', first_click_medium) as channel,
                    COUNT(transaction_id) as first_click_conversions
                FROM `{PROJECT_ID}.customerlabs_dataset.mart_attribution_first_click`
                GROUP BY 1
            ),
            lc AS (
                SELECT 
                    CONCAT(last_click_source, ' / ', last_click_medium) as channel,
                    COUNT(transaction_id) as last_click_conversions
                FROM `{PROJECT_ID}.customerlabs_dataset.mart_attribution_last_click`
                GROUP BY 1
            )
            SELECT 
                COALESCE(fc.channel, lc.channel) as channel,
                COALESCE(fc.first_click_conversions, 0) as first_click_conversions,
                COALESCE(lc.last_click_conversions, 0) as last_click_conversions
            FROM fc
            FULL OUTER JOIN lc ON fc.channel = lc.channel
        """
        channel_df = client.query(channel_query).to_dataframe()
        
        # Live events
        live_query = f"""
            SELECT 
                event_timestamp as event_time,
                event_name,
                user_pseudo_id as user,
                CONCAT(source, ' / ', medium) as channel
            FROM `{PROJECT_ID}.customerlabs_dataset.streamed_events`
            ORDER BY event_timestamp DESC
            LIMIT 20
        """
        live_df = client.query(live_query).to_dataframe()
        
        return ts_df, channel_df, live_df
    except Exception as e:
        st.error(f"Error fetching data from BQ: {e}")
        return get_mock_data()

# --- Main Dashboard ---
def main():
    st.title("🚀 Real-time Attribution Dashboard")
    st.markdown("Comparing First-Click vs Last-Click attribution from GA4 Data.")
    
    client = get_bq_client()
    if client:
        ts_df, channel_df, live_df = fetch_bq_data(client)
    else:
        ts_df, channel_df, live_df = get_mock_data()
        
    # --- Top Level Metrics ---
    st.header("Overall Totals")
    col1, col2 = st.columns(2)
    total_fc = channel_df['first_click_conversions'].sum()
    total_lc = channel_df['last_click_conversions'].sum()
    
    col1.metric("First-Click Conversions (Total)", f"{total_fc:,.0f}")
    col2.metric("Last-Click Conversions (Total)", f"{total_lc:,.0f}")
    
    st.divider()
    
    # --- Visualizations ---
    col3, col4 = st.columns(2)
    
    with col3:
        st.subheader("14-Day Time Series (First-Click)")
        if not ts_df.empty:
            fig_ts = px.line(ts_df, x="date", y="conversions", color="channel", title="Conversions over time by Channel")
            st.plotly_chart(fig_ts, use_container_width=True)
        else:
            st.info("No data available for the last 14 days.")
            
    with col4:
        st.subheader("Channel Breakdown (First vs Last)")
        if not channel_df.empty:
            melted_channel = channel_df.melt(id_vars=["channel"], var_name="Model", value_name="Conversions")
            fig_bar = px.bar(melted_channel, x="channel", y="Conversions", color="Model", barmode="group", title="Attribution Comparison")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No channel data available.")
            
    st.divider()
    
    # --- Live Event Panel ---
    st.header("⚡ Live Streamed Events")
    st.markdown("Displaying the most recent events hitting the pipeline.")
    
    if st.button("Refresh Data"):
        st.rerun()
        
    st.dataframe(live_df, use_container_width=True)

if __name__ == "__main__":
    main()
