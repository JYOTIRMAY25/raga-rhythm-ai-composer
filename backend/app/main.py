"""
FastAPI application entrypoint for RagaRhythm AI.
Includes Request ID middleware, structured observability logging, CORS protection,
and production exception handling.
"""

from __future__ import annotations

import logging
import time
import uuid
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

# Configure Structured Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("ragarhythm")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Request ID & Observability Middleware
@app.middleware("http")
async def observability_and_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.perf_counter()

    # Attach request_id to request state
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(
            f"request_id={request_id} method={request.method} path={request.url.path} "
            f"status=500 duration_ms={duration_ms:.2f} error={type(exc).__name__}"
        )
        raise exc

    duration_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

    # Log clean, safe structured line (no secrets, no bodies)
    logger.info(
        f"request_id={request_id} method={request.method} path={request.url.path} "
        f"status={response.status_code} duration_ms={duration_ms:.2f}"
    )

    return response


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
