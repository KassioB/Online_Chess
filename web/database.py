''' Guarda as contas dos jogadores e as sessões de login em um banco SQLite '''

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time

DB_PATH = os.environ.get("CHESS_DB", os.path.join(os.path.dirname(__file__), "chess.db"))
SESSION_TTL = 7 * 24 * 3600  # sessões duram 7 dias
PBKDF2_ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                password_hash BLOB NOT NULL,
                salt BLOB NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                expires_at REAL NOT NULL
            );
        """)


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)


def create_user(username, password):
    # retorna uma mensagem de erro ou None se a conta foi criada
    if not USERNAME_RE.match(username):
        return "O nome de usuário deve ter de 3 a 20 letras, números ou _"
    if len(password) < 4:
        return "A senha deve ter pelo menos 4 caracteres"
    salt = os.urandom(16)
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, _hash_password(password, salt), salt, time.time()))
    except sqlite3.IntegrityError:
        return "Esse nome de usuário já existe"
    return None


def check_login(username, password):
    # retorna o nome do usuário (como foi cadastrado) se a senha estiver certa
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if row and hmac.compare_digest(row["password_hash"], _hash_password(password, row["salt"])):
        return row["username"]
    return None


def create_session(username):
    token = secrets.token_urlsafe(32)
    with _connect() as conn:
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()["id"]
        conn.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
                     (token, user_id, time.time() + SESSION_TTL))
    return token


def get_session_user(token):
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT users.username FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token = ? AND sessions.expires_at > ?", (token, time.time())).fetchone()
    return row["username"] if row else None


def delete_session(token):
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
