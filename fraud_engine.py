import sqlite3
from datetime import datetime, timedelta

DB_NAME = "atmguard.db"

HIGH_AMOUNT_THRESHOLD = 100000
MAX_TXN_IN_WINDOW = 3
TXN_WINDOW_MINUTES = 10
MAX_SESSIONS_WINDOW = 5
SESSION_WINDOW_MINUTES = 15


class FraudResult:
    def __init__(self):
        self.reasons = []
        self.severity = "LOW"
        self.action = "ALLOW"

    def add(self, reason, severity="LOW", action="ALLOW"):
        self.reasons.append(reason)
        if severity == "HIGH":
            self.severity = "HIGH"
            self.action = action
        elif severity == "MEDIUM" and self.severity != "HIGH":
            self.severity = "MEDIUM"
            self.action = action


def check_fraud(card_id: str, amount: float, transaction_type: str, location: str = "UNKNOWN"):
    result = FraudResult()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Rule 1: High amount
    if transaction_type == "withdraw" and amount >= HIGH_AMOUNT_THRESHOLD:
        result.add(
            reason="Unusually high withdrawal amount",
            severity="HIGH",
            action="BLOCK"
        )

    # Rule 2: Transaction velocity
    window_start = datetime.now() - timedelta(minutes=TXN_WINDOW_MINUTES)
    cursor.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE card_id=? AND type='withdraw' AND timestamp>=?
    """, (card_id, window_start.strftime("%Y-%m-%d %H:%M:%S")))
    txn_count = cursor.fetchone()[0]
    if txn_count >= MAX_TXN_IN_WINDOW:
        result.add(
            reason="Multiple withdrawals in short time",
            severity="HIGH",
            action="BLOCK"
        )

    # Rule 3: Session abuse
    session_window = datetime.now() - timedelta(minutes=SESSION_WINDOW_MINUTES)
    cursor.execute("""
        SELECT COUNT(*) FROM atm_session
        WHERE card_id=? AND created_at>=?
    """, (card_id, session_window.strftime("%Y-%m-%d %H:%M:%S")))
    session_count = cursor.fetchone()[0]
    if session_count >= MAX_SESSIONS_WINDOW:
        result.add(
            reason="Excessive ATM sessions detected",
            severity="HIGH",
            action="BLOCK"
        )
        
    # Rule 4: Impossible Travel (Location Velocity)
    if location != "UNKNOWN":
        cursor.execute("""
            SELECT location, timestamp FROM transactions
            WHERE card_id=? AND timestamp >= ?
            ORDER BY timestamp DESC LIMIT 1
        """, (card_id, window_start.strftime("%Y-%m-%d %H:%M:%S")))
        last_txn = cursor.fetchone()
        
        if last_txn:
            last_loc, last_time = last_txn
            if last_loc and last_loc != location:
                # Simple check: different location within 10 minutes
                result.add(
                    reason=f"Impossible travel detected: {last_loc} -> {location}",
                    severity="HIGH",
                    action="BLOCK"
                )

    conn.close()
    return result
