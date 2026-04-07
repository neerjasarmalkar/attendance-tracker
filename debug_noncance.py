from flask import Flask
from flask_mysqldb import MySQL

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'tracker'

mysql = MySQL(app)

with app.app_context():
    cur = mysql.connection.cursor()
    # Check column type
    cur.execute("DESCRIBE users")
    cols = cur.fetchall()
    print("--- COLUMNS ---")
    for col in cols:
        print(f"{col[0]}: {col[1]}")
    
    print("\n--- TEACHER ROWS ---")
    cur.execute("SELECT id, name, Tlive_lat, noncance FROM users WHERE role='teacher'")
    rows = cur.fetchall()
    for r in rows:
        print(r)
    cur.close()
