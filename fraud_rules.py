import sqlite3
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "atmguard.db")


MAX_SINGLE_WITHDRAWAL = 100000
MAX_DAILY_WITHDRAWAL = 300000
MAX_WITHDRAWALS_10_MIN = 3


def get_connection():
    return sqlite3.connect(DB_NAME)


def check_withdrawal_fraud(card_id, amount):
    """
    Returns list of fraud reasons
    """
    conn = get_connection()
    cursor = conn.cursor()

    reasons = []

    # ---------------- RULE 1: Single withdrawal limit ----------------
    if amount > MAX_SINGLE_WITHDRAWAL:
        reasons.append("Withdrawal exceeds single-transaction limit")

    # ---------------- RULE 2: Daily withdrawal limit ----------------
    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE card_id = ?
        AND DATE(timestamp) = ?
    """, (card_id, today))

    daily_total = cursor.fetchone()[0]

    if daily_total + amount > MAX_DAILY_WITHDRAWAL:
        reasons.append("Daily withdrawal limit exceeded")

    # ---------------- RULE 3: Rapid withdrawals ----------------
    ten_minutes_ago = datetime.now() - timedelta(minutes=10)

    cursor.execute("""
        SELECT COUNT(*)
        FROM transactions
        WHERE card_id = ?
        AND timestamp >= ?
    """, (card_id, ten_minutes_ago.strftime("%Y-%m-%d %H:%M:%S")))

    recent_count = cursor.fetchone()[0]

    if recent_count >= MAX_WITHDRAWALS_10_MIN:
        reasons.append("Multiple withdrawals in short time")

    conn.close()
    return reasons
