#!/usr/bin/env bash
set -euo pipefail

ODOO_BIN=${1:-/opt/odoo/odoo-bin}
shift || true

: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=odoo}"
: "${DB_PASSWORD:=odoo}"
: "${DB_NAME:=odoo}"

# Modules installed on first database init.
# Keep `base` and `web` so the web UI (/web/login) is available.
: "${ODOO_INIT_MODULES:=base,web}"

# Fail fast if core base data file is missing (common when the image was built
# from an incomplete context or addons paths are wrong).
if [ ! -f "/opt/odoo/odoo/addons/base/data/base_data.sql" ]; then
  echo "ERROR: Missing /opt/odoo/odoo/addons/base/data/base_data.sql in container."
  echo "Debug: printing odoo.addons search paths..."
  python -c "import odoo.addons; import sys; print('sys.path='); print('  ' + '\n  '.join(sys.path)); print('odoo.addons.__path__='); print('  ' + '\n  '.join(list(odoo.addons.__path__)))" || true
  exit 1
fi

db_is_initialized() {
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Atc \
    "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='ir_module_module' LIMIT 1;" 2>/dev/null \
    | grep -q '^1$'
}

module_is_installed() {
  local module_name="$1"
  PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Atc \
    "SELECT 1 FROM ir_module_module WHERE name='${module_name}' AND state='installed' LIMIT 1;" 2>/dev/null \
    | grep -q '^1$'
}

# Wait for Postgres
for i in {1..60}; do
  if PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" >/dev/null 2>&1; then
    break
  fi
  echo "Waiting for postgres at $DB_HOST:$DB_PORT... ($i/60)"
  sleep 1
done

if ! db_is_initialized; then
  echo "Database '$DB_NAME' is not initialized. Installing base..."
  "$ODOO_BIN" \
    --db_host "$DB_HOST" \
    --db_port "$DB_PORT" \
    --db_user "$DB_USER" \
    --db_password "$DB_PASSWORD" \
    -d "$DB_NAME" \
    -i "$ODOO_INIT_MODULES" \
    --without-demo=all \
    --stop-after-init \
    "$@"
  echo "Base installed. Starting Odoo..."
else
  # If DB exists but web isn't installed, /web/login will 404. Install web once.
  if ! module_is_installed web; then
    echo "Database '$DB_NAME' initialized but module 'web' not installed. Installing web..."
    "$ODOO_BIN" \
      --db_host "$DB_HOST" \
      --db_port "$DB_PORT" \
      --db_user "$DB_USER" \
      --db_password "$DB_PASSWORD" \
      -d "$DB_NAME" \
      -i web \
      --without-demo=all \
      --stop-after-init \
      "$@"
  fi
fi

exec "$ODOO_BIN" \
  --db_host "$DB_HOST" \
  --db_port "$DB_PORT" \
  --db_user "$DB_USER" \
  --db_password "$DB_PASSWORD" \
  -d "$DB_NAME" \
  "$@"

