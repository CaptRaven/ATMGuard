from enum import Enum, auto

class ATMState(Enum):
    IDLE = auto()
    CARD_INSERTED = auto()
    PIN_VERIFIED = auto()
    TRANSACTION_SELECTED = auto()
    AMOUNT_ENTERED = auto()
    COMPLETED = auto()
    BLOCKED = auto()
    EXPIRED = auto()
