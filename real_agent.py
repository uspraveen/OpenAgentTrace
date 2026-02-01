import sqlite3
import os
import asyncio
from openai import OpenAI
from instrumentor import auto_instrument

# ❌ REMOVED: auto_instrument("tracer.yaml") from here

# --- 2. SETUP CLIENTS ---
# (Ideally, use os.getenv for keys, but keeping your code for now)
client = OpenAI(api_key="") 
DB_PATH = "commerce.db"

# --- 3. DATABASE FUNCTIONS (SQL Layer) ---

def lookup_customer(email):
    """Fetches customer profile from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM customers WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None

def lookup_orders(customer_id):
    """Fetches order history from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM orders WHERE customer_id = ?", (customer_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

# --- 4. INTELLIGENCE LAYER (LLM Layer) ---

def generate_response(customer_name, orders, question):
    """Uses OpenAI to write a polite response based on DB data."""
    print(f"   🧠 AI generating response for {customer_name}...")
    
    system_prompt = "You are a helpful support agent. Use the order data to answer the user."
    
    # Construct Context from Real Data
    context = f"Customer: {customer_name}\nOrders:\n"
    for o in orders:
        context += f"- Order #{o['id']}: {o['items']} (Status: {o['status']})\n"
        
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nUser Question: {question}"}
        ]
    )
    
    return response.choices[0].message.content

# --- 5. MAIN WORKFLOW ---

async def handle_support_request(email, question):
    print(f"\n🚀 Processing Request from: {email}")
    
    # Step 1: SQL Lookup (Customer)
    customer = lookup_customer(email)
    if not customer:
        print("   ❌ Customer not found.")
        return "Sorry, we can't find an account with that email."
        
    # Step 2: SQL Lookup (Orders)
    orders = lookup_orders(customer['id'])
    
    # Step 3: LLM Generation
    answer = generate_response(customer['name'], orders, question)
    
    print(f"✅ Agent Response: {answer}")
    return answer

# --- RUN LOOP ---
if __name__ == "__main__":
    # Ensure DB exists
    if not os.path.exists(DB_PATH):
        print("⚠️ database not found. Please run 'setup_db.py' first.")
        exit(1)

    # ✅ MOVED HERE: Apply patches AFTER functions are defined
    print("🔌 Injecting Tracers...")
    auto_instrument("tracer.yaml")

    print("Support Agent Online...")
    
    try:
        # Scenario A: Happy Path
        asyncio.run(handle_support_request("alice@example.com", "Where is my laptop?"))
        
        # Scenario B: Another User
        asyncio.run(handle_support_request("bob@example.com", "Has my order shipped?"))
        
        # Scenario C: Unknown User
        asyncio.run(handle_support_request("fake@email.com", "Where is my stuff?"))
        
        import time
        print("⏳ Flushing traces to backend...")
        time.sleep(3) 
        print("✅ Done.")
        
    except KeyboardInterrupt:
        print("Stopped.")