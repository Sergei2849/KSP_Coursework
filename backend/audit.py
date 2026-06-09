from backend.db import query
from backend.log import get_logger

log = get_logger()


def write_action(user_id, action, details=""):
    try:
        query(
            """
            INSERT INTO action_logs (user_id, action, details)
            VALUES (%s, %s, %s)
            """,
            (user_id, action, details),
            commit=True,
        )
    except Exception as exc:
        log.warning("Не удалось записать действие в таблицу action_logs: %s", exc)
