# =============================================================================
# Amz-Hunt — Production Docker Image
# =============================================================================
# Base: python:3.11-slim (minimal Debian-based image, ~50 MB compressed)
# Target: 24/7 VPS deployment for Amazon Egypt promo monitoring
# =============================================================================

FROM python:3.11-slim

# ── Environment Variables ───────────────────────────────────────────────────
# PYTHONDONTWRITEBYTECODE=1 : Prevent __pycache__ .pyc files inside container.
# PYTHONUNBUFFERED=1        : stdout/stderr unbuffered → docker logs works real-time.
# PYTHONPATH=/app           : Ensures `python -m scripts.run_monitor` resolves src.* imports.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# ── Working Directory ───────────────────────────────────────────────────────
WORKDIR /app

# ── System Dependencies ─────────────────────────────────────────────────────
# curl_cffi requires libcurl with impersonation patches.
# lxml requires libxml2 and libxslt (C libraries).
# Clean apt cache to keep image small.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libcurl4-openssl-dev \
        libxml2 \
        libxslt1.1 \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Python Dependencies ─────────────────────────────────────────────────────
# Copy requirements.txt first (Docker layer caching — dependencies only rebuild
# when requirements.txt changes, not when application code changes).
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application Source ──────────────────────────────────────────────────────
# Copy src/ and scripts/ directories (the only directories needed at runtime).
# data/ is NOT copied — it's a bind-mounted volume for runtime state.
COPY src/ ./src/
COPY scripts/ ./scripts/

# ── Runtime ─────────────────────────────────────────────────────────────────
# Single entry point per Architecture_Blueprint §4.2.
# The orchestrator runs indefinitely until SIGTERM from docker stop.
CMD ["python", "-m", "scripts.run_monitor"]