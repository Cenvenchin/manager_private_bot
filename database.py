import sqlite3
import hashlib
import secrets

from contextlib import contextmanager
from datetime import datetime, timezone

DB_NAME = "manager_bot.db"


@contextmanager
def get_connection():
    """Создаёт безопасное подключение к SQLite."""

    connection = sqlite3.connect(DB_NAME, timeout=10)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    """Создаёт таблицы и индексы."""

    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                role TEXT NOT NULL DEFAULT 'user'
                    CHECK(role IN ('admin', 'user')),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN (
                        'pending',
                        'awaiting_pin',
                        'active',
                        'blocked'
                    )),
                pin_hash TEXT,
                pin_salt TEXT,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL CHECK(amount > 0),
                service TEXT NOT NULL CHECK(length(trim(service)) > 0),
                created_at TEXT NOT NULL,

                FOREIGN KEY (user_id)
                    REFERENCES users(id)
                    ON DELETE RESTRICT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_incomes_user_date
            ON incomes(user_id, created_at)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_status
            ON users(status)
        """)


def get_current_time():
    """Возвращает текущее время в UTC."""

    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )


def ensure_admin(telegram_id, first_name=None, username=None):
    """Создаёт или обновляет администратора."""

    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (
                telegram_id,
                username,
                first_name,
                role,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'admin', 'active', ?)
        """, (
            telegram_id,
            username,
            first_name,
            get_current_time()
        ))

        conn.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?,
                status = 'active'
            WHERE telegram_id = ? AND role = 'admin'
        """, (username, first_name, telegram_id))


def get_user_by_telegram_id(telegram_id):
    """Находит пользователя по Telegram ID."""

    with get_connection() as conn:

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        return dict(user) if user else None


def register_user(telegram_id, first_name=None, username=None):
    """Автоматически регистрирует нового пользователя."""

    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO users (
                telegram_id,
                username,
                first_name,
                role,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'user', 'active', ?)
        """, (
            telegram_id,
            username,
            first_name,
            get_current_time()
        ))

        # Обновляем данные уже зарегистрированного пользователя.
        # Старые заявки тоже автоматически активируются.
        conn.execute("""
            UPDATE users
            SET username = ?,
                first_name = ?,
                status = CASE
                    WHEN status IN ('pending', 'awaiting_pin')
                    THEN 'active'
                    ELSE status
                END
            WHERE telegram_id = ?
        """, (username, first_name, telegram_id))

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

        return dict(user), cursor.rowcount == 1


def approve_user(user_id):
    """Одобряет регистрацию пользователя."""

    with get_connection() as conn:

        cursor = conn.execute("""
            UPDATE users
            SET status = 'awaiting_pin'
            WHERE id = ?
              AND role = 'user'
              AND status = 'pending'
        """, (user_id,))

        return cursor.rowcount == 1


def hash_pin(pin):
    """Создаёт соль и хеш PIN-кода."""

    salt = secrets.token_hex(16)

    pin_hash = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt.encode("utf-8"),
        528_000
    ).hex()

    return pin_hash, salt


def verify_pin(pin, pin_hash, pin_salt):
    """Проверяет введённый PIN-код."""

    if not pin_hash or not pin_salt:
        return False

    calculated_hash = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        pin_salt.encode("utf-8"),
        528_000
    ).hex()

    return secrets.compare_digest(
        calculated_hash,
        pin_hash
    )


def set_user_pin(user_id, pin):
    """Сохраняет хеш PIN-кода пользователя."""

    if not pin.isdigit() or len(pin) != 4:
        raise ValueError("PIN должен состоять из 4 цифр")

    pin_hash, pin_salt = hash_pin(pin)

    with get_connection() as conn:

        cursor = conn.execute("""
            UPDATE users
            SET pin_hash = ?,
                pin_salt = ?,
                status = 'active'
            WHERE id = ?
              AND status = 'awaiting_pin'
        """, (pin_hash, pin_salt, user_id))

        return cursor.rowcount == 1


def add_income(user_id, amount, service):
    """Добавляет доход пользователя."""

    if not isinstance(amount, int) or amount <= 0:
        raise ValueError("Некорректная сумма")

    service = service.strip()

    if not service:
        raise ValueError("Название услуги не может быть пустым")

    with get_connection() as conn:

        cursor = conn.execute("""
            INSERT INTO incomes (
                user_id,
                amount,
                service,
                created_at
            )
            SELECT id, ?, ?, ?
            FROM users
            WHERE id = ?
              AND status = 'active'
        """, (
            amount,
            service,
            get_current_time(),
            user_id
        ))

        if cursor.rowcount != 1:
            raise ValueError("Пользователь не найден или заблокирован")

        return cursor.lastrowid
