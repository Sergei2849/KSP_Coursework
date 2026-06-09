#!/usr/bin/env bash
set -e

DB_NAME="${DB_NAME:-engine_coursework}"

createdb "$DB_NAME" 2>/dev/null || true
psql "$DB_NAME" -f database/schema.sql
psql "$DB_NAME" -f database/seed.sql

echo "База $DB_NAME подготовлена."
