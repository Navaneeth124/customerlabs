import os
import time
import uuid
import random
from datetime import datetime, timezone
from google.cloud import bigquery

# IMPORTANT: Ensure your GOOGLE_APPLICATION_CREDENTIALS environment variable is set.
# e.g., os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/path/to/key.json"

PROJECT_ID = "luminous-return-502518-t7"
DATASET_ID = "ga4_attribution"
TABLE_ID = "streamed_events"
TABLE_REF = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

def get_bq_client():
    try:
        return bigquery.Client(project=PROJECT_ID)
    except Exception as e:
        print(f"Failed to initialize BigQuery client: {e}")
        print("Please ensure GOOGLE_APPLICATION_CREDENTIALS is set.")
        return None

def create_table_if_not_exists(client):
    schema = [
        bigquery.SchemaField("event_date", "STRING"),
        bigquery.SchemaField("event_timestamp", "INTEGER"),
        bigquery.SchemaField("event_name", "STRING"),
        bigquery.SchemaField("user_pseudo_id", "STRING"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("medium", "STRING"),
        bigquery.SchemaField("campaign", "STRING"),
        bigquery.SchemaField("transaction_id", "STRING"),
        bigquery.SchemaField("purchase_revenue", "FLOAT"),
        bigquery.SchemaField("event_id", "STRING") # For idempotency/dedupe
    ]
    
    table = bigquery.Table(TABLE_REF, schema=schema)
    try:
        client.get_table(table)  # Check if exists
        print(f"Table {TABLE_REF} already exists.")
    except Exception:
        # Table doesn't exist, create it
        print(f"Creating table {TABLE_REF}...")
        client.create_table(table)
        print("Table created.")

def generate_sample_events(num_events=10):
    events = []
    
    # Generate some users
    users = [f"user_{uuid.uuid4().hex[:8]}" for _ in range(3)]
    
    channels = [
        {"source": "google", "medium": "cpc", "campaign": "summer_sale"},
        {"source": "facebook", "medium": "cpc", "campaign": "retargeting"},
        {"source": "newsletter", "medium": "email", "campaign": "weekly_digest"},
        {"source": "(direct)", "medium": "(none)", "campaign": "(not set)"}
    ]
    
    event_names = ["page_view", "add_to_cart", "begin_checkout", "purchase"]
    
    for i in range(num_events):
        now = datetime.now(timezone.utc)
        user = random.choice(users)
        channel = random.choice(channels)
        
        # Make the last few events purchases to simulate conversions
        if i >= num_events - 2:
            event_name = "purchase"
            transaction_id = f"T_{uuid.uuid4().hex[:8]}"
            revenue = round(random.uniform(10.0, 150.0), 2)
        else:
            event_name = random.choice(event_names[:-1])
            transaction_id = None
            revenue = None

        events.append({
            "event_date": now.strftime("%Y%m%d"),
            "event_timestamp": int(now.timestamp() * 1e6), # microseconds
            "event_name": event_name,
            "user_pseudo_id": user,
            "source": channel["source"],
            "medium": channel["medium"],
            "campaign": channel["campaign"],
            "transaction_id": transaction_id,
            "purchase_revenue": revenue,
            "event_id": str(uuid.uuid4()) # Unique identifier for deduplication
        })
    return events

def stream_events_to_bq():
    client = get_bq_client()
    if not client:
        return
        
    create_table_if_not_exists(client)
    
    events = generate_sample_events(15)
    print(f"Streaming {len(events)} events to BigQuery...")
    
    # BigQuery streaming insert
    # To demonstrate idempotency, we can use insertId in the API (though deprecated, it's still supported)
    # Alternatively, the dbt staging model deduplicates by event_id / user_pseudo_id + event_timestamp.
    # Latency: Data is typically queryable within seconds via streaming buffer, but can take ~90 mins for full columnar extraction.
    errors = client.insert_rows_json(
        TABLE_REF, 
        events,
        row_ids=[e["event_id"] for e in events] # Enables best-effort deduplication by BQ
    )
    
    if errors == []:
        print("Successfully streamed events.")
        for e in events:
            print(f" -> {e['event_name']} by {e['user_pseudo_id']} from {e['source']}")
    else:
        print("Encountered errors while streaming:", errors)

if __name__ == "__main__":
    stream_events_to_bq()
