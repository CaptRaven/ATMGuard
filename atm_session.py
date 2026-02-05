import time
import sqlite3
from atm_states import ATMState

SESSION_TIMEOUT = 30  # seconds for testing

class ATMSession:
    def __init__(self, card_id: str, db_path="atmguard.db"):
        self.card_id = card_id
        self.state = ATMState.CARD_INSERTED
        self.pin_attempts = 0
        self.selected_transaction = None
        self.amount = None
        self.last_activity = time.time()
        self.db_path = db_path
        self.current_location = "UNKNOWN"

    def touch(self):
        self.last_activity = time.time()

    def check_timeout(self):
        # Extend timeout logic to handle rapid wrong PINs appropriately
        if time.time() - self.last_activity > SESSION_TIMEOUT:
            self.state = ATMState.EXPIRED
            raise Exception("Session expired due to inactivity")

    def require_state(self, required_state: ATMState):
        # Do not check timeout if we are just starting or handling exceptions
        if required_state != ATMState.CARD_INSERTED:
            self.check_timeout()
            
        if self.state != required_state:
            raise Exception(f"Action not allowed. Required: {required_state.name}, Current: {self.state.name}")

    def reset_for_next_transaction(self):
        self.selected_transaction = None
        self.amount = None
        self.state = ATMState.PIN_VERIFIED
        self.touch()

    def get_db(self):
        return sqlite3.connect(self.db_path)

# Global storage for active sessions (in-memory for simplicity)
_sessions = {}

def get_session(card_id: str) -> ATMSession:
    if card_id not in _sessions:
        _sessions[card_id] = ATMSession(card_id)
    return _sessions[card_id]

def get_current_state(card_id: str):
    session = get_session(card_id)
    session.check_timeout()
    return session.state

def update_state(card_id: str, new_state: ATMState):
    session = get_session(card_id)
    session.state = new_state
    session.touch()
