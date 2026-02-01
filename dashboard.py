import streamlit as st
import sqlite3
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

# --- CONFIG ---
TRACER_DIR = Path(".agent_tracer")
DB_PATH = TRACER_DIR / "traces.db"
BLOB_DIR = TRACER_DIR / "blobs"

st.set_page_config(page_title="Agent Tracer", layout="wide")
st.title("🕵️ Agent Tracer (Local)")

# --- HELPERS ---
def load_blob(blob_hash):
    if not blob_hash: return {}
    path = BLOB_DIR / blob_hash
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"error": "Blob not found"}

def get_traces():
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT 
            trace_id, 
            span_id, 
            parent_span_id,
            name, 
            type, 
            status, 
            duration, 
            start_time,
            input_hash,
            output_hash,
            error_message
        FROM spans 
        ORDER BY start_time DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# --- UI LOGIC ---

# 1. Sidebar: Trace Selection
st.sidebar.header("Execution History")
df = get_traces()

if df.empty:
    st.warning("No traces found. Run `python demo_agent.py` first!")
    st.stop()

# Group by Trace ID to show unique runs
unique_traces = df[['trace_id', 'start_time', 'name', 'status']].drop_duplicates('trace_id')
unique_traces['label'] = unique_traces.apply(
    lambda x: f"{datetime.fromtimestamp(x['start_time']).strftime('%H:%M:%S')} - {x['status']}", axis=1
)

selected_trace_id = st.sidebar.selectbox(
    "Select Trace", 
    unique_traces['trace_id'].tolist(),
    format_func=lambda x: unique_traces[unique_traces['trace_id'] == x]['label'].values[0]
)

# 2. Main View: DAG / Waterfall
trace_spans = df[df['trace_id'] == selected_trace_id].sort_values("start_time")

st.subheader(f"Trace: {selected_trace_id}")

# Metric Cards
col1, col2, col3 = st.columns(3)
root_span = trace_spans[trace_spans['parent_span_id'].isna()].iloc[0]
col1.metric("Status", root_span['status'], delta_color="normal" if root_span['status']=="SUCCESS" else "inverse")
col2.metric("Total Duration", f"{root_span['duration']:.4f}s")
col3.metric("Spans", len(trace_spans))

# 3. Waterfall Visualization (Simple Table for now)
st.markdown("### Execution Flow")

for index, row in trace_spans.iterrows():
    # Indent based on hierarchy (mock logic: if parent exists, indent)
    indent = "└─ " if row['parent_span_id'] else ""
    icon = "✅" if row['status'] == "SUCCESS" else "❌"
    
    with st.expander(f"{indent} {icon} **{row['name']}** ({row['type']}) - {row['duration']:.4f}s"):
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Inputs:**")
            st.json(load_blob(row['input_hash']))
            
        with c2:
            st.markdown("**Outputs:**")
            if row['status'] == "FAILURE":
                st.error(row['error_message'])
            st.json(load_blob(row['output_hash']))
        
        st.caption(f"Span ID: {row['span_id']} | Parent: {row['parent_span_id']}")