import sqlite3

def init_db():
    conn = sqlite3.connect("commerce.db")
    cursor = conn.cursor()

    # 1. Create Tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            status TEXT,
            items TEXT,
            total REAL
        )
    """)

    # 2. Seed Data
    cursor.execute("INSERT OR IGNORE INTO customers (id, email, name) VALUES (1, 'alice@example.com', 'Alice Smith')")
    cursor.execute("INSERT OR IGNORE INTO customers (id, email, name) VALUES (2, 'bob@example.com', 'Bob Jones')")
    
    cursor.execute("INSERT OR IGNORE INTO orders (id, customer_id, status, items, total) VALUES (101, 1, 'SHIPPED', 'Laptop, Mouse', 1200.50)")
    cursor.execute("INSERT OR IGNORE INTO orders (id, customer_id, status, items, total) VALUES (102, 1, 'PROCESSING', 'Monitor', 300.00)")
    cursor.execute("INSERT OR IGNORE INTO orders (id, customer_id, status, items, total) VALUES (201, 2, 'DELIVERED', 'Headphones', 150.00)")

    conn.commit()
    conn.close()
    print("✅ Real Database 'commerce.db' created with seed data.")

if __name__ == "__main__":
    init_db()