import sqlite3

conn = sqlite3.connect("atmguard.db")
cursor = conn.cursor()

cursor.execute("ALTER TABLE card ADD COLUMN balance INTEGER DEFAULT 50000")

conn.commit()
conn.close()

print("Balance column added successfully")
