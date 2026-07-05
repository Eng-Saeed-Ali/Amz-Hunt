#!/usr/bin/env bash
# =============================================================================
# Amz-Hunt — Automated VPS Deployment Script
# =============================================================================
# Purpose: One-command production deployment for the Amz-Hunt monitor.
#          Pulls latest code, validates environment, rebuilds container,
#          and cleans up stale Docker images to conserve VPS disk space.
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# Requirements:
#   - Docker Engine and Docker Compose installed on the target VPS.
#   - A valid .env file (copy from .env.example and fill in credentials).
#   - Git access to the repository (SSH key or credential helper configured).
# =============================================================================

set -e  # Exit immediately on any command failure (strict error handling).

# ── Step 0: Announce ────────────────────────────────────────────────────────
echo "========================================"
echo " Amz-Hunt — VPS Deployment"
echo " Started at $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "========================================"

# ── Step 1: Pull Latest Code ────────────────────────────────────────────────
echo ""
echo "[1/4] Pulling latest code from remote..."
git pull origin main 2>&1
echo "       Git pull completed successfully."

# ── Step 2: Validate .env Exists ────────────────────────────────────────────
echo ""
echo "[2/4] Checking environment configuration..."
if [ ! -f ".env" ]; then
    echo ""
    echo "  ╔══════════════════════════════════════════════════════════════╗"
    echo "  ║  ERROR: .env file not found!                                ║"
    echo "  ║                                                            ║"
    echo "  ║  The Amz-Hunt monitor requires TELEGRAM_BOT_TOKEN and      ║"
    echo "  ║  TELEGRAM_CHAT_ID to be set before deployment.             ║"
    echo "  ║                                                            ║"
    echo "  ║  Quick fix:                                                ║"
    echo "  ║    cp .env.example .env                                    ║"
    echo "  ║    nano .env   (add your real Telegram credentials)        ║"
    echo "  ║                                                            ║"
    echo "  ║  Then re-run:  ./deploy.sh                                 ║"
    echo "  ╚══════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi
echo "       .env file found — credentials are configured."

# ── Step 3: Build & Start Container ─────────────────────────────────────────
echo ""
echo "[3/4] Building image and starting container..."
docker compose up -d --build 2>&1
echo "       Container 'amz-hunt-bot' is now running."

# ── Step 4: Clean Up Stale Images ───────────────────────────────────────────
echo ""
echo "[4/4] Pruning dangling Docker images to reclaim disk space..."
docker image prune -f 2>&1
echo "       Cleanup complete."

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo " Deployment Complete"
echo "========================================"
echo ""
echo " Monitor status:"
docker compose ps 2>&1
echo ""
echo " Tail logs with:  docker compose logs -f"
echo ""