#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: bash scripts/nas_rollback.sh <tag-or-commit>"
  exit 1
fi

TARGET_REF="$1"
ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

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

echo "[1/5] Fetch branches and tags"
git fetch --all --tags

echo "[2/5] Checkout $TARGET_REF"
git checkout "$TARGET_REF"

echo "[3/5] Rebuild and restart services"
compose_cmd up -d --build

echo "[4/5] Show container status"
compose_cmd ps

echo "[5/5] Rollback complete: $(git rev-parse --short HEAD)"
