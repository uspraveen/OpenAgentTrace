# ui.py
import streamlit as st
import requests
import pandas as pd
import graphviz
import time

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Agent Tracer V3", layout="wide", page_icon="🧠")
st.markdown("""
<style>
    .stMetric { background-color: #1E1E1E; padding: 10px; border-radius: 5px; border: 1px solid #333; }
    div[data-testid="stExpander"] { border: 1px solid #333; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("🧠 Tracer V3")
    if st.toggle("Live Stream", value=True):
        time.sleep(2)
        st.rerun()

# --- MAIN ---
try:
    traces = requests.get(f"{API_URL}/traces").json()
except:
    st.error("Server Offline. Run `python api.py`")
    st.stop()

if not traces:
    st.info("Waiting for Agent data...")
    st.stop()

df = pd.DataFrame(traces)
selected_id = st.sidebar.selectbox("History", df['trace_id'], format_func=lambda x: f"{df[df['trace_id']==x].iloc[0]['name']} ({x[:4]})")

# --- DETAIL VIEW ---
if selected_id:
    trace_data = requests.get(f"{API_URL}/trace/{selected_id}").json()
    df_spans = pd.DataFrame(trace_data)
    root = df_spans[df_spans['parent_span_id'].isna()].iloc[0]

    # Header
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agent", root['name'])
    c2.metric("Status", root['status'], delta_color="normal" if root['status']=="SUCCESS" else "inverse")
    c3.metric("Duration", f"{root['duration']:.2f}s" if root['duration'] else "--")
    
    # ✨ V3 FEATURE: AUTO DIAGNOSIS
    if root['status'] == "FAILURE":
        if c4.button("✨ Diagnose Failure"):
            with st.spinner("Asking AI Debugger..."):
                analysis = requests.post(f"{API_URL}/analyze/{selected_id}").json()
                st.info(analysis['analysis'])

    # TABS
    tab_graph, tab_playground = st.tabs(["📊 Execution Graph", "🎮 Prompt Playground"])

    with tab_graph:
        # Graphviz
        graph = graphviz.Digraph()
        graph.attr(rankdir='LR', bgcolor='transparent')
        for _, s in df_spans.iterrows():
            color = "green" if s['status'] == "SUCCESS" else "red"
            graph.node(s['span_id'], f"{s['name']}\n({s['type']})", color=color, shape="box", style="rounded")
            if s['parent_span_id']:
                graph.edge(s['parent_span_id'], s['span_id'])
        st.graphviz_chart(graph)

        # JSON Inspector
        for _, s in df_spans.iterrows():
            with st.expander(f"{'✅' if s['status']=='SUCCESS' else '❌'} {s['name']}"):
                st.write("**Input:**", s['inputs'])
                st.write("**Output:**", s['outputs'])
                if s['error_message']: st.error(s['error_message'])

    with tab_playground:
        st.caption("Select an LLM step to edit and re-run the prompt.")
        
        # Filter only LLM spans
        llm_spans = df_spans[df_spans['type'] == 'llm']
        
        if llm_spans.empty:
            st.warning("No LLM calls found in this trace.")
        else:
            target_span_id = st.selectbox("Select LLM Step", llm_spans['span_id'], format_func=lambda x: llm_spans[llm_spans['span_id']==x].iloc[0]['name'])
            target_span = llm_spans[llm_spans['span_id'] == target_span_id].iloc[0]

            # Attempt to extract prompt from inputs (Heuristic)
            # Adjust this based on how you structure inputs in agent.py
            inputs = target_span['inputs'] or {}
            # Defaults
            sys_prompt = "You are a helpful assistant."
            user_prompt = str(inputs)

            # If our agent stored them nicely in "kwargs", let's grab them
            if isinstance(inputs, dict) and 'kwargs' in inputs:
                sys_prompt = inputs['kwargs'].get('system_prompt', sys_prompt)
                user_prompt = inputs['kwargs'].get('user_message', user_prompt)
                # If we injected context in agent.py, user_message might be just the question
                # Let's show the raw inputs for editing
            
            col_a, col_b = st.columns(2)
            with col_a:
                new_sys = st.text_area("System Prompt", sys_prompt, height=150)
                new_user = st.text_area("User Prompt", user_prompt, height=300)
            
            with col_b:
                st.markdown("**Live Test Result**")
                if st.button("▶️ Run Fix"):
                    with st.spinner("Calling LLM..."):
                        res = requests.post(f"{API_URL}/playground/run", json={
                            "system_prompt": new_sys,
                            "user_prompt": new_user
                        }).json()
                        
                        if "error" in res:
                            st.error(res['error'])
                        else:
                            st.success("Success!")
                            st.write(res['result'])