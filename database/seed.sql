BEGIN;

INSERT INTO roles (code, name) VALUES
    ('admin', 'Администратор'),
    ('mechanic', 'Механик'),
    ('client', 'Клиент')
ON CONFLICT (code) DO NOTHING;

INSERT INTO users (name, email, password_hash, role_id)
SELECT 'Администратор', 'admin@engine.local',
       'pbkdf2:sha256:1000000$enginecoursework$30e3c2212d7c877a137ddef52c129b98abf43428cead0654cecd601e33c7b093',
       id
FROM roles
WHERE code = 'admin'
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (name, email, password_hash, role_id)
SELECT 'Иван Механик', 'mechanic@engine.local',
       'pbkdf2:sha256:1000000$enginecoursework$30e3c2212d7c877a137ddef52c129b98abf43428cead0654cecd601e33c7b093',
       id
FROM roles
WHERE code = 'mechanic'
ON CONFLICT (email) DO NOTHING;

INSERT INTO users (name, email, password_hash, role_id)
SELECT 'Клиент сервиса', 'client@engine.local',
       'pbkdf2:sha256:1000000$enginecoursework$30e3c2212d7c877a137ddef52c129b98abf43428cead0654cecd601e33c7b093',
       id
FROM roles
WHERE code = 'client'
ON CONFLICT (email) DO NOTHING;

INSERT INTO engines (model, engine_type, power_hp, volume_liters, serial_number, description, created_by)
SELECT 'Toyota 2JZ-GE', 'Бензиновый рядный', 220, 3.00, 'ENG-2JZ-001',
       'Атмосферный двигатель для учебного учета диагностики.',
       u.id
FROM users u
WHERE u.email = 'mechanic@engine.local'
ON CONFLICT (serial_number) DO NOTHING;

INSERT INTO engines (model, engine_type, power_hp, volume_liters, serial_number, description, created_by)
SELECT 'Cummins ISF 2.8', 'Дизельный', 150, 2.80, 'ENG-CUM-002',
       'Дизельный двигатель легкого коммерческого транспорта.',
       u.id
FROM users u
WHERE u.email = 'mechanic@engine.local'
ON CONFLICT (serial_number) DO NOTHING;

INSERT INTO engine_parts (engine_id, name, part_code, condition, note)
SELECT e.id, 'Топливный насос', 'FUEL-219', 'Требует проверки', 'Плавающее давление на холостом ходу.'
FROM engines e
WHERE e.serial_number = 'ENG-2JZ-001';

INSERT INTO engine_parts (engine_id, name, part_code, condition, note)
SELECT e.id, 'Свечи зажигания', 'SPARK-11', 'Исправна', 'Плановая замена через 8000 км.'
FROM engines e
WHERE e.serial_number = 'ENG-2JZ-001';

INSERT INTO engine_parts (engine_id, name, part_code, condition, note)
SELECT e.id, 'Турбокомпрессор', 'TURBO-28', 'В диагностике', 'Проверить люфт крыльчатки.'
FROM engines e
WHERE e.serial_number = 'ENG-CUM-002';

INSERT INTO service_requests (engine_id, created_by, client_name, phone, problem, priority, status, admin_comment)
SELECT e.id, u.id, 'Петров Петр', '+7 900 111-22-33',
       'Двигатель троит после прогрева, заметна потеря мощности.',
       'Высокий', 'В диагностике', 'Назначена компьютерная диагностика.'
FROM engines e
JOIN users u ON u.email = 'client@engine.local'
WHERE e.serial_number = 'ENG-2JZ-001';

COMMIT;
