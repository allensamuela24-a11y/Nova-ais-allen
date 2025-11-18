# transaction_db_setup.py

import sqlite3

DB_FILE = "transactions.db"

# -------------------------
# Setup the mock DB
# -------------------------

def initialize_db():
    """Create the database and transactions table with mock data if not already present."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create the table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        transaction_id TEXT PRIMARY KEY,
        customer_email TEXT,
        merchant_name TEXT,
        payment_method TEXT,
        currency TEXT,
        amount REAL,
        date TEXT
    )
    """)

    # Check if table already has data
    cursor.execute("SELECT COUNT(*) FROM transactions")
    count = cursor.fetchone()[0]

    if count == 0:
        mock_data = [
            ("TXN001", "allen.samuel.augustine@gmail.com", "Aldi", "Credit Card", "EUR", 59.99, "2025-05-01"),
            ("TXN002", "antony.g.robinson@gmail.com", "Amazon DE", "Sofort", "EUR", 89.50, "2025-05-02"),
            ("TXN003", "anna@gmail.com", "MediaMarkt", "Buy Now Pay Later", "EUR", 120.00, "2025-05-03"),
            ("TXN004", "kimberlydrozario1584@gmail.com", "Otto", "Cash on Delivery", "GBP", 45.00, "2025-05-04"),
            ("TXN005", "aria@gmail.com", "Saturn", "Giropay", "EUR", 75.30, "2025-05-05"),
            ("TXN006", "ar@novalnet.de", "Decathlon", "SEPA Direct Debit", "EUR", 38.99, "2025-05-06"),
            ("TXN007", "mateusz.nowak@example.pl", "Zara", "Credit Card", "PLN", 210.00, "2025-05-07"),
            ("TXN008", "sofia.karlsson@example.se", "H&M", "Swish", "SEK", 150.00, "2025-05-08"),
            ("TXN009", "laura.garcia@example.es", "El Corte Inglés", "Bizum", "EUR", 60.00, "2025-05-09"),
            ("TXN010", "nina.bauer@example.de", "Lidl", "Bank Transfer", "EUR", 20.00, "2025-05-10")
        ]

        cursor.executemany("""
        INSERT OR IGNORE INTO transactions (
            transaction_id, customer_email, merchant_name, payment_method, currency, amount, date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, mock_data)

        print("✅ Mock database created with 10 transactions.")

    conn.commit()
    conn.close()

# -------------------------
# Lookup a transaction
# -------------------------

def lookup_transaction(transaction_id: str, sender_email: str):
    """Returns transaction details if both ID and email match, ignoring case for email."""
    print(f"🔍 Looking up transaction ID '{transaction_id}' for sender email '{sender_email}' (case-insensitive)...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM transactions
    WHERE transaction_id = ? AND LOWER(customer_email) = LOWER(?)
    """, (transaction_id, sender_email))

    row = cursor.fetchone()
    conn.close()

    if row:
        print(f"✅ Match found for transaction {transaction_id}.")
        return {
            "transaction_id": row[0],
            "customer_email": row[1],
            "merchant_name": row[2],
            "payment_method": row[3],
            "currency": row[4],
            "amount": row[5],
            "date": row[6]
        }
    else:
        print(f"❌ No match found for transaction {transaction_id} with email {sender_email}.")
    return None


# -------------------------
# Run manually to initialize DB
# -------------------------

if __name__ == "__main__":
    initialize_db()
    