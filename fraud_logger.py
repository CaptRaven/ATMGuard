import sqlite3
from datetime import datetime
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "atmguard.db")


def get_connection():
    return sqlite3.connect(DB_NAME, isolation_level=None)


def log_fraud(card_id, fraud_type):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO fraud_log (card_id, fraud_type, action_taken, timestamp)
        VALUES (?, ?, ?, ?)
    """, (
        card_id,
        fraud_type,
        "Logged",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.close()


def increment_violation_count(card_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE card
        SET state_violations = COALESCE(state_violations, 0) + 1
        WHERE card_id = ?
    """, (card_id,))

    cursor.execute("""
        SELECT state_violations
        FROM card
        WHERE card_id = ?
    """, (card_id,))

    count = cursor.fetchone()[0]

    if count >= 2:
        cursor.execute("""
            UPDATE card
            SET status = 'blocked'
            WHERE card_id = ?
        """, (card_id,))

        cursor.execute("""
            INSERT INTO fraud_log (card_id, fraud_type, action_taken, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            card_id,
            "Repeated ATM state violation",
            "Card blocked",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.close()
