"""
FastAPI application entrypoint for RagaRhythm AI.
Includes Request ID middleware, structured observability logging, CORS protection,
and production exception handling.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import settings
from backend.app.core.exceptions import (
    APIError,
    api_error_handler,
    generic_exception_handler,
)
from backend.app.jobs import job_manager
from backend.app.observability import (
    log_event,
    metrics_registry,
    reset_current_request_id,
    sanitize_request_id,
    set_current_request_id,
)

# Configure Root Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("ragarhythm")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and graceful shutdown lifecycle."""
    yield
    # Graceful shutdown of in-process background worker thread pool
    job_manager.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Request ID & Observability Middleware
@app.middleware("http")
async def observability_and_request_id_middleware(request: Request, call_next):
    raw_req_id = request.headers.get("X-Request-ID")
    request_id = sanitize_request_id(raw_req_id)
    token = set_current_request_id(request_id)
    request.state.request_id = request_id
    start_time = time.perf_counter()

    try:
        log_event(
            "request.started",
            request_id=request_id,
            method=request.method,
            route=request.url.path,
        )
    except Exception:
        pass

    try:
        response = await call_next(request)
        duration_ms = max(0.0, (time.perf_counter() - start_time) * 1000.0)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

        is_error = response.status_code >= 400
        try:
            metrics_registry.record_request(duration_ms, is_error=is_error)
        except Exception:
            pass

        try:
            event_name = "request.failed" if is_error else "request.completed"
            log_level = logging.WARNING if is_error else logging.INFO
            log_event(
                event_name,
                level=log_level,
                request_id=request_id,
                method=request.method,
                route=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
        except Exception:
            pass
        return response
    except Exception as exc:
        duration_ms = max(0.0, (time.perf_counter() - start_time) * 1000.0)
        try:
            metrics_registry.record_request(duration_ms, is_error=True)
        except Exception:
            pass
        try:
            log_event(
                "request.failed",
                level=logging.ERROR,
                request_id=request_id,
                method=request.method,
                route=request.url.path,
                status_code=500,
                duration_ms=round(duration_ms, 2),
                error_code=type(exc).__name__,
            )
        except Exception:
            pass
        raise exc
    finally:
        reset_current_request_id(token)


# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time-Ms", "Content-Disposition"],
)

# Register Custom Exception Handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include v1 REST Router
app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirects root URL to interactive OpenAPI Swagger documentation."""
    return RedirectResponse(url="/docs")
