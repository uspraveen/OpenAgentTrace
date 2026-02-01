import uuid
import time
import queue
import threading
import requests
import inspect
import functools
import contextvars
from typing import Any, Dict

# ✅ FIX: Use explicit IP to avoid Windows localhost issues
API_URL = "http://127.0.0.1:8000/ingest"

# Context Tracking
ctx_trace_id = contextvars.ContextVar("trace_id", default=None)
ctx_span_id = contextvars.ContextVar("span_id", default=None)
span_queue = queue.Queue()

# --- WORKER THREAD (DEBUG MODE) ---
def worker():
    print("🔌 Tracer: Background worker started...")
    while True:
        payload = span_queue.get()
        if payload is None: break
        
        try:
            # ✅ FIX: Added timeout and status check
            response = requests.post(API_URL, json=payload, timeout=2.0, proxies={"http": None, "https": None} )
            if response.status_code != 200:
                print(f"⚠️ Tracer Error: Server returned {response.status_code}")
                
        except Exception as e:
            # ✅ FIX: Print errors loudly so we can see them
            print(f"❌ Tracer Connection Failed: {e}")
            
        span_queue.task_done()

# Start worker
t = threading.Thread(target=worker, daemon=True)
t.start()

# --- HELPER LOGIC ---
def _run_span_logic(func, name, span_type, meta, args, kwargs, is_async):
    trace_id = ctx_trace_id.get()
    if not trace_id:
        trace_id = str(uuid.uuid4())
        ctx_trace_id.set(trace_id)
    
    parent_id = ctx_span_id.get()
    span_id = str(uuid.uuid4())
    token = ctx_span_id.set(span_id)

    span = {
        "span_id": span_id, "trace_id": trace_id, "parent_span_id": parent_id,
        "name": name, "type": span_type, "start_time": time.time(),
        "status": "RUNNING", "inputs": {"args": args, "kwargs": kwargs}, "meta": meta
    }
    
    span_queue.put(span.copy()) # Log 'Start'

    try:
        if is_async: 
            # This path is unused; wrapper handles async
            pass 
        else:
            result = func(*args, **kwargs)
            span['outputs'] = result
            span['status'] = "SUCCESS"
            return result
    except Exception as e:
        span['error_message'] = str(e)
        span['status'] = "FAILURE"
        raise e
    finally:
        span['end_time'] = time.time()
        span['duration'] = span['end_time'] - span['start_time']
        span_queue.put(span) # Log 'End'
        ctx_span_id.reset(token)

# --- DECORATORS ---

def trace(name=None, span_type="function", meta: Dict = {}):
    def decorator(func):
        fname = name or func.__name__
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return _run_span_logic(func, fname, span_type, meta, args, kwargs, is_async=False)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            trace_id = ctx_trace_id.get() or str(uuid.uuid4())
            ctx_trace_id.set(trace_id)
            parent_id = ctx_span_id.get()
            span_id = str(uuid.uuid4())
            token = ctx_span_id.set(span_id)
            
            span = {
                "span_id": span_id, "trace_id": trace_id, "parent_span_id": parent_id,
                "name": fname, "type": span_type, "start_time": time.time(),
                "status": "RUNNING", "inputs": {"args": args, "kwargs": kwargs}, "meta": meta
            }
            span_queue.put(span.copy())

            try:
                result = await func(*args, **kwargs)
                span['outputs'] = result
                span['status'] = "SUCCESS"
                return result
            except Exception as e:
                span['error_message'] = str(e)
                span['status'] = "FAILURE"
                raise e
            finally:
                span['end_time'] = time.time()
                span['duration'] = span['end_time'] - span['start_time']
                span_queue.put(span)
                ctx_span_id.reset(token)

        if inspect.iscoroutinefunction(func): return async_wrapper
        else: return sync_wrapper
    return decorator

def trace_sql(query: str):
    def decorator(func):
        return trace(name="db_query", span_type="db", meta={"sql": query})(func)
    return decorator

def trace_vector(collection: str):
    def decorator(func):
        return trace(name=f"vec_search:{collection}", span_type="vector_db", meta={"collection": collection})(func)
    return decorator

def get_context_headers():
    """
    Generates headers to pass context to a remote service.
    Usage: requests.post(url, headers=tracer.get_context_headers())
    """
    current_trace = ctx_trace_id.get()
    current_span = ctx_span_id.get()
    
    headers = {}
    if current_trace:
        headers["X-Trace-Id"] = current_trace
    if current_span:
        headers["X-Parent-Span-Id"] = current_span
        
    return headers

def join_trace(trace_id, parent_span_id):
    """
    Manually sets the context to continue a distributed trace.
    Usage: Call this at the start of your API handler.
    """
    if trace_id:
        ctx_trace_id.set(trace_id)
    if parent_span_id:
        ctx_span_id.set(parent_span_id)