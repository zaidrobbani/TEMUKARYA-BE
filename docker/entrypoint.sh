#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Menjalankan migrasi database..."
  alembic upgrade head
fi

exec "$@"
