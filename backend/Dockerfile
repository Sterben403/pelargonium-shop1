# Production image of the Pelargonium Shop API (widget, owner workspace and API in one service).
#   docker build -t pelargonium-shop --build-arg APP_VERSION=$(git rev-parse HEAD) backend
#   docker run -p 8010:8000 -e DATABASE_URL=... -e ADMIN_PASSWORD=... -e SECRET_KEY=... pelargonium-shop
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# security fixes for the base image (Trivy fails the build on fixed HIGH/CRITICAL issues)
RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
RUN useradd --create-home shop && mkdir -p /app/uploads && chown shop /app/uploads
USER shop

ARG APP_VERSION=""
ENV APP_VERSION=${APP_VERSION} \
    UPLOAD_DIR=/app/uploads

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/health\", timeout=4)"
# hosting platforms (Render) set PORT; locally and in CI the default 8000 is used
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
