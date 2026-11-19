#!/usr/bin/env sh
# Dump the database to backups/ and keep the last 14 days. Run nightly from cron, e.g.:
#   15 3 * * * cd /docker/sarjy && sh scripts/backup.sh >> backups/backup.log 2>&1
# Restore with:
#   docker compose exec -T db pg_restore -U sarjy -d sarjy --clean < backups/<file>.dump
set -eu

cd "$(dirname "$0")/.."
mkdir -p backups

file="backups/sarjy-$(date +%Y-%m-%d).dump"
docker compose exec -T db pg_dump -U sarjy -d sarjy --format=custom > "$file.tmp"
mv "$file.tmp" "$file"
find backups -name 'sarjy-*.dump' -mtime +14 -delete

echo "$(date -Iseconds) wrote $file"
