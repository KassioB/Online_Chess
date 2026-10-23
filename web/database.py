''' Guarda as contas dos jogadores e as sessões de login no PostgreSQL.
O endereço do banco vem da variável de ambiente DATABASE_URL (no Render ela é configurada no
painel; no computador fica no arquivo .env na raiz do projeto). '''

import hashlib
import hmac
import os
import re
import secrets

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SESSION_TTL_DAYS = 7  # sessões duram 7 dias
PBKDF2_ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")

_pool = None


def _connect():
    return _pool.connection()


def init_db():
    global _pool
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Defina DATABASE_URL com o endereço do PostgreSQL (veja o .env.example)")
    _pool = ConnectionPool(
        url,
        min_size=1,
        max_size=5,
        # prepare_threshold=None: sem prepared statements, que não funcionam através do pooler do Neon
        kwargs={"row_factory": dict_row, "prepare_threshold": None},
        # o Neon desliga o banco quando fica parado: testa a conexão antes de usar e reconecta se caiu
        check=ConnectionPool.check_connection,
        open=True,
    )
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                username TEXT NOT NULL,
                password_hash BYTEA NOT NULL,
                salt BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )""")
        # nomes de usuário não diferenciam maiúsculas de minúsculas ("Kassio" e "kassio" são o mesmo)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower ON users (lower(username))")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TIMESTAMPTZ NOT NULL
            )""")
        conn.execute("DELETE FROM sessions WHERE expires_at <= now()")


def close_db():
    if _pool is not None:
        _pool.close()


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
                "INSERT INTO users (username, password_hash, salt) VALUES (%s, %s, %s)",
                (username, _hash_password(password, salt), salt))
    except psycopg.errors.UniqueViolation:
        return "Esse nome de usuário já existe"
    return None


def check_login(username, password):
    # retorna o nome do usuário (como foi cadastrado) se a senha estiver certa
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE lower(username) = lower(%s)", (username,)).fetchone()
    if row and hmac.compare_digest(bytes(row["password_hash"]), _hash_password(password, bytes(row["salt"]))):
        return row["username"]
    return None


def create_session(username):
    token = secrets.token_urlsafe(32)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) "
            "SELECT %s, id, now() + make_interval(days => %s) FROM users WHERE lower(username) = lower(%s)",
            (token, SESSION_TTL_DAYS, username))
    return token


def get_session_user(token):
    if not token:
        return None
    with _connect() as conn:
        row = conn.execute(
            "SELECT users.username FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token = %s AND sessions.expires_at > now()", (token,)).fetchone()
    return row["username"] if row else None


def delete_session(token):
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token = %s", (token,))
