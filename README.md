# Курсовая работа по КСП

Учебное клиент-серверное приложение для учета двигателей, деталей и заявок на обслуживание.

Тема: **Информационная система учета двигателей и заявок на их обслуживание**.

## Что реализовано

- Регистрация пользователя.
- Вход по email и паролю.
- Валидация email на frontend и backend.
- Разделение ролей: администратор, механик, клиент.
- PostgreSQL база данных на 6 таблиц.
- 3 представления, 3 функции, 3 хранимые процедуры и 3 триггера в БД.
- Логирование действий в `logs/app.log`.
- Справочник двигателей.
- Справочник деталей двигателя.
- Заявки на обслуживание двигателя.
- Смена статуса заявки администратором.
- Страница статистики по двигателям, заявкам и действиям.
- CSV-выгрузка заявок.

## Стек

- Backend: Python, Flask.
- Database: PostgreSQL.
- Frontend: HTML, CSS, JavaScript без фреймворков.

## Структура

```text
backend/    Flask-приложение и API
database/   SQL-схема и стартовые данные
docs/       заметки для защиты
logs/       файл журнала действий
public/     HTML, CSS и JavaScript
uploads/    папка под будущие пользовательские файлы
```

## Таблицы БД

- `roles` - роли пользователей.
- `users` - пользователи, email, хеш пароля и роль.
- `engines` - справочник двигателей.
- `engine_parts` - детали двигателей.
- `service_requests` - заявки на обслуживание.
- `action_logs` - таблица под журнал действий.

## Расширения БД

Представления:

- `v_engines_full` - двигатели с количеством деталей и заявок.
- `v_service_requests_full` - заявки с данными двигателя и автора.
- `v_request_status_stats` - статистика заявок по статусам.

Функции:

- `fn_engine_parts_count(engine_id)` - количество деталей двигателя.
- `fn_user_request_count(user_id)` - количество заявок пользователя.
- `fn_search_engines(query)` - поиск двигателей по модели, типу или серийному номеру.

Хранимые процедуры:

- `sp_change_request_status` - смена статуса заявки с записью в журнал.
- `sp_update_part_condition` - безопасное обновление состояния детали.
- `sp_cancel_old_new_requests` - отмена старых необработанных заявок.

Триггеры:

- `trg_users_email_check` - проверка email на уровне БД.
- `trg_prevent_last_admin_delete` - защита от удаления последнего администратора.
- `trg_service_request_status_check` - проверка допустимого статуса заявки.

## Роли

- `admin` - видит все заявки, меняет статусы, смотрит логи, может удалять двигатели.
- `mechanic` - добавляет двигатели, детали и создает заявки.
- `client` - создает заявки и видит свои заявки.

## Запуск

Установить зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Подготовить базу:

```bash
createdb engine_coursework
psql engine_coursework -f database/schema.sql
psql engine_coursework -f database/seed.sql
```

Создать `.env` по примеру:

```bash
cp .env.example .env
```

Запустить приложение:

```bash
python -m backend.app
```

Открыть:

```text
http://localhost:3000
```

## Тестовые пользователи

После выполнения `database/seed.sql` можно войти:

```text
admin@engine.local
mechanic@engine.local
client@engine.local
```

Пароль для всех тестовых пользователей:

```text
1234
```

## API

- `POST /api/auth/register` - регистрация.
- `POST /api/auth/login` - вход.
- `GET /api/auth/me` - текущий пользователь.
- `GET /api/engines` - список двигателей.
- `POST /api/engines` - добавить двигатель.
- `PUT /api/engines/<id>` - изменить двигатель.
- `DELETE /api/engines/<id>` - удалить двигатель, только администратор.
- `GET /api/parts` - список деталей.
- `POST /api/parts` - добавить деталь.
- `GET /api/service-requests` - список заявок.
- `POST /api/service-requests` - создать заявку.
- `PATCH /api/service-requests/<id>` - изменить статус, только администратор.
- `GET /api/logs` - журнал действий, только администратор.
- `GET /api/stats` - статистика системы, администратор и механик.
