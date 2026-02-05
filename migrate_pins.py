import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = "atmguard.db"

def migrate_pins():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT card_id, pin FROM card")
    cards = cursor.fetchall()

    print(f"Found {len(cards)} cards. checking PINs...")

    updated_count = 0
    for card in cards:
        pin = card["pin"]
        if not pin.startswith("scrypt:") and not pin.startswith("pbkdf2:"):
            # Needs hashing
            hashed_pin = generate_password_hash(pin)
            cursor.execute("UPDATE card SET pin = ? WHERE card_id = ?", (hashed_pin, card["card_id"]))
            updated_count += 1
            print(f"Hashed PIN for {card['card_id']}")
    
    conn.commit()
    conn.close()
    print(f"Migration complete. Hashed {updated_count} PINs.")

if __name__ == "__main__":
    migrate_pins()
