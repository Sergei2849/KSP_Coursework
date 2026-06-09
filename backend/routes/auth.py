from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from backend.audit import write_action
from backend.auth import (
    MIN_PASSWORD_LEN,
    fetch_user_by_email,
    fetch_user_by_id,
    is_admin_email,
    is_valid_email,
    load_db_user,
    normalize_email,
    role_id_for_code,
    user_public,
)
from backend.db import query_one
from backend.log import get_logger

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")
log = get_logger()


@auth_bp.before_request
def _optional_user():
    load_db_user()


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""

    if len(name) < 2:
        return jsonify({"error": "Укажите имя пользователя"}), 400
    if not is_valid_email(email):
        return jsonify({"error": "Некорректный email"}), 400
    if len(password) < MIN_PASSWORD_LEN:
        return jsonify({"error": f"Пароль должен быть не короче {MIN_PASSWORD_LEN} символов"}), 400
    if fetch_user_by_email(email):
        return jsonify({"error": "Пользователь с таким email уже зарегистрирован"}), 409

    role_code = "admin" if is_admin_email(email) else "mechanic"
    role_id = role_id_for_code(role_code)
    if not role_id:
        return jsonify({"error": "Роли не загружены в БД"}), 500

    row = query_one(
        """
        INSERT INTO users (name, email, password_hash, role_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (name, email, generate_password_hash(password), role_id),
        commit=True,
    )
    user = user_public(fetch_user_by_id(row["id"]))
    log.info("Регистрация пользователя: id=%s email=%s role=%s", user["id"], email, user["role"])
    write_action(user["id"], "Регистрация", f"email={email}, role={user['role']}")
    return jsonify(user), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = normalize_email(data.get("email") or "")
    password = data.get("password") or ""

    if not is_valid_email(email):
        return jsonify({"error": "Некорректный email"}), 400
    if not password:
        return jsonify({"error": "Введите пароль"}), 400

    user = fetch_user_by_email(email)
    if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
        log.info("Неудачный вход: email=%s", email)
        return jsonify({"error": "Неверный email или пароль"}), 401

    public = user_public(user)
    log.info("Вход пользователя: id=%s email=%s role=%s", public["id"], email, public["role"])
    write_action(public["id"], "Вход", f"email={email}")
    return jsonify(public)


@auth_bp.get("/me")
def me():
    if not g.get("db_user"):
        return jsonify({"error": "Не авторизован"}), 401
    return jsonify(user_public(g.db_user))
