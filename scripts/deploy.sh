#!/usr/bin/env sh
# Deploy the latest commit on the VPS. Run from the repository checkout on the server:
#   cd /docker/sarjy && sh scripts/deploy.sh
set -eu

cd "$(dirname "$0")/.."

if ! grep -q '^COOKIE_SECURE=true' .env; then
  echo "Refusing to deploy: set COOKIE_SECURE=true in .env (the site is served over HTTPS)." >&2
  exit 1
fi

git pull --ff-only
docker compose up -d --build

echo "Waiting for the app to become healthy..."
for _ in $(seq 1 30); do
  if [ "$(docker compose ps app --format '{{.Health}}')" = "healthy" ]; then
    docker image prune -f >/dev/null
    echo "Deployed $(git rev-parse --short HEAD)."
    exit 0
  fi
  sleep 2
done

echo "The app did not become healthy. Recent logs:" >&2
docker compose logs --tail 50 app >&2
exit 1
