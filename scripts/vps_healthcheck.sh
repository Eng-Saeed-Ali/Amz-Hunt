#!/usr/bin/env bash
# =============================================================================
# Amz-Hunt — VPS Health-Check Script
# =============================================================================
# Purpose: Lightweight production health-check for the amz-hunt-bot container.
#          Designed to run as a cron job on the VPS host (every 5 minutes).
#          If the container is down or unhealthy, it auto-restarts and logs
#          the incident with a UTC timestamp to a local incident log file.
#
# Crontab Setup (run on VPS host, NOT inside the container):
#   crontab -e
#   Add this line to run every 5 minutes:
#     */5 * * * * /path/to/Amz-Hunt/scripts/vps_healthcheck.sh >> /path/to/Amz-Hunt/data/vps_cron.log 2>&1
#
#   Replace /path/to/Amz-Hunt with the absolute path on your VPS
#   (e.g., /home/deploy/Amz-Hunt or /opt/amz-hunt).
#
# Requirements:
#   - Docker Engine installed on the VPS host.
#   - This script must be executable: chmod +x scripts/vps_healthcheck.sh
#   - The Amz-Hunt docker-compose.yml must be in the project root.
# =============================================================================

# ── Configuration ────────────────────────────────────────────────────────────
# Absolute path to the Amz-Hunt project root on the VPS.
# CHANGE THIS to match your VPS deployment path.
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

CONTAINER_NAME="amz-hunt-bot"
COMPOSE_SERVICE="amz-hunt-monitor"
INCIDENT_LOG="${PROJECT_ROOT}/data/vps_health_incidents.log"

# ── Check 1: Is the container running? ──────────────────────────────────────
CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "not_found")

if [ "$CONTAINER_STATUS" != "running" ]; then
    TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    echo "[${TIMESTAMP}] INCIDENT: Container '${CONTAINER_NAME}' is NOT running (status: ${CONTAINER_STATUS}). Restarting..." >> "$INCIDENT_LOG"

    cd "$PROJECT_ROOT" || exit 1
    docker compose restart "$COMPOSE_SERVICE" 2>&1

    TIMESTAMP_AFTER=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    echo "[${TIMESTAMP_AFTER}] ACTION: Restart command issued for '${COMPOSE_SERVICE}'." >> "$INCIDENT_LOG"
    exit 0
fi

# ── Check 2: Is the container healthy? ──────────────────────────────────────
# Note: Docker HEALTHCHECK must be defined in the Dockerfile or docker-compose.yml
# for the container to report a health status. If no HEALTHCHECK is configured,
# docker inspect will return an empty string for State.Health.Status, and this
# check is simply skipped (no false-positive incident logged).
HEALTH_STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "")

if [ -n "$HEALTH_STATUS" ] && [ "$HEALTH_STATUS" != "healthy" ]; then
    TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    echo "[${TIMESTAMP}] INCIDENT: Container '${CONTAINER_NAME}' is running but health status is '${HEALTH_STATUS}' (expected 'healthy'). Restarting..." >> "$INCIDENT_LOG"

    cd "$PROJECT_ROOT" || exit 1
    docker compose restart "$COMPOSE_SERVICE" 2>&1

    TIMESTAMP_AFTER=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
    echo "[${TIMESTAMP_AFTER}] ACTION: Restart command issued for '${COMPOSE_SERVICE}'." >> "$INCIDENT_LOG"
    exit 0
fi

# ── All Clear ────────────────────────────────────────────────────────────────
# Container is running and healthy (or health-check not configured yet).
# No incident logged — silent success to keep cron output minimal.
exit 0