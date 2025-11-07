"""Logging middleware for request tracing and observability.

This middleware:
- Generates unique trace IDs for each request
- Extracts user context from authentication
- Logs request start and completion
- Adds trace ID to response headers
- Measures request duration
"""

import uuid
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.utils.logging import trace_id_var, user_id_var, get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    def __init__(self, app: ASGIApp):
        """Initialize the logging middleware.

        Args:
            app: The ASGI application
        """
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process each request with logging.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The HTTP response
        """
        # Generate unique trace ID for this request
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)

        # Extract user ID from request state (set by auth middleware)
        # If no auth middleware, default to 'anonymous'
        user_id = 'anonymous'
        if hasattr(request.state, 'user'):
            user_obj = request.state.user
            if isinstance(user_obj, dict):
                user_id = user_obj.get('id', user_obj.get('sub', 'anonymous'))
            elif hasattr(user_obj, 'id'):
                user_id = str(user_obj.id)

        user_id_var.set(user_id)

        # Record start time
        start_time = time.time()

        # Log request start
        logger.info(
            'Request started',
            extra={
                'method': request.method,
                'path': request.url.path,
                'query_params': str(request.query_params),
                'client_ip': request.client.host if request.client else 'unknown',
                'user_agent': request.headers.get('user-agent', 'unknown')
            }
        )

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log successful request completion
            logger.info(
                'Request completed',
                extra={
                    'status_code': response.status_code,
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': round(duration_ms, 2)
                }
            )

            # Add trace ID to response headers for client-side correlation
            response.headers['X-Trace-ID'] = trace_id

            return response

        except Exception as exc:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log request failure
            logger.error(
                'Request failed',
                extra={
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': round(duration_ms, 2),
                    'error_type': type(exc).__name__,
                    'error_message': str(exc)
                },
                exc_info=True
            )

            # Re-raise the exception to be handled by error handlers
            raise


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Simpler middleware that just adds request IDs without logging.

    Use this if you want trace IDs but handle logging separately.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Add trace ID to request context.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The HTTP response with X-Trace-ID header
        """
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)

        response = await call_next(request)
        response.headers['X-Trace-ID'] = trace_id

        return response
