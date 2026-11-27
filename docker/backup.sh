#!/bin/sh
# Backup database + file upload produksi ke ~/backups (atau BACKUP_DIR). Panduan: docs/deploy.md
set -eu

cd "$(dirname "$0")/.."
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
STAMP="$(date +%F-%H%M)"
mkdir -p "$BACKUP_DIR"

docker compose -f docker-compose.prod.yml exec -T db sh -c \
  'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines "$MYSQL_DATABASE"' \
  | gzip > "$BACKUP_DIR/db-$STAMP.sql.gz"

docker run --rm -v temukarya-prod_uploads:/data:ro -v "$BACKUP_DIR":/backup alpine \
  tar czf "/backup/uploads-$STAMP.tar.gz" -C /data .

echo "Backup selesai: $BACKUP_DIR/db-$STAMP.sql.gz, $BACKUP_DIR/uploads-$STAMP.tar.gz"
