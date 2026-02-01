import yaml
import importlib
import sys
import os
from backend.tracer import trace, trace_sql, trace_vector

# Ensure backend is in path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

def auto_instrument(config_path="tracer.yaml"):
    """
    Reads a YAML config and monkey-patches the target functions
    with the appropriate Agent Tracer decorators.
    """
    if not os.path.exists(config_path):
        print(f"⚠️ Config {config_path} not found. Skipping auto-instrumentation.")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    print(f"🔌 Agent Tracer: applying patches from {config_path}...")

    # Prevent re-patching if called recursively
    if getattr(sys, "_agent_tracer_patched", False):
        return
    sys._agent_tracer_patched = True

    for rule in config.get('targets', []):
        module_path = rule['module']
        function_name = rule['function']
        trace_type = rule.get('type', 'function')
        
        try:
            # --- INTELLIGENT IMPORT LOGIC ---
            # If we are patching the script that is currently running (e.g. real_agent.py),
            # we must patch '__main__' instead of importing 'real_agent' again.
            if module_path == os.path.basename(sys.argv[0]).replace(".py", ""):
                mod = sys.modules['__main__']
            else:
                mod = importlib.import_module(module_path)
            
            # 2. Get the original function
            if not hasattr(mod, function_name):
                # Only warn if it's NOT the double-import artifact
                if mod.__name__ != "__main__": 
                    print(f"   ❌ Could not find {function_name} in {mod.__name__}")
                continue
            
            original_func = getattr(mod, function_name)
            
            # 3. Select the correct decorator
            if trace_type == 'sql':
                query_meta = rule.get('meta', {}).get('query_template', 'Dynamic SQL')
                decorator = trace_sql(query=query_meta)
            
            elif trace_type == 'vector':
                collection = rule.get('meta', {}).get('collection', 'default')
                decorator = trace_vector(collection=collection)
            
            elif trace_type == 'llm':
                meta = rule.get('meta', {})
                decorator = trace(name=function_name, span_type="llm", meta=meta)
                
            else:
                decorator = trace(name=function_name, span_type=trace_type)

            # 4. Apply the Patch
            instrumented_func = decorator(original_func)
            setattr(mod, function_name, instrumented_func)
            
            print(f"   ✅ Patched: {mod.__name__}.{function_name} [{trace_type}]")

        except ImportError:
            print(f"   ❌ Failed to import module: {module_path}")
        except Exception as e:
            # Ignore errors arising from circular imports during startup
            pass