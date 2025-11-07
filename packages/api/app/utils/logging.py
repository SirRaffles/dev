"""Structured logging utilities for the V42 Prefill API.

This module provides structured JSON logging with request tracing capabilities.
All logs include trace_id and user_id context for distributed tracing.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variables for request tracing
# These are thread-safe and async-safe context variables
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')


class StructuredFormatter(logging.Formatter):
    """Custom log formatter that outputs structured JSON logs.

    Each log entry includes:
    - timestamp: ISO 8601 formatted UTC timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - logger: Logger name
    - message: Log message
    - trace_id: Request correlation ID
    - user_id: Authenticated user ID or 'anonymous'
    - extra: Any additional fields passed via logging.info(..., extra={...})
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as structured JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log entry
        """
        log_data: Dict[str, Any] = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'trace_id': trace_id_var.get(),
            'user_id': user_id_var.get(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        # Add extra fields from the log record
        # Skip private attributes and standard LogRecord attributes
        skip_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs', 'message',
            'pathname', 'process', 'processName', 'relativeCreated', 'thread',
            'threadName', 'exc_info', 'exc_text', 'stack_info', 'getMessage',
            'extra'
        }

        for key, value in record.__dict__.items():
            if key not in skip_attrs and not key.startswith('_'):
                log_data[key] = value

        return json.dumps(log_data)


def setup_logging(level: str = 'INFO', format_type: str = 'json') -> None:
    """Configure the root logger with structured logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ('json' or 'text')
    """
    # Remove existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler()

    # Set formatter based on format type
    if format_type == 'json':
        handler.setFormatter(StructuredFormatter())
    else:
        # Text format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Reduce noise from uvicorn and other libraries
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.error').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_trace_context(trace_id: str, user_id: str = 'anonymous') -> None:
    """Set the trace context for the current request.

    Args:
        trace_id: Unique request identifier
        user_id: User identifier or 'anonymous'
    """
    trace_id_var.set(trace_id)
    user_id_var.set(user_id)


def get_trace_id() -> str:
    """Get the current trace ID.

    Returns:
        Current trace ID or empty string
    """
    return trace_id_var.get()


def get_user_id() -> str:
    """Get the current user ID.

    Returns:
        Current user ID or 'anonymous'
    """
    return user_id_var.get()
