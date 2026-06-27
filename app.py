from flask import Flask, request, jsonify, send_from_directory
import sqlite3, os, hashlib, random, string, datetime
from flask_cors import CORS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bank_system_web.db')

app = Flask(__name__, static_folder='.')
CORS(app)

# --- Database helpers ---

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_number TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            stored_password TEXT,
            phone_number TEXT,
            balance REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def gen_account_number():
    while True:
        digits = ''.join(random.choices(string.digits, k=10))
        acc = f"ACC{digits}"
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE account_number=?', (acc,))
        if not cur.fetchone():
            conn.close()
            return acc
        conn.close()


def get_db_conn():
    return sqlite3.connect(DB_PATH)

# Initialize DB on startup
init_db()

# --- Static file routes ---
@app.route('/')
def index():
    return send_from_directory('.', 'dashboard.html')

@app.route('/<path:filename>')
def static_files(filename):
    # serve other html/css/js
    return send_from_directory('.', filename)

# --- API endpoints ---
@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    phone = (data.get('phone') or '').strip()
    if not username or not password:
        return jsonify(success=False, error='Username and password required')
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE username=?', (username,))
    if cur.fetchone():
        conn.close()
        return jsonify(success=False, error='Username already exists')
    account_number = gen_account_number()
    hashed = hash_password(password)
    try:
        cur.execute('INSERT INTO users (account_number, username, password, stored_password, phone_number, balance) VALUES (?, ?, ?, ?, ?, ?)',
                    (account_number, username, hashed, password, phone, 0.0))
        conn.commit()
        conn.close()
        return jsonify(success=True, account_number=account_number)
    except Exception as e:
        conn.close()
        return jsonify(success=False, error=str(e))

@app.route('/api/search')
def api_search():
    username = (request.args.get('username') or '').strip()
    if not username:
        return jsonify(success=False, error='username required')
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, account_number, username, phone_number, balance, created_at, stored_password FROM users WHERE username=?', (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify(success=False, error='User not found')
    user = {
        'id': row[0], 'account_number': row[1], 'username': row[2], 'phone_number': row[3], 'balance': row[4], 'created_at': row[5], 'stored_password': row[6] or ''
    }
    return jsonify(success=True, user=user)

@app.route('/api/users')
def api_users():
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('SELECT id, account_number, username, phone_number, balance, created_at FROM users ORDER BY created_at DESC')
    rows = cur.fetchall()
    conn.close()
    users = []
    for r in rows:
        users.append({'id': r[0], 'account_number': r[1], 'username': r[2], 'phone_number': r[3], 'balance': r[4], 'created_at': r[5]})
    return jsonify(success=True, users=users)

@app.route('/api/show_password')
def api_show_password():
    username = (request.args.get('username') or '').strip()
    if not username:
        return jsonify(success=False, error='username required')
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('SELECT stored_password FROM users WHERE username=?', (username,))
    r = cur.fetchone()
    conn.close()
    if not r:
        return jsonify(success=False, error='User not found')
    return jsonify(success=True, password=r[0] or '')

@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.get_json() or {}
    admin = (data.get('admin') or '').strip()
    pwd = (data.get('pwd') or '').strip()
    target = (data.get('target') or '').strip()
    if admin != 'Surya' or pwd != 'Surya@143':
        return jsonify(success=False, error='Invalid admin credentials')
    if not target:
        return jsonify(success=False, error='target username required')
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute('SELECT id FROM users WHERE username=?', (target,))
    r = cur.fetchone()
    if not r:
        conn.close()
        return jsonify(success=False, error='User not found')
    try:
        cur.execute('DELETE FROM users WHERE username=?', (target,))
        conn.commit()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        conn.close()
        return jsonify(success=False, error=str(e))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
