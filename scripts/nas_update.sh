#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BRANCH="${UPDATE_BRANCH:-main}"

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "ERROR: neither docker compose nor docker-compose is available"
  exit 1
}

cd "$ROOT_DIR"

echo "[1/7] Validate git repository"
git rev-parse --is-inside-work-tree >/dev/null

echo "[2/7] Fetch remote branch: $BRANCH"
git fetch origin "$BRANCH"

CURRENT_COMMIT="$(git rev-parse HEAD)"
REMOTE_COMMIT="$(git rev-parse "origin/$BRANCH")"

if [ "$CURRENT_COMMIT" = "$REMOTE_COMMIT" ]; then
  echo "Already up to date"
  exit 0
fi

echo "[3/7] Save rollback point"
echo "$CURRENT_COMMIT" > .last_update_prev_commit

echo "[4/7] Pull latest code"
git pull --ff-only origin "$BRANCH"

echo "[5/7] Rebuild and restart services"
compose_cmd up -d --build
compose_cmd restart frontend

echo "[6/7] Show container status"
compose_cmd ps

echo "[7/7] Update complete: $(git rev-parse --short HEAD)"
