import sqlite3

db = sqlite3.connect("RIT.db")
c = db.cursor()
c.execute("ALTER TABLE totals RENAME COLUMN voice_hours to voice_seconds")
db.commit()
db.close()
