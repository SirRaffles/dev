"""Main FastAPI application for V42 Prefill API.

This module sets up the FastAPI application with all middleware,
routers, and configuration for structured logging and observability.
"""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.middleware.logging_middleware import LoggingMiddleware
from app.routers import v42_prefills
from app.utils.logging import setup_logging, get_logger

# Initialize logging before anything else
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')
setup_logging(level=LOG_LEVEL, format_type=LOG_FORMAT)

logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="V42 Prefill API",
    description="API for V42 form prefill suggestions with structured logging and observability",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware (should be added last to wrap all other middleware)
app.add_middleware(LoggingMiddleware)


# Exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that logs all unhandled exceptions.

    Args:
        request: The incoming request
        exc: The exception that was raised

    Returns:
        JSON error response
    """
    logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        extra={
            'error_type': type(exc).__name__,
            'error_message': str(exc),
            'path': request.url.path,
            'method': request.method
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "v42-prefill-api",
        "version": "2.0.0"
    }


# Include routers
app.include_router(
    v42_prefills.router,
    prefix="/api/v1/prefills",
    tags=["prefills"]
)


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("V42 Prefill API starting up", extra={
        "log_level": LOG_LEVEL,
        "log_format": LOG_FORMAT
    })


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("V42 Prefill API shutting down")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None  # Disable uvicorn's default logging
    )
