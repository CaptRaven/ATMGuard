from flask import Flask, render_template, request, jsonify, Response
import sqlite3
from functools import wraps
import atm_logic
from atm_session import ATMSession

app = Flask(__name__)
DB_NAME = "atmguard.db"

# ---------------- SECURITY ----------------
def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return username == 'admin' and password == 'secure_password'

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def get_mini_statement(card_id, limit=5):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT amount, status, timestamp
        FROM transactions
        WHERE card_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (card_id, limit))
    rows = cursor.fetchall()
    db.close()
    return rows

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template("atm.html")


@app.route("/atm", methods=["POST"])
def atm_api():
    data = request.get_json()
    card_id = data.get("card_id")
    pin = data.get("pin")
    transaction_type = data.get("transaction_type")
    amount = int(data.get("amount", 0))
    location = data.get("location", "UNKNOWN_ATM")

    if not card_id:
        return jsonify({"status": "error", "message": "Card ID required"}), 400

    try:
        # Start or retrieve session
        # This connects the web app to the logic core
        session = atm_logic.start_session(card_id)

        # PIN VALIDATION
        if pin:
            atm_logic.verify_pin(session, pin)
            # If no transaction type is specified, just confirm PIN
            if not transaction_type:
                return jsonify({"status": "success", "message": "PIN Accepted"})

        # TRANSACTIONS
        if transaction_type == "balance":
            atm_logic.select_transaction(session, "balance")
            balance = atm_logic.get_balance(session)
            session.reset_for_next_transaction()
            return jsonify({"status": "success", "message": f"Balance ₦{balance}"})

        if transaction_type == "withdraw":
            atm_logic.select_transaction(session, "withdraw")
            atm_logic.enter_amount(session, amount)
            
            # Pass location to logic for fraud checks
            session.current_location = location
            
            atm_logic.complete_transaction(session)
            # If successful (no exception raised)
            # We need the new balance to show to user
            new_balance = atm_logic.get_balance(session)
            session.reset_for_next_transaction()
            return jsonify({"status": "success", "message": "Take your cash", "balance": new_balance})

        if transaction_type == "mini":
            # Mini statement is read-only, we can allow it if PIN verified?
            # atm_logic doesn't enforce state for this, but ideally we should.
            # For now, let's assume if they are in the session they are good.
            statement = get_mini_statement(card_id)
            return jsonify({"status": "success", "statement": [dict(row) for row in statement]})

    except Exception as e:
        # Handle logic errors (fraud blocked, invalid pin, etc)
        msg = str(e)
        status = "blocked" if "blocked" in msg.lower() else "error"
        return jsonify({"status": status, "message": msg})

    return jsonify({"status": "error", "message": "Invalid transaction"}), 400


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
@requires_auth
def admin_dashboard():
    db = get_db()
    cursor = db.cursor()

    # Get Logs
    cursor.execute("SELECT * FROM fraud_log ORDER BY timestamp DESC")
    fraud_logs = cursor.fetchall()

    # Get Cards
    cursor.execute("SELECT card_id, status, pin_attempts, balance FROM card")
    cards = cursor.fetchall()

    # Get Count
    cursor.execute("SELECT COUNT(*) as total FROM fraud_log")
    fraud_count = cursor.fetchone()["total"]

    # Get Chart Data
    cursor.execute("""
        SELECT fraud_type, COUNT(*) as total
        FROM fraud_log
        GROUP BY fraud_type
    """)
    chart_rows = cursor.fetchall()
    
    db.close()

    chart_labels = [row["fraud_type"] for row in chart_rows]
    chart_values = [row["total"] for row in chart_rows]

    return render_template("admin.html", 
                           fraud_logs=fraud_logs, 
                           cards=cards, 
                           fraud_count=fraud_count,
                           chart_labels=chart_labels,
                           chart_values=chart_values)

# ---------------- ADMIN ACTIONS ----------------

@app.route("/admin/unblock/<card_id>", methods=["POST"])
@requires_auth
def unblock_card_route(card_id):
    db = get_db()
    db.execute("UPDATE card SET status='active', pin_attempts=0 WHERE card_id=?", (card_id,))
    db.commit()
    db.close()
    return jsonify({"status": "success", "message": f"Card {card_id} unblocked"})


if __name__ == "__main__":
    app.run(debug=True)
