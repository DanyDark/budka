import sqlite3
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")
DB_FILE = os.path.join(DATA_DIR, "users.db")

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Пользователи
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        nick TEXT NOT NULL,
        class TEXT,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    try:
    c.execute("ALTER TABLE users ADD COLUMN is_substitute INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    # Заявки
    c.execute('''CREATE TABLE IF NOT EXISTS pending_users (
        user_id INTEGER PRIMARY KEY,
        nick TEXT NOT NULL,
        class TEXT NOT NULL,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Опросы
    c.execute('''CREATE TABLE IF NOT EXISTS polls (
        poll_id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        meetings_json TEXT NOT NULL,
        is_active INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Ответы зарегистрированных
    c.execute('''CREATE TABLE IF NOT EXISTS poll_responses (
        user_id INTEGER,
        poll_id INTEGER,
        meeting TEXT,
        answer TEXT,
        responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, poll_id, meeting))''')

    # Ответы "за другого"
    c.execute('''CREATE TABLE IF NOT EXISTS external_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        poll_id INTEGER,
        external_nick TEXT,
        external_class TEXT,
        meeting TEXT,
        answer TEXT,
        admin_id INTEGER,
        responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    # Лидер пати (один на весь бот)
    c.execute('''CREATE TABLE IF NOT EXISTS party_leader (
        user_id INTEGER PRIMARY KEY)''')

    # Состав пати
    c.execute('''CREATE TABLE IF NOT EXISTS party_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        leader_id INTEGER NOT NULL,
        nick TEXT NOT NULL,
        class TEXT NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    conn.commit()
    conn.close()

# ---------- ПОЛЬЗОВАТЕЛИ ----------
def is_registered(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res is not None

def get_user_nick(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT nick FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_class(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT class FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def register_user(user_id, nick, user_class):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id, nick, class) VALUES (?, ?, ?)",
                (user_id, nick, user_class))
    conn.commit()
    conn.close()

def is_nick_taken(nick):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE nick=?", (nick,))
    if cur.fetchone():
        conn.close()
        return True
    cur.execute("SELECT 1 FROM pending_users WHERE nick=?", (nick,))
    res = cur.fetchone()
    conn.close()
    return res is not None

def add_pending_user(user_id, nick, user_class):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO pending_users VALUES (?,?,?,CURRENT_TIMESTAMP)",
                (user_id, nick, user_class))
    conn.commit()
    conn.close()

def is_pending(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pending_users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res is not None

def get_pending_users():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM pending_users ORDER BY requested_at")
    rows = cur.fetchall()
    conn.close()
    return rows

def confirm_all_pending():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id, nick, class FROM pending_users")
    pending = cur.fetchall()
    for uid, nick, cls in pending:
        cur.execute("INSERT OR REPLACE INTO users (user_id, nick, class) VALUES (?,?,?)",
                    (uid, nick, cls))
    cur.execute("DELETE FROM pending_users")
    conn.commit()
    conn.close()
    return pending

def remove_pending_user_by_nick(nick):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM pending_users WHERE nick=?", (nick,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id, nick, class FROM users ORDER BY registered_at")
    rows = cur.fetchall()
    conn.close()
    return rows
    
def set_substitute(user_id, status=True):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_substitute=? WHERE user_id=?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()

def is_substitute(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT is_substitute FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row and row[0] == 1

# ---------- ЛИДЕР ПАТИ ----------
def set_party_leader(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO party_leader (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_party_leader():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM party_leader")
    conn.commit()
    conn.close()

def get_party_leader():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM party_leader LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def is_party_leader(user_id):
    return get_party_leader() == user_id

# ---------- СОСТАВ ПАТИ ----------
def add_party_member(leader_id, nick, cls):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO party_members (leader_id, nick, class) VALUES (?, ?, ?)",
                (leader_id, nick, cls))
    conn.commit()
    conn.close()

def remove_party_member(leader_id, nick):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM party_members WHERE leader_id=? AND nick=?", (leader_id, nick))
    conn.commit()
    conn.close()

def get_party_members(leader_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT nick, class FROM party_members WHERE leader_id=? ORDER BY added_at", (leader_id,))
    rows = cur.fetchall()
    conn.close()
    return rows  # список кортежей (nick, class)

# ---------- ОПРОСЫ ----------
def create_poll(text, meetings):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE polls SET is_active=0")
    meetings_json = json.dumps(meetings, ensure_ascii=False)
    cur.execute("INSERT INTO polls (text, meetings_json, is_active) VALUES (?,?,1)", (text, meetings_json))
    conn.commit()
    conn.close()

def get_active_poll():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT poll_id, text, meetings_json FROM polls WHERE is_active=1")
    row = cur.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "text": row[1], "meetings": json.loads(row[2])}
    return None

def deactivate_poll():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE polls SET is_active=0")
    conn.commit()
    conn.close()

def save_responses_batch(user_id, poll_id, responses_dict):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    for meeting, answer in responses_dict.items():
        cur.execute(
            "INSERT OR REPLACE INTO poll_responses VALUES (?,?,?,?,CURRENT_TIMESTAMP)",
            (user_id, poll_id, meeting, answer))
    conn.commit()
    conn.close()

def save_external_response(poll_id, nick, cls, meeting, answer, admin_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO external_responses (poll_id, external_nick, external_class, meeting, answer, admin_id) VALUES (?,?,?,?,?,?)",
        (poll_id, nick, cls, meeting, answer, admin_id))
    conn.commit()
    conn.close()

def get_user_current_poll_answers(user_id):
    poll = get_active_poll()
    if not poll:
        return None
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT meeting, answer FROM poll_responses WHERE user_id=? AND poll_id=?", (user_id, poll['id']))
    rows = cur.fetchall()
    conn.close()
    return {m: a for m, a in rows}
    
def get_user_id_by_nick(nick):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE nick=?", (nick,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_non_responders(poll_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id, nick FROM users")
    all_users = cur.fetchall()
    cur.execute("SELECT DISTINCT user_id FROM poll_responses WHERE poll_id=?", (poll_id,))
    responders = {row[0] for row in cur.fetchall()}
    conn.close()
    return [(uid, nick) for uid, nick in all_users if uid not in responders]

def get_responses_grouped_by_meeting(poll_id):
    grouped = {}
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""SELECT u.nick, u.class, pr.meeting, pr.answer
                   FROM poll_responses pr JOIN users u ON pr.user_id=u.user_id
                   WHERE pr.poll_id=?""", (poll_id,))
    for nick, cls, meeting, answer in cur.fetchall():
        grouped.setdefault(meeting, []).append((nick, cls or "Не указан", answer))
    cur.execute("SELECT external_nick, external_class, meeting, answer FROM external_responses WHERE poll_id=?", (poll_id,))
    for nick, cls, meeting, answer in cur.fetchall():
        grouped.setdefault(meeting, []).append((nick, cls or "Внешний", answer))
    conn.close()
    return grouped
