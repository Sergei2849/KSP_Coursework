import os
import re

from flask import g, jsonify, request

from backend.db import query_one

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MIN_PASSWORD_LEN = 4


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email))


def is_admin_email(email: str) -> bool:
    admin_email = normalize_email(os.getenv("ADMIN_EMAIL", ""))
    return bool(admin_email) and normalize_email(email) == admin_email


def role_id_for_code(code: str):
    row = query_one("SELECT id FROM roles WHERE code = %s", (code,))
    return row["id"] if row else None


def fetch_user_by_email(email: str):
    return query_one(
        """
        SELECT u.id, u.name, u.email, u.password_hash,
               r.code AS role, r.name AS role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.email = %s
        """,
        (normalize_email(email),),
    )


def fetch_user_by_id(user_id: int):
    return query_one(
        """
        SELECT u.id, u.name, u.email, r.code AS role, r.name AS role_name
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s
        """,
        (user_id,),
    )


def user_public(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "role_name": row["role_name"],
    }


def load_db_user():
    raw_user_id = request.headers.get("X-User-Id")
    if not raw_user_id:
        g.db_user = None
        return None

    try:
        user_id = int(raw_user_id)
    except ValueError:
        return jsonify({"error": "Некорректный идентификатор пользователя"}), 400

    row = fetch_user_by_id(user_id)
    if not row:
        return jsonify({"error": "Пользователь не найден"}), 401

    g.db_user = dict(row)
    return None


def require_user():
    if not g.get("db_user"):
        return jsonify({"error": "Сначала выполните вход"}), 401
    return None


def require_role(*codes):
    err = require_user()
    if err:
        return err
    if g.db_user["role"] not in codes:
        return jsonify({"error": "Недостаточно прав для этой операции"}), 403
    return None
