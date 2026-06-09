BEGIN;

CREATE EXTENSION IF NOT EXISTS citext;

CREATE TABLE roles (
    id   SERIAL PRIMARY KEY,
    code VARCHAR(32)  NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(255) NOT NULL,
    email         CITEXT       NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id       INTEGER      NOT NULL REFERENCES roles (id) ON DELETE RESTRICT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_role_id ON users (role_id);

CREATE TABLE engines (
    id             SERIAL PRIMARY KEY,
    model          VARCHAR(255) NOT NULL,
    engine_type    VARCHAR(100) NOT NULL,
    power_hp       INTEGER CHECK (power_hp IS NULL OR power_hp > 0),
    volume_liters  NUMERIC(5, 2) CHECK (volume_liters IS NULL OR volume_liters > 0),
    serial_number  VARCHAR(100) UNIQUE,
    description    TEXT,
    created_by     INTEGER     NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_engines_created_by ON engines (created_by);

CREATE TABLE engine_parts (
    id         SERIAL PRIMARY KEY,
    engine_id  INTEGER      NOT NULL REFERENCES engines (id) ON DELETE CASCADE,
    name       VARCHAR(255) NOT NULL,
    part_code  VARCHAR(100),
    condition  VARCHAR(100) NOT NULL DEFAULT 'Исправна',
    note       TEXT,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_engine_parts_engine_id ON engine_parts (engine_id);

CREATE TABLE service_requests (
    id            SERIAL PRIMARY KEY,
    engine_id     INTEGER      NOT NULL REFERENCES engines (id) ON DELETE CASCADE,
    created_by    INTEGER      NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    client_name   VARCHAR(255) NOT NULL,
    phone         VARCHAR(50),
    problem       TEXT         NOT NULL,
    priority      VARCHAR(50)  NOT NULL DEFAULT 'Обычный',
    status        VARCHAR(50)  NOT NULL DEFAULT 'Новая',
    admin_comment TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_service_requests_engine_id ON service_requests (engine_id);
CREATE INDEX idx_service_requests_created_by ON service_requests (created_by);
CREATE INDEX idx_service_requests_status ON service_requests (status);

CREATE TABLE action_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users (id) ON DELETE SET NULL,
    action      VARCHAR(255) NOT NULL,
    details     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_engines_updated_at
    BEFORE UPDATE ON engines
    FOR EACH ROW
    EXECUTE PROCEDURE set_updated_at();

CREATE TRIGGER trg_service_requests_updated_at
    BEFORE UPDATE ON service_requests
    FOR EACH ROW
    EXECUTE PROCEDURE set_updated_at();

CREATE OR REPLACE FUNCTION validate_user_email()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.email IS NULL OR NEW.email::TEXT !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' THEN
        RAISE EXCEPTION 'Некорректный формат email';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_email_check
    BEFORE INSERT OR UPDATE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE validate_user_email();

CREATE OR REPLACE FUNCTION prevent_last_admin_delete()
RETURNS TRIGGER AS $$
DECLARE
    admin_role_id INTEGER;
    admin_count INTEGER;
BEGIN
    SELECT id INTO admin_role_id FROM roles WHERE code = 'admin';
    IF OLD.role_id = admin_role_id THEN
        SELECT COUNT(*) INTO admin_count FROM users WHERE role_id = admin_role_id;
        IF admin_count <= 1 THEN
            RAISE EXCEPTION 'Нельзя удалить последнего администратора';
        END IF;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_last_admin_delete
    BEFORE DELETE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE prevent_last_admin_delete();

CREATE OR REPLACE FUNCTION validate_service_request_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status NOT IN ('Новая', 'В диагностике', 'Ожидает деталь', 'Выполнена', 'Отменена') THEN
        RAISE EXCEPTION 'Недопустимый статус заявки: %', NEW.status;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_service_request_status_check
    BEFORE INSERT OR UPDATE ON service_requests
    FOR EACH ROW
    EXECUTE PROCEDURE validate_service_request_status();

CREATE VIEW v_engines_full AS
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

CREATE VIEW v_service_requests_full AS
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

CREATE VIEW v_request_status_stats AS
SELECT
    status,
    COUNT(*) AS requests_count
FROM service_requests
GROUP BY status;

CREATE OR REPLACE FUNCTION fn_engine_parts_count(p_engine_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM engine_parts
    WHERE engine_id = p_engine_id;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_user_request_count(p_user_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM service_requests
    WHERE created_by = p_user_id;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_search_engines(p_query TEXT)
RETURNS TABLE (
    id INTEGER,
    model VARCHAR,
    engine_type VARCHAR,
    serial_number VARCHAR,
    parts_count BIGINT,
    requests_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.model,
        e.engine_type,
        e.serial_number,
        e.parts_count,
        e.requests_count
    FROM v_engines_full e
    WHERE LOWER(e.model) LIKE LOWER('%' || p_query || '%')
       OR LOWER(e.engine_type) LIKE LOWER('%' || p_query || '%')
       OR LOWER(COALESCE(e.serial_number, '')) LIKE LOWER('%' || p_query || '%')
    ORDER BY e.model;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE PROCEDURE sp_change_request_status(
    p_request_id INTEGER,
    p_new_status VARCHAR,
    p_admin_id INTEGER,
    p_comment TEXT DEFAULT NULL
)
LANGUAGE plpgsql AS $$
DECLARE
    v_old_status VARCHAR;
BEGIN
    SELECT status INTO v_old_status
    FROM service_requests
    WHERE id = p_request_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Заявка % не найдена', p_request_id;
    END IF;

    UPDATE service_requests
    SET status = p_new_status,
        admin_comment = p_comment,
        updated_at = NOW()
    WHERE id = p_request_id;

    INSERT INTO action_logs (user_id, action, details)
    VALUES (
        p_admin_id,
        'Изменен статус заявки процедурой',
        'request_id=' || p_request_id || ', old=' || v_old_status || ', new=' || p_new_status
    );
END;
$$;

CREATE OR REPLACE PROCEDURE sp_update_part_condition(
    p_part_id INTEGER,
    p_condition VARCHAR,
    p_note TEXT DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM engine_parts WHERE id = p_part_id) THEN
        RAISE EXCEPTION 'Деталь % не найдена', p_part_id;
    END IF;

    UPDATE engine_parts
    SET condition = p_condition,
        note = COALESCE(p_note, note)
    WHERE id = p_part_id;
END;
$$;

CREATE OR REPLACE PROCEDURE sp_cancel_old_new_requests(p_days INTEGER DEFAULT 30)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE service_requests
    SET status = 'Отменена',
        admin_comment = 'Автоматическая отмена старой необработанной заявки',
        updated_at = NOW()
    WHERE status = 'Новая'
      AND created_at < NOW() - (p_days || ' days')::INTERVAL;
END;
$$;

COMMIT;
