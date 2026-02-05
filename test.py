from atm_session import start_session
from atm_flow import enter_amount

card_id = "CARD123"

start_session(card_id)

# Skip PIN and transaction
enter_amount(card_id, 10000)
