# ═══════════════════════════════════════════════════════════════════
# Dockerfile — AI Marketing Engine
# Hugging Face Spaces · Docker SDK space
#
# Build stages:
#   1. Base OS + system deps (Chromium runtime libraries)
#   2. Python deps from requirements.txt
#   3. Playwright chromium browser download
#   4. App code copy + non-root user setup
#   5. Expose port 7860 (HF Spaces default) + launch Streamlit
#
# Persistent storage:
#   HF Spaces mounts /data as a persistent volume when the Space has
#   "Persistent storage" enabled. Our database.py auto-detects /data
#   and uses it for marketing_engine.db.
# ═══════════════════════════════════════════════════════════════════

# ── 1. Base image ────────────────────────────────────────────────
# python:3.11-slim-bookworm = Debian 12, minimal, fast build
FROM python:3.11-slim-bookworm

# ── 2. Build-time metadata ───────────────────────────────────────
LABEL maintainer="AI Marketing Engine"
LABEL description="24/7 Automated AI Marketing Dashboard on HF Spaces"

# Prevent Python from writing .pyc files and enable unbuffered logs
# so Streamlit output appears in real-time in HF build logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Tell Playwright where to store browser binaries inside the image
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    # Suppress Streamlit's "first run" browser-open prompt
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true \
    # HF Spaces expects the app on port 7860
    PORT=7860

# ── 3. System dependencies ───────────────────────────────────────
# These are the shared libraries Chromium needs at runtime on Debian.
# We install them as root before switching to a non-root user.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core Chromium runtime libs
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libwayland-client0 \
    # Font rendering (prevents blank screenshots)
    fonts-liberation \
    fonts-noto-color-emoji \
    # Network tools
    wget \
    ca-certificates \
    # Cleanup in same layer to keep image lean
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── 4. Create non-root user ──────────────────────────────────────
# HF Spaces security policy requires running as a non-root user.
# UID 1000 is the standard convention for HF.
RUN useradd -m -u 1000 appuser

# ── 5. Working directory ─────────────────────────────────────────
WORKDIR /app

# ── 6. Install Python dependencies ──────────────────────────────
# Copy requirements first so Docker layer-caches this step.
# Re-runs only when requirements.txt changes — not on every code edit.
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── 7. Install Playwright Chromium browser ───────────────────────
# playwright install downloads the browser binaries into
# PLAYWRIGHT_BROWSERS_PATH (/ms-playwright).
# --with-deps installs any remaining OS libs the bundled Chromium needs
# (belt-and-suspenders on top of step 3).
RUN playwright install chromium --with-deps

# ── 8. Copy application code ─────────────────────────────────────
COPY . .

# ── 9. Set ownership so appuser can write logs / temp files ──────
RUN chown -R appuser:appuser /app \
    && chmod -R 755 /app \
    # Give appuser write access to Playwright browser dir
    && chown -R appuser:appuser /ms-playwright

# ── 10. Ensure /data exists (HF persistent volume mount point) ───
# HF will mount its persistent volume here at runtime.
# We create the dir now so the path exists even if storage is off.
RUN mkdir -p /data && chown appuser:appuser /data

# ── 11. Switch to non-root user ──────────────────────────────────
USER appuser

# ── 12. Expose HF Spaces port ────────────────────────────────────
EXPOSE 7860

# ── 13. Health-check (optional but useful) ───────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:7860/_stcore/health || exit 1

# ── 14. Launch Streamlit ─────────────────────────────────────────
# --server.port          : must match EXPOSE above (HF routes 7860)
# --server.address       : bind to all interfaces inside the container
# --server.headless      : no browser auto-open (already set via ENV)
# --server.enableCORS    : false — HF proxy handles CORS
# --server.enableXsrfProtection : true — keep CSRF protection on
CMD ["streamlit", "run", "app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--server.enableCORS=false", \
     "--server.enableXsrfProtection=true"]
