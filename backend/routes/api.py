from flask import Blueprint, g, jsonify, request

from backend.audit import write_action
from backend.auth import load_db_user, require_role, require_user
from backend.db import query, query_one
from backend.log import get_logger

api_bp = Blueprint("api", __name__, url_prefix="/api")
log = get_logger()

REQUEST_STATUSES = {"Новая", "В диагностике", "Ожидает деталь", "Выполнена", "Отменена"}


@api_bp.before_request
def _load_user():
    response = load_db_user()
    if response is not None:
        return response


@api_bp.get("/engines")
def list_engines():
    err = require_user()
    if err:
        return err

    rows = query(
        """
        SELECT *, created_by_name AS owner_name
        FROM v_engines_full
        ORDER BY created_at DESC
        """
    )
    return jsonify([dict(row) for row in rows])


@api_bp.post("/engines")
def create_engine():
    err = require_role("admin", "mechanic")
    if err:
        return err

    data = request.get_json(silent=True) or {}
    model = (data.get("model") or "").strip()
    engine_type = (data.get("engine_type") or "").strip()
    power_hp = data.get("power_hp")
    volume_liters = data.get("volume_liters")
    serial_number = (data.get("serial_number") or "").strip()
    description = (data.get("description") or "").strip()

    if len(model) < 2:
        return jsonify({"error": "Укажите модель двигателя"}), 400
    if len(engine_type) < 2:
        return jsonify({"error": "Укажите тип двигателя"}), 400

    row = query_one(
        """
        INSERT INTO engines
            (model, engine_type, power_hp, volume_liters, serial_number, description, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (model, engine_type, power_hp or None, volume_liters or None, serial_number or None, description, g.db_user["id"]),
        commit=True,
    )
    log.info("Добавлен двигатель id=%s model=%r user=%s", row["id"], model, g.db_user["id"])
    write_action(g.db_user["id"], "Добавлен двигатель", f"id={row['id']}, model={model}")
    return jsonify(dict(row)), 201


@api_bp.put("/engines/<int:engine_id>")
def update_engine(engine_id):
    err = require_role("admin", "mechanic")
    if err:
        return err

    engine = query_one("SELECT * FROM engines WHERE id = %s", (engine_id,))
    if not engine:
        return jsonify({"error": "Двигатель не найден"}), 404

    data = request.get_json(silent=True) or {}
    model = (data.get("model") or engine["model"]).strip()
    engine_type = (data.get("engine_type") or engine["engine_type"]).strip()
    power_hp = data.get("power_hp", engine["power_hp"])
    volume_liters = data.get("volume_liters", engine["volume_liters"])
    serial_number = (data.get("serial_number") or engine["serial_number"] or "").strip()
    description = (data.get("description") or engine["description"] or "").strip()

    row = query_one(
        """
        UPDATE engines
        SET model = %s, engine_type = %s, power_hp = %s, volume_liters = %s,
            serial_number = %s, description = %s
        WHERE id = %s
        RETURNING *
        """,
        (model, engine_type, power_hp or None, volume_liters or None, serial_number or None, description, engine_id),
        commit=True,
    )
    log.info("Обновлен двигатель id=%s user=%s", engine_id, g.db_user["id"])
    write_action(g.db_user["id"], "Обновлен двигатель", f"id={engine_id}")
    return jsonify(dict(row))


@api_bp.delete("/engines/<int:engine_id>")
def delete_engine(engine_id):
    err = require_role("admin")
    if err:
        return err

    row = query_one("DELETE FROM engines WHERE id = %s RETURNING id", (engine_id,), commit=True)
    if not row:
        return jsonify({"error": "Двигатель не найден"}), 404
    log.info("Удален двигатель id=%s admin=%s", engine_id, g.db_user["id"])
    write_action(g.db_user["id"], "Удален двигатель", f"id={engine_id}")
    return jsonify({"ok": True})


@api_bp.get("/parts")
def list_parts():
    err = require_user()
    if err:
        return err

    engine_id = request.args.get("engine_id")
    search = (request.args.get("q") or "").strip()
    sql = """
        SELECT p.*, e.model AS engine_model
        FROM engine_parts p
        JOIN engines e ON e.id = p.engine_id
    """
    params = []
    where = []
    if engine_id:
        where.append("p.engine_id = %s")
        params.append(engine_id)
    if search:
        where.append("(LOWER(p.name) LIKE LOWER(%s) OR LOWER(p.part_code) LIKE LOWER(%s))")
        params.extend([f"%{search}%", f"%{search}%"])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.name"

    rows = query(sql, tuple(params))
    return jsonify([dict(row) for row in rows])


@api_bp.post("/parts")
def create_part():
    err = require_role("admin", "mechanic")
    if err:
        return err

    data = request.get_json(silent=True) or {}
    engine_id = data.get("engine_id")
    name = (data.get("name") or "").strip()
    part_code = (data.get("part_code") or "").strip()
    condition = (data.get("condition") or "Исправна").strip()
    note = (data.get("note") or "").strip()

    if not engine_id or not query_one("SELECT id FROM engines WHERE id = %s", (engine_id,)):
        return jsonify({"error": "Выберите существующий двигатель"}), 400
    if len(name) < 2:
        return jsonify({"error": "Укажите название детали"}), 400

    row = query_one(
        """
        INSERT INTO engine_parts (engine_id, name, part_code, condition, note)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (engine_id, name, part_code or None, condition, note),
        commit=True,
    )
    log.info("Добавлена деталь id=%s engine=%s user=%s", row["id"], engine_id, g.db_user["id"])
    write_action(g.db_user["id"], "Добавлена деталь", f"id={row['id']}, engine={engine_id}")
    return jsonify(dict(row)), 201


@api_bp.get("/service-requests")
def list_service_requests():
    err = require_user()
    if err:
        return err

    role = g.db_user["role"]
    user_id = g.db_user["id"]
    base_sql = """
        SELECT *, created_by_name AS author_name
        FROM v_service_requests_full
    """
    if role == "admin":
        rows = query(base_sql + " ORDER BY created_at DESC")
    else:
        rows = query(
            base_sql + " WHERE created_by_email = %s ORDER BY created_at DESC",
            (g.db_user["email"],),
        )
    return jsonify([dict(row) for row in rows])


@api_bp.post("/service-requests")
def create_service_request():
    err = require_role("admin", "mechanic", "client")
    if err:
        return err

    data = request.get_json(silent=True) or {}
    engine_id = data.get("engine_id")
    client_name = (data.get("client_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    problem = (data.get("problem") or "").strip()
    priority = (data.get("priority") or "Обычный").strip()

    if not engine_id or not query_one("SELECT id FROM engines WHERE id = %s", (engine_id,)):
        return jsonify({"error": "Выберите двигатель из справочника"}), 400
    if len(client_name) < 3:
        return jsonify({"error": "Укажите ФИО клиента"}), 400
    if len(problem) < 10:
        return jsonify({"error": "Описание проблемы должно быть подробнее"}), 400

    row = query_one(
        """
        INSERT INTO service_requests
            (engine_id, created_by, client_name, phone, problem, priority)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (engine_id, g.db_user["id"], client_name, phone, problem, priority),
        commit=True,
    )
    log.info("Создана заявка id=%s engine=%s user=%s", row["id"], engine_id, g.db_user["id"])
    write_action(g.db_user["id"], "Создана заявка", f"id={row['id']}, engine={engine_id}")
    return jsonify(dict(row)), 201


@api_bp.patch("/service-requests/<int:request_id>")
def update_service_request_status(request_id):
    err = require_role("admin")
    if err:
        return err

    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    admin_comment = (data.get("admin_comment") or "").strip()

    if status not in REQUEST_STATUSES:
        return jsonify({"error": "Недопустимый статус заявки"}), 400

    row = query_one(
        """
        UPDATE service_requests
        SET status = %s, admin_comment = %s
        WHERE id = %s
        RETURNING *
        """,
        (status, admin_comment, request_id),
        commit=True,
    )
    if not row:
        return jsonify({"error": "Заявка не найдена"}), 404
    log.info("Изменен статус заявки id=%s status=%r admin=%s", request_id, status, g.db_user["id"])
    write_action(g.db_user["id"], "Изменен статус заявки", f"id={request_id}, status={status}")
    return jsonify(dict(row))


@api_bp.get("/logs")
def read_logs():
    err = require_role("admin")
    if err:
        return err

    from backend.log import LOG_FILE

    if not LOG_FILE.exists():
        return jsonify([])
    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    return jsonify(list(reversed(lines[-80:])))


@api_bp.get("/stats")
def get_stats():
    err = require_role("admin", "mechanic")
    if err:
        return err

    totals = {
        "engines": query_one("SELECT COUNT(*) AS count FROM engines")["count"],
        "parts": query_one("SELECT COUNT(*) AS count FROM engine_parts")["count"],
        "requests": query_one("SELECT COUNT(*) AS count FROM service_requests")["count"],
        "users": query_one("SELECT COUNT(*) AS count FROM users")["count"],
    }
    status_rows = query(
        """
        SELECT status, requests_count
        FROM v_request_status_stats
        ORDER BY requests_count DESC, status
        """
    )
    engine_rows = query(
        """
        SELECT id, model, serial_number, parts_count, requests_count
        FROM v_engines_full
        ORDER BY requests_count DESC, parts_count DESC, model
        LIMIT 10
        """
    )
    recent_actions = query(
        """
        SELECT l.created_at, l.action, l.details, u.name AS user_name
        FROM action_logs l
        LEFT JOIN users u ON u.id = l.user_id
        ORDER BY l.created_at DESC
        LIMIT 10
        """
    )

    return jsonify(
        {
            "totals": totals,
            "statuses": [dict(row) for row in status_rows],
            "engines": [dict(row) for row in engine_rows],
            "recent_actions": [dict(row) for row in recent_actions],
        }
    )
