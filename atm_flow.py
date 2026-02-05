from atm_states import (
    CARD_INSERTED,
    PIN_VERIFIED,
    TRANSACTION_SELECTED,
    AMOUNT_ENTERED
)

from atm_session import (
    get_current_state,
    update_state
)

from fraud_logger import (
    log_fraud,
    increment_violation_count
)

from security_checks import is_card_blocked
from fraud_rules import check_withdrawal_fraud
import sqlite3
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "atmguard.db")


def get_connection():
    return sqlite3.connect(DB_NAME, isolation_level=None)


# ---------------- STEP 1: PIN ----------------
def verify_pin(card_id, pin_correct):
    if is_card_blocked(card_id):
        raise Exception("Card is blocked")

    state = get_current_state(card_id)

    if state != CARD_INSERTED:
        increment_violation_count(card_id)
        log_fraud(card_id, "PIN entered in invalid state")
        raise Exception(f"PIN not allowed in state: {state}")

    if not pin_correct:
        return False

    update_state(card_id, PIN_VERIFIED)
    return True


# ---------------- STEP 2: TRANSACTION ----------------
def select_transaction(card_id):
    if is_card_blocked(card_id):
        raise Exception("Card is blocked")

    state = get_current_state(card_id)

    if state != PIN_VERIFIED:
        increment_violation_count(card_id)
        log_fraud(card_id, "Transaction selected in invalid state")
        raise Exception(f"Transaction not allowed in state: {state}")

    update_state(card_id, TRANSACTION_SELECTED)
    return "Withdrawal selected"


# ---------------- STEP 3: AMOUNT + FRAUD CHECK ----------------
def enter_amount(card_id, amount):
    if is_card_blocked(card_id):
        raise Exception("Card is blocked")

    state = get_current_state(card_id)

    if state != TRANSACTION_SELECTED:
        increment_violation_count(card_id)
        log_fraud(card_id, "Amount entered in invalid state")
        raise Exception(f"Amount not allowed in state: {state}")

    # -------- FRAUD ANALYSIS --------
    fraud_reasons = check_withdrawal_fraud(card_id, amount)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO transactions (card_id, amount)
        VALUES (?, ?)
    """, (card_id, amount))

    if fraud_reasons:
        for reason in fraud_reasons:
            log_fraud(card_id, reason)

    update_state(card_id, AMOUNT_ENTERED)
    conn.close()

    if fraud_reasons:
        return f"Transaction flagged: {', '.join(fraud_reasons)}"

    return "Withdrawal successful"
