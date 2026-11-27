#!/usr/bin/env bash
# Deploy di server: tarik branch terbaru, build ulang, tunggu API sehat.
# Dipanggil GitHub Actions lewat SSH (lihat .github/workflows/ci-cd.yml) atau manual: bash docker/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."
BRANCH="${DEPLOY_BRANCH:-main}"

# Versi baru bisa membawa migrasi: backup dulu selama DB sudah jalan.
if [ -n "$(docker compose ps -q db 2>/dev/null)" ]; then
  sh docker/backup.sh
fi

git fetch --prune origin "$BRANCH"
git checkout -q "$BRANCH"
# --ff-only: gagal (bukan menimpa) kalau ada commit lokal di server.
git merge --ff-only "origin/$BRANCH"
echo "Deploy $BRANCH @ $(git rev-parse --short HEAD): $(git log -1 --format=%s)"

docker compose up -d --build --remove-orphans

api="$(docker compose ps -q api)"
for _ in $(seq 1 36); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$api" 2>/dev/null || echo unknown)"
  if [ "$status" = "healthy" ]; then
    echo "API sehat."
    docker image prune -f >/dev/null
    exit 0
  fi
  sleep 5
done

echo "API tidak sehat setelah 3 menit (status: $status)." >&2
docker compose ps >&2
docker compose logs --tail 80 api >&2
exit 1
