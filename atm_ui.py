from atm_session import ATMSession
from atm_logic import verify_pin, select_transaction, enter_amount, complete_transaction, get_balance
from atm_states import ATMState

def atm_ui():
    print("=== Welcome to ATMGuard ===")
    card_id = input("Insert card (enter Card ID): ").strip()
    
    session = ATMSession(card_id)

    # ---------------- PIN Verification ----------------
    while session.state == ATMState.CARD_INSERTED:
        pin = input("Enter PIN: ").strip()
        try:
            verify_pin(session, pin)
            print("PIN verified successfully.\n")
        except Exception as e:
            print(e)
            if "blocked" in str(e).lower():
                return  # Stop session if card blocked

    # ---------------- Transaction Loop ----------------
    while session.state in [ATMState.PIN_VERIFIED, ATMState.COMPLETED]:
        print("Select Transaction:")
        print("1) Withdraw")
        print("2) Check Balance")
        print("3) Exit")
        choice = input("Choice: ").strip()

        if choice == "1":
            select_transaction(session, "withdraw")
            while True:
                try:
                    amount = float(input("Enter withdrawal amount: ").strip())
                    enter_amount(session, amount)
                    complete_transaction(session)
                    print(f"Withdrawal of ₦{amount} completed successfully.\n")
                    session.reset_for_next_transaction()
                    break
                except Exception as e:
                    print(e)
                    retry = input("Try again? (y/n): ").strip().lower()
                    if retry != 'y':
                        session.reset_for_next_transaction()
                        break

        elif choice == "2":
            select_transaction(session, "balance")
            balance = get_balance(session)
            print(f"Your account balance is: ₦{balance}\n")
            session.reset_for_next_transaction()

        elif choice == "3":
            print("Thank you for using ATMGuard. Goodbye!")
            break

        else:
            print("Invalid choice. Try again.\n")

if __name__ == "__main__":
    atm_ui()
