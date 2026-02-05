from atm_session import ATMSession, get_session
from atm_states import ATMState
from fraud_engine import check_fraud
from datetime import datetime
from werkzeug.security import check_password_hash
import sqlite3

MAX_PIN_ATTEMPTS = 3

def start_session(card_id: str):
    # Log session start for fraud detection
    conn = sqlite3.connect("atmguard.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO atm_session (card_id, state) VALUES (?, ?)", (card_id, "STARTED"))
    conn.commit()
    conn.close()
    
    # Return in-memory session
    return get_session(card_id)

def get_balance(session: ATMSession):
    conn = session.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM card WHERE card_id=?", (session.card_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    raise Exception("Card not found")

def update_balance(session: ATMSession, new_balance):
    conn = session.get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE card SET balance=? WHERE card_id=?", (new_balance, session.card_id))
    conn.commit()
    conn.close()

def block_card(card_id, reason):
    conn = sqlite3.connect("atmguard.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE card SET status='blocked' WHERE card_id=?", (card_id,))
    cursor.execute("""
        INSERT INTO fraud_log (card_id, fraud_type, action_taken, timestamp)
        VALUES (?, ?, ?, ?)
    """, (card_id, reason, "Card blocked", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def verify_pin(session: ATMSession, pin: str):
    # Allow re-verification if already verified
    if session.state != ATMState.PIN_VERIFIED:
        session.require_state(ATMState.CARD_INSERTED)
    
    conn = session.get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT pin, pin_attempts, status FROM card WHERE card_id=?", (session.card_id,))
    row = cursor.fetchone()
    if not row:
        raise Exception("Card not found")
    db_pin, attempts, status = row
    if status == "blocked":
        raise Exception("Card is blocked")
    
    # Try verifying as hash first, fallback to plaintext (for migration safety)
    is_valid = False
    if db_pin.startswith("scrypt:") or db_pin.startswith("pbkdf2:"):
        is_valid = check_password_hash(db_pin, pin)
    else:
        is_valid = (db_pin == pin)

    if is_valid:
        session.state = ATMState.PIN_VERIFIED
        session.touch()
        # Reset attempts on success
        if attempts > 0:
            cursor.execute("UPDATE card SET pin_attempts=0 WHERE card_id=?", (session.card_id,))
            conn.commit()
        conn.close()
        return

    # If invalid, increment attempts but KEEP session alive
    attempts += 1
    
    # Refresh session activity immediately to prevent timeout race condition
    session.touch()

    if attempts >= MAX_PIN_ATTEMPTS:
        cursor.execute("UPDATE card SET status='blocked', pin_attempts=? WHERE card_id=?", (attempts, session.card_id))
        conn.commit()
        conn.close()
        raise Exception("Card blocked due to multiple wrong PIN attempts")
    cursor.execute("UPDATE card SET pin_attempts=? WHERE card_id=?", (attempts, session.card_id))
    conn.commit()
    conn.close()
    
    raise Exception(f"Invalid PIN ({attempts}/{MAX_PIN_ATTEMPTS})")

def select_transaction(session: ATMSession, transaction: str):
    session.require_state(ATMState.PIN_VERIFIED)
    if transaction not in ["withdraw", "balance"]:
        raise Exception("Invalid transaction")
    session.selected_transaction = transaction
    session.state = ATMState.TRANSACTION_SELECTED
    session.touch()

def enter_amount(session: ATMSession, amount: float):
    session.require_state(ATMState.TRANSACTION_SELECTED)
    if amount <= 0:
        raise Exception("Amount must be > 0")
    balance = get_balance(session)
    if session.selected_transaction == "withdraw" and amount > balance:
        raise Exception(f"Insufficient balance: ₦{balance}")
    session.amount = amount
    session.state = ATMState.AMOUNT_ENTERED
    session.touch()

def complete_transaction(session: ATMSession):
    session.check_timeout()
    fraud = check_fraud(
        card_id=session.card_id,
        amount=session.amount or 0,
        transaction_type=session.selected_transaction,
        location=session.current_location
    )

    if fraud.action == "BLOCK":
        block_card(session.card_id, ", ".join(fraud.reasons))
        raise Exception("Transaction blocked due to suspected fraud")

    if session.selected_transaction == "withdraw" and session.amount:
        balance = get_balance(session)
        update_balance(session, balance - session.amount)

    # Log transaction
    conn = session.get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (card_id, type, amount, status, timestamp, location)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        session.card_id,
        session.selected_transaction,
        session.amount or 0,
        "FLAGGED" if fraud.reasons else "COMPLETED",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        session.current_location
    ))
    for reason in fraud.reasons:
        cursor.execute("""
            INSERT INTO fraud_log (card_id, fraud_type, action_taken, timestamp)
            VALUES (?, ?, ?, ?)
        """, (
            session.card_id,
            reason,
            "Transaction flagged",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    conn.commit()
    conn.close()
    session.state = ATMState.COMPLETED
