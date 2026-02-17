# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=0 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# ---- System deps + TeXLive ----
# Use cache for apt metadata/packages to speed rebuilds
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libgtk-3-0 \
    texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps (cached wheels) ----
COPY requirements.txt ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# ---- Playwright browser install (cached) ----
# This is a big download; cache the browser directory
RUN --mount=type=cache,target=/ms-playwright \
    python -m playwright install chromium

# ---- App code last ----
COPY . .

EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app", "--workers", "2", "--threads", "4", "--timeout", "60"]
