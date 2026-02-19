# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Build arg to optionally install Playwright + Chromium (big download)
ARG INSTALL_PLAYWRIGHT=0

# ---- System deps + TeXLive ----
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl \
      # If you still use Playwright sometimes, these libs are needed for Chromium
      libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 \
      libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
      libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libgtk-3-0 \
      # LaTeX (pdflatex + packages your resume.cls uses)
      texlive-latex-base \
      texlive-latex-recommended \
      texlive-fonts-recommended \
      texlive-latex-extra \
      # Helpful utilities for reliable PDF builds
      latexmk \
      ghostscript \
    && apt-get clean

# ---- Python deps (cached wheels) ----
COPY requirements.txt ./

RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install -r requirements.txt

# ---- Optional Playwright browser install (cached) ----
RUN --mount=type=cache,target=/ms-playwright,sharing=locked \
    if [ "$INSTALL_PLAYWRIGHT" = "1" ]; then \
      python -m playwright install chromium; \
    else \
      echo "Skipping Playwright install (INSTALL_PLAYWRIGHT=0)"; \
    fi

# ---- App code last ----
COPY . .

# Your backend listens on 5001
EXPOSE 5001

# Longer timeout because LLM + LaTeX can take >60s
CMD ["gunicorn", "-b", "0.0.0.0:5001", "app:app", "--workers", "2", "--threads", "4", "--timeout", "300"]