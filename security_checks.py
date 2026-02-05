import sqlite3
import os
from fraud_logger import log_fraud


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "atmguard.db")


def get_connection():
    return sqlite3.connect(DB_NAME)


def is_card_blocked(card_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status FROM card WHERE card_id = ?
    """, (card_id,))

    row = cursor.fetchone()
    conn.close()

    if row and row[0] == "blocked":
        log_fraud(card_id, "Blocked card attempted ATM action")
        return True

    return False
