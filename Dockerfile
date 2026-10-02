# ==============================================================================
# Production Dockerfile for RagaRhythm AI Backend
# Multi-stage, stateless, non-root, Cloud Run compatible container image
# ==============================================================================

FROM python:3.11-slim AS builder

WORKDIR /app

# Install system build dependencies if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --prefix=/install -r backend/requirements.txt

# ==============================================================================
# Production Runtime Stage
# ==============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root application user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/sh -m appuser

# Copy application source code
COPY backend ./backend

# Set ownership
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Configure environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0

EXPOSE 8080

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/v1/health || exit 1

# Production entrypoint (exec format with dynamic PORT expansion)
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2 --no-access-log"]
