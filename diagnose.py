import requests
import time
import sys
import os

# Ensure we can import the backend code
sys.path.append(os.path.join(os.getcwd(), 'backend'))

print("🔍 STARTING DIAGNOSTICS...")

# --- TEST 1: RAW SERVER CONNECTION ---
print("\n[Test 1] Checking connectivity to Backend API...")
URL = "http://127.0.0.1:8000/ingest"
dummy_payload = {
    "span_id": "test-123",
    "trace_id": "trace-test",
    "name": "diagnostic_probe",
    "type": "test",
    "start_time": time.time(),
    "status": "SUCCESS"
}

try:
    # Force bypass proxies which cause 90% of localhost issues
    resp = requests.post(URL, json=dummy_payload, timeout=5, proxies={"http": None, "https": None})
    print(f"   ✅ Server responded: {resp.status_code}")
    if resp.status_code == 200:
        print("   ✅ Connection confirmed.")
    else:
        print(f"   ❌ Server Error: {resp.text}")
except Exception as e:
    print(f"   ❌ Network Failed: {e}")
    print("   👉 check if main.py is running!")
    print("   👉 check if port 8000 is open!")


# --- TEST 2: TRACER WORKER ---
print("\n[Test 2] Checking Tracer Queue & Worker Thread...")
try:
    from backend import tracer
    
    # Enable VERBOSE mode manually for this test
    def verbose_worker():
        print("   🔌 Debug Worker started.")
        while True:
            item = tracer.span_queue.get()
            if item is None: break
            print(f"   📦 Queue Item Retrieved: {item.get('name')}")
            try:
                print(f"   🚀 Sending POST to {tracer.API_URL}...")
                r = requests.post(tracer.API_URL, json=item, timeout=2, proxies={"http": None, "https": None})
                print(f"   📨 Response: {r.status_code}")
            except Exception as e:
                print(f"   ❌ Worker Exception: {e}")
            tracer.span_queue.task_done()

    # Kill the old worker and start our verbose one (Monkey Patch)
    # We can't easily kill threads, so we just start a second consumer which is fine for testing
    import threading
    t = threading.Thread(target=verbose_worker, daemon=True)
    t.start()
    
    # Manually trigger a trace
    print("   Generating Test Span...")
    
    @tracer.trace(name="test_function", span_type="debug")
    def my_test():
        print("   ▶️ Executing function body...")
        return "ok"

    my_test()
    
    print("   ⏳ Waiting for flush...")
    time.sleep(2)
    print("   ✅ Done.")

except ImportError as e:
    print(f"   ❌ Could not import tracer: {e}")
except Exception as e:
    print(f"   ❌ Test Failed: {e}")