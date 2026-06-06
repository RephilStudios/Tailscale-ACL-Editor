#!/usr/bin/env bash
set -euo pipefail

cd /opt/shiner-connect

# ── Color helpers ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 1. Prerequisites ──
info "Checking prerequisites..."

if ! command -v docker &>/dev/null; then
    error "Docker is not installed or not in PATH."
    exit 1
fi

if ! docker compose version &>/dev/null; then
    error "Docker Compose plugin not found. Is 'docker-compose' (standalone) installed instead?"
    exit 1
fi

if [ ! -f .env ]; then
    error ".env file not found in $(pwd). Create one before running this script."
    exit 1
fi

info "Prerequisites OK."

# ── 0.5. Load .env ──
set -a
. .env
set +a

info "Using DB_USER=$DB_USER"

# ── 2. Pull images ──
info "Pulling latest images..."
docker compose pull

# ── 3. Start the stack ──
info "Starting the stack..."
docker compose up -d

# ── 4. Wait for PostgreSQL to be healthy ──
info "Waiting for PostgreSQL to be ready..."
for i in $(seq 1 60); do
    if docker compose exec -T db pg_isready -U "$DB_USER" &>/dev/null; then
        break
    fi
    sleep 2
done

# ── 5. Run migrations ──
info "Running database migrations..."
docker compose exec -T web python manage.py migrate

# ── 6. Done ──
echo
info "Bootstrap complete! Containers are running."
echo
warn "Run this next to create your admin user:"
warn "  cd /opt/shiner-connect && docker compose exec web python manage.py createsuperuser"
echo
warn "Then configure the license server credentials on the DGX License Server (port 8005)."
