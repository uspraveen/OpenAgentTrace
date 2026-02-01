import os
import sys
import json
import uuid
import time
import sqlite3
import hashlib
import inspect
import functools
import contextvars
from pathlib import Path
from datetime import datetime

# --- 1. CONFIGURATION & CONTEXT ---
TRACER_DIR = Path(".agent_tracer")
BLOB_DIR = TRACER_DIR / "blobs"
DB_PATH = TRACER_DIR / "traces.db"

# The "Invisible Thread" - Tracks execution context across async tasks
ctx_trace_id = contextvars.ContextVar("trace_id", default=None)
ctx_span_id = contextvars.ContextVar("span_id", default=None)

# --- 2. STORAGE ENGINE (Local First) ---
class StorageEngine:
    def __init__(self):
        self._init_dirs()
        self._init_db()

    def _init_dirs(self):
        TRACER_DIR.mkdir(exist_ok=True)
        BLOB_DIR.mkdir(exist_ok=True)

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        # WAL mode = High concurrency, no locking issues
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                span_id TEXT PRIMARY KEY,
                trace_id TEXT,
                parent_span_id TEXT,
                name TEXT,
                type TEXT,
                start_time REAL,
                end_time REAL,
                duration REAL,
                status TEXT,
                error_message TEXT,
                input_hash TEXT,
                output_hash TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_blob(self, data: any) -> str:
        """Saves a JSON object to disk and returns its SHA256 hash."""
        try:
            # Handle non-serializable objects gracefully
            text = json.dumps(data, default=str, sort_keys=True)
        except Exception:
            text = str(data)
            
        blob_hash = hashlib.sha256(text.encode()).hexdigest()
        file_path = BLOB_DIR / blob_hash
        
        # Deduplication: Only write if it doesn't exist
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
        return blob_hash

    def save_span(self, span_data: dict):
        """Writes the span metadata to SQLite."""
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                """INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span_data['span_id'],
                    span_data['trace_id'],
                    span_data['parent_span_id'],
                    span_data['name'],
                    span_data['type'],
                    span_data['start_time'],
                    span_data['end_time'],
                    span_data['duration'],
                    span_data['status'],
                    span_data['error_message'],
                    span_data['input_hash'],
                    span_data['output_hash']
                )
            )
            conn.commit()
        except Exception as e:
            print(f"!! AgentTracer DB Error: {e}")
        finally:
            conn.close()

storage = StorageEngine()

# --- 3. THE TRACER (SDK) ---
def get_current_trace_id():
    tid = ctx_trace_id.get()
    if not tid:
        tid = str(uuid.uuid4())
        ctx_trace_id.set(tid)
    return tid

def trace(name=None, span_type="function"):
    """
    The Universal Decorator. 
    Handles both Sync and Async functions transparently.
    """
    def decorator(func):
        nonlocal name
        if name is None:
            name = func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await _run_trace(func, args, kwargs, name, span_type, is_async=True)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _run_trace(func, args, kwargs, name, span_type, is_async=False)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

def _run_trace(func, args, kwargs, name, span_type, is_async):
    # 1. Setup Context
    trace_id = get_current_trace_id()
    parent_id = ctx_span_id.get()
    new_span_id = str(uuid.uuid4())
    
    # Set context for children
    token = ctx_span_id.set(new_span_id)
    
    start_time = time.time()
    # Save Inputs (Blob)
    input_hash = storage.save_blob({"args": args, "kwargs": kwargs})
    
    status = "SUCCESS"
    error_msg = None
    result = None

    try:
        # 2. Execute
        if is_async:
            # We must await if the loop is running, but this function is tricky
            # The wrapper above handles the await. We just need to call here.
            # Wait, _run_trace needs to be awaitable if is_async is True?
            # Design fix: _run_trace itself shouldn't be async/sync, 
            # let's duplicate logic or use a helper. 
            # For simplicity in this snippet, I will inline logic below in wrapper.
            pass 
    except Exception:
        pass

    # REVISED EXECUTION LOGIC TO HANDLE ASYNC CORRECTLY
    # (The previous abstract function approach is complex with async/sync split)
    pass

# --- 3b. REVISED TRACER LOGIC (Clean Implementation) ---
async def _execute_async(func, args, kwargs, span_data, token):
    try:
        result = await func(*args, **kwargs)
        span_data['output_hash'] = storage.save_blob(result)
        span_data['status'] = "SUCCESS"
        return result
    except Exception as e:
        span_data['error_message'] = str(e)
        span_data['status'] = "FAILURE"
        span_data['output_hash'] = storage.save_blob({"error": str(e)})
        raise e
    finally:
        _finalize_span(span_data, token)

def _execute_sync(func, args, kwargs, span_data, token):
    try:
        result = func(*args, **kwargs)
        span_data['output_hash'] = storage.save_blob(result)
        span_data['status'] = "SUCCESS"
        return result
    except Exception as e:
        span_data['error_message'] = str(e)
        span_data['status'] = "FAILURE"
        span_data['output_hash'] = storage.save_blob({"error": str(e)})
        raise e
    finally:
        _finalize_span(span_data, token)

def _finalize_span(span_data, token):
    span_data['end_time'] = time.time()
    span_data['duration'] = span_data['end_time'] - span_data['start_time']
    storage.save_span(span_data)
    ctx_span_id.reset(token)

def trace(name=None, span_type="function"):
    def decorator(func):
        fname = name or func.__name__

        def _prepare_span():
            trace_id = get_current_trace_id()
            parent_id = ctx_span_id.get()
            span_id = str(uuid.uuid4())
            token = ctx_span_id.set(span_id)
            
            span_data = {
                "span_id": span_id,
                "trace_id": trace_id,
                "parent_span_id": parent_id,
                "name": fname,
                "type": span_type,
                "start_time": time.time(),
                "input_hash": None,
                "output_hash": None,
                "status": "RUNNING",
                "error_message": None
            }
            return span_data, token

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                span_data, token = _prepare_span()
                span_data['input_hash'] = storage.save_blob({"args": args, "kwargs": kwargs})
                return await _execute_async(func, args, kwargs, span_data, token)
            return wrapper
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                span_data, token = _prepare_span()
                span_data['input_hash'] = storage.save_blob({"args": args, "kwargs": kwargs})
                return _execute_sync(func, args, kwargs, span_data, token)
            return wrapper
    return decorator