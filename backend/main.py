import json
import hashlib
import time
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Float, Text, JSON
from sqlalchemy.orm import sessionmaker, declarative_base

# --- CONFIG ---
BASE_DIR = Path(".")
BLOB_DIR = BASE_DIR / "blobs"
BLOB_DIR.mkdir(exist_ok=True)
DATABASE_URL = "sqlite:///./tracer_v4.db"
DUCK_DB_PATH = "analytics.duckdb"

# --- SQLALCHEMY SETUP (Transactional Graph) ---
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SpanModel(Base):
    __tablename__ = "spans"
    span_id = Column(String, primary_key=True, index=True)
    trace_id = Column(String, index=True)
    parent_span_id = Column(String, nullable=True)
    name = Column(String)
    type = Column(String)
    start_time = Column(Float)
    end_time = Column(Float, nullable=True)
    duration = Column(Float, nullable=True)
    status = Column(String)
    error_message = Column(Text, nullable=True)
    input_hash = Column(String, nullable=True)
    output_hash = Column(String, nullable=True)
    metadata_json = Column(JSON, nullable=True)

Base.metadata.create_all(bind=engine)

# --- DUCKDB SETUP (Analytical Metrics) ---
def init_duckdb():
    conn = duckdb.connect(DUCK_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            time TIMESTAMP,
            trace_id VARCHAR,
            span_id VARCHAR,
            name VARCHAR,
            type VARCHAR,
            status VARCHAR,
            duration DOUBLE,
            cost DOUBLE DEFAULT 0.0,
            tokens_total INTEGER DEFAULT 0
        )
    """)
    conn.close()

init_duckdb()

# --- BLOB STORAGE HELPERS ---
def save_blob(data: Any) -> Optional[str]:
    if data is None: return None
    try:
        text = json.dumps(data, default=str)
    except:
        text = str(data)
    blob_hash = hashlib.sha256(text.encode()).hexdigest()
    with open(BLOB_DIR / blob_hash, "w", encoding="utf-8") as f:
        f.write(text)
    return blob_hash

def get_blob(blob_hash: Optional[str]) -> Any:
    if not blob_hash: return None
    path = BLOB_DIR / blob_hash
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# --- API ---
app = FastAPI(title="Agent Tracer V6")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpanIngest(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    type: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    inputs: Any = None
    outputs: Any = None
    meta: Dict[str, Any] = {}

@app.post("/ingest")
def ingest_span(span: SpanIngest):
    # 1. WRITE TO SQLITE (Graph)
    db = SessionLocal()
    in_hash = save_blob(span.inputs)
    out_hash = save_blob(span.outputs)

    # Upsert logic (check if span exists to avoid duplicates)
    existing = db.query(SpanModel).filter(SpanModel.span_id == span.span_id).first()
    if not existing:
        existing = SpanModel(span_id=span.span_id)
        db.add(existing)

    existing.trace_id = span.trace_id
    existing.parent_span_id = span.parent_span_id
    existing.name = span.name
    existing.type = span.type
    existing.start_time = span.start_time
    existing.end_time = span.end_time
    existing.duration = span.duration
    existing.status = span.status
    existing.error_message = span.error_message
    existing.input_hash = in_hash
    existing.output_hash = out_hash
    existing.metadata_json = span.meta
    
    db.commit()
    db.close()

    # 2. WRITE TO DUCKDB (Analytics) - Only on span completion
    if span.end_time:
        tokens = span.meta.get("usage", {}).get("total_tokens", 0)
        cost = span.meta.get("cost", 0.0)
        
        d_conn = duckdb.connect(DUCK_DB_PATH)
        # Using epoch_ms requires timestamp in ms
        d_conn.execute(f"""
            INSERT INTO metrics VALUES (
                epoch_ms({int(span.start_time * 1000)}), 
                ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            span.trace_id, span.span_id, span.name, span.type,
            span.status, span.duration or 0.0, cost, tokens
        ))
        d_conn.close()

    return {"status": "ok"}

@app.get("/traces")
def list_traces():
    db = SessionLocal()
    # Get the root span for each trace to list them
    traces = db.query(
        SpanModel.trace_id, SpanModel.name, SpanModel.start_time, SpanModel.status
    ).filter(SpanModel.parent_span_id == None).order_by(SpanModel.start_time.desc()).limit(50).all()
    
    result = []
    for t in traces:
        result.append({
            "trace_id": t.trace_id,
            "name": t.name,
            "start_time": datetime.fromtimestamp(t.start_time).isoformat(),
            "status": t.status
        })
    db.close()
    return result

@app.get("/traces/{trace_id}")
def get_trace_details(trace_id: str):
    db = SessionLocal()
    spans = db.query(SpanModel).filter(SpanModel.trace_id == trace_id).all()
    enriched = []
    for s in spans:
        enriched.append({
            "span_id": s.span_id,
            "parent_span_id": s.parent_span_id,
            "name": s.name,
            "type": s.type,
            "status": s.status,
            "duration": s.duration,
            "meta": s.metadata_json,
            "inputs": get_blob(s.input_hash),
            "outputs": get_blob(s.output_hash)
        })
    db.close()
    return enriched

@app.get("/analytics/dashboard")
def get_analytics(start: Optional[str] = None, end: Optional[str] = None):
    con = duckdb.connect(DUCK_DB_PATH)
    
    # Base Time Filter Logic
    time_filter = "1=1"
    params = []
    
    if start:
        time_filter += " AND time >= ?"
        params.append(start)
    if end:
        # Add 1 day to include the end date fully if it's just YYYY-MM-DD
        time_filter += " AND time <= ?"
        params.append(end)

    # 1. Error Rate (Filtered)
    err_query = f"""
        SELECT (COUNT(CASE WHEN status = 'FAILURE' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) 
        FROM metrics 
        WHERE {time_filter}
    """
    res_err = con.execute(err_query, params).fetchone()
    error_rate = res_err[0] if res_err and res_err[0] is not None else 0.0

    # 2. Latency Stats (Filtered)
    lat_query = f"""
        SELECT type, quantile_cont(duration, 0.95), avg(duration) 
        FROM metrics 
        WHERE type IN ('llm', 'db', 'vector_db') AND {time_filter} 
        GROUP BY type
    """
    lat_stats = con.execute(lat_query, params).fetchall()

    # 3. Daily Trend (Filtered)
    # Default to 7 days if no specific filter is applied
    chart_filter = time_filter if (start or end) else "time > now() - INTERVAL 7 DAY"
    chart_params = params if (start or end) else []
    
    trend_query = f"""
        SELECT date_trunc('day', time), sum(tokens_total) 
        FROM metrics 
        WHERE {chart_filter}
        GROUP BY 1 
        ORDER BY 1 ASC
    """
    daily = con.execute(trend_query, chart_params).fetchall()
    
    con.close()

    return {
        "error_rate": round(error_rate, 2),
        "latency_by_type": [{"type": r[0], "p95": round(r[1], 3), "avg": round(r[2], 3)} for r in lat_stats],
        "daily_trend": [{"date": r[0].strftime("%Y-%m-%d"), "tokens": r[1]} for r in daily]
    }

@app.delete("/traces/{trace_id}")
def delete_trace(trace_id: str):
    # 1. Delete from SQLite
    db = SessionLocal()
    db.query(SpanModel).filter(SpanModel.trace_id == trace_id).delete()
    db.commit()
    db.close()

    # 2. Delete from DuckDB
    d_conn = duckdb.connect(DUCK_DB_PATH)
    d_conn.execute("DELETE FROM metrics WHERE trace_id = ?", (trace_id,))
    d_conn.close()
    
    return {"status": "deleted", "id": trace_id}

@app.delete("/analytics/reset")
def reset_analytics():
    con = duckdb.connect(DUCK_DB_PATH)
    con.execute("DELETE FROM metrics")
    con.close()
    return {"status": "metrics_cleared"}

@app.delete("/traces/reset")
def reset_all_traces():
    db = SessionLocal()
    db.query(SpanModel).delete()
    db.commit()
    db.close()
    
    # Also clear analytics to keep things in sync
    reset_analytics()
    return {"status": "all_data_cleared"}

if __name__ == "__main__":
    import uvicorn
    # Bind to 0.0.0.0 to allow connections from localhost and 127.0.0.1
    uvicorn.run(app, host="0.0.0.0", port=8000)