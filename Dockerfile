# ==============================================================================
# Production Dockerfile for RagaRhythm AI Backend
# Multi-stage, stateless, non-root, Cloud Run compatible container image
# ==============================================================================

# Build Stage: Compile and install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build tools if needed for C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements into clean prefix
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --prefix=/install -r backend/requirements.txt

# ==============================================================================
# Production Runtime Stage
# ==============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime curl for healthchecks and libsndfile for audio decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root application user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/sh -m appuser

# Copy application source code (excluding tests and datasets via .dockerignore)
COPY backend ./backend

# Set proper non-root ownership
RUN chown -R appuser:appgroup /app

# Switch to unprivileged runtime user
USER appuser

# Configure environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production \
    PORT=8080 \
    HOST=0.0.0.0

EXPOSE 8080

# Container liveness health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1

# Production entrypoint with exec for direct SIGTERM signal handling
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --no-access-log"]
