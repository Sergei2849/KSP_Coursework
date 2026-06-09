import os
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

BASE_DIR = Path(__file__).resolve().parent.parent
SQLITE_PATH = BASE_DIR / "database" / "demo.sqlite3"
TEST_PASSWORD_HASH = "pbkdf2:sha256:1000000$enginecoursework$30e3c2212d7c877a137ddef52c129b98abf43428cead0654cecd601e33c7b093"


def _default_database_url():
    user = os.getenv("USER") or os.getenv("USERNAME") or "postgres"
    return f"postgresql://{user}@127.0.0.1:5432/engine_coursework"


DATABASE_URL = os.getenv("DATABASE_URL") or _default_database_url()


def _is_sqlite():
    return DATABASE_URL.startswith("sqlite:///")


def _sqlite_file():
    return Path(DATABASE_URL.removeprefix("sqlite:///"))


def _sqlite_connect():
    path = _sqlite_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _init_sqlite(conn)
    return conn


def _init_sqlite(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS engines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT NOT NULL,
            engine_type TEXT NOT NULL,
            power_hp INTEGER,
            volume_liters REAL,
            serial_number TEXT UNIQUE,
            description TEXT,
            created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS engine_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engine_id INTEGER NOT NULL REFERENCES engines(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            part_code TEXT,
            condition TEXT NOT NULL DEFAULT 'Исправна',
            note TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS service_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            engine_id INTEGER NOT NULL REFERENCES engines(id) ON DELETE CASCADE,
            created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            client_name TEXT NOT NULL,
            phone TEXT,
            problem TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Обычный',
            status TEXT NOT NULL DEFAULT 'Новая',
            admin_comment TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIEW IF NOT EXISTS v_engines_full AS
        SELECT
            e.id,
            e.model,
            e.engine_type,
            e.power_hp,
            e.volume_liters,
            e.serial_number,
            e.description,
            e.created_at,
            e.updated_at,
            u.name AS created_by_name,
            u.email AS created_by_email,
            COUNT(DISTINCT p.id) AS parts_count,
            COUNT(DISTINCT r.id) AS requests_count
        FROM engines e
        JOIN users u ON u.id = e.created_by
        LEFT JOIN engine_parts p ON p.engine_id = e.id
        LEFT JOIN service_requests r ON r.engine_id = e.id
        GROUP BY e.id, u.name, u.email;

        CREATE VIEW IF NOT EXISTS v_service_requests_full AS
        SELECT
            r.id,
            r.client_name,
            r.phone,
            r.problem,
            r.priority,
            r.status,
            r.admin_comment,
            r.created_at,
            r.updated_at,
            e.model AS engine_model,
            e.serial_number AS engine_serial_number,
            u.name AS created_by_name,
            u.email AS created_by_email
        FROM service_requests r
        JOIN engines e ON e.id = r.engine_id
        JOIN users u ON u.id = r.created_by;

        CREATE VIEW IF NOT EXISTS v_request_status_stats AS
        SELECT status, COUNT(*) AS requests_count
        FROM service_requests
        GROUP BY status;
        """
    )
    _seed_sqlite(conn)
    conn.commit()


def _seed_sqlite(conn):
    conn.executemany(
        "INSERT OR IGNORE INTO roles (code, name) VALUES (?, ?)",
        [
            ("admin", "Администратор"),
            ("mechanic", "Механик"),
            ("client", "Клиент"),
        ],
    )
    role_ids = {
        row["code"]: row["id"]
        for row in conn.execute("SELECT id, code FROM roles").fetchall()
    }
    conn.executemany(
        """
        INSERT OR IGNORE INTO users (name, email, password_hash, role_id)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("Администратор", "admin@engine.local", TEST_PASSWORD_HASH, role_ids["admin"]),
            ("Иван Механик", "mechanic@engine.local", TEST_PASSWORD_HASH, role_ids["mechanic"]),
            ("Клиент сервиса", "client@engine.local", TEST_PASSWORD_HASH, role_ids["client"]),
        ],
    )
    mechanic = conn.execute("SELECT id FROM users WHERE email = ?", ("mechanic@engine.local",)).fetchone()
    client = conn.execute("SELECT id FROM users WHERE email = ?", ("client@engine.local",)).fetchone()
    if mechanic:
        conn.executemany(
            """
            INSERT OR IGNORE INTO engines
                (model, engine_type, power_hp, volume_liters, serial_number, description, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Toyota 2JZ-GE",
                    "Бензиновый рядный",
                    220,
                    3.00,
                    "ENG-2JZ-001",
                    "Атмосферный двигатель для учебного учета диагностики.",
                    mechanic["id"],
                ),
                (
                    "Cummins ISF 2.8",
                    "Дизельный",
                    150,
                    2.80,
                    "ENG-CUM-002",
                    "Дизельный двигатель легкого коммерческого транспорта.",
                    mechanic["id"],
                ),
            ],
        )
    engine_2jz = conn.execute("SELECT id FROM engines WHERE serial_number = ?", ("ENG-2JZ-001",)).fetchone()
    engine_cummins = conn.execute("SELECT id FROM engines WHERE serial_number = ?", ("ENG-CUM-002",)).fetchone()
    if engine_2jz:
        for part in [
            (engine_2jz["id"], "Топливный насос", "FUEL-219", "Требует проверки", "Плавающее давление на холостом ходу."),
            (engine_2jz["id"], "Свечи зажигания", "SPARK-11", "Исправна", "Плановая замена через 8000 км."),
        ]:
            exists = conn.execute(
                "SELECT id FROM engine_parts WHERE engine_id = ? AND part_code = ?",
                (part[0], part[2]),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO engine_parts (engine_id, name, part_code, condition, note)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    part,
                )
    if engine_cummins:
        exists = conn.execute(
            "SELECT id FROM engine_parts WHERE engine_id = ? AND part_code = ?",
            (engine_cummins["id"], "TURBO-28"),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO engine_parts (engine_id, name, part_code, condition, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (engine_cummins["id"], "Турбокомпрессор", "TURBO-28", "В диагностике", "Проверить люфт крыльчатки."),
            )
    if engine_2jz and client:
        exists = conn.execute("SELECT id FROM service_requests WHERE engine_id = ? AND created_by = ?", (engine_2jz["id"], client["id"])).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO service_requests
                    (engine_id, created_by, client_name, phone, problem, priority, status, admin_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    engine_2jz["id"],
                    client["id"],
                    "Петров Петр",
                    "+7 900 111-22-33",
                    "Двигатель троит после прогрева, заметна потеря мощности.",
                    "Высокий",
                    "В диагностике",
                    "Назначена компьютерная диагностика.",
                ),
            )


def _adapt_sql(sql):
    return sql.replace("%s", "?")


def get_connection():
    if _is_sqlite():
        return _sqlite_connect()
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def query(sql, params=None, *, commit=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(_adapt_sql(sql) if _is_sqlite() else sql, params or ())
            rows = cur.fetchall() if cur.description else None
        finally:
            cur.close()
        if commit:
            conn.commit()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_one(sql, params=None, *, commit=False):
    rows = query(sql, params, commit=commit)
    return rows[0] if rows else None
