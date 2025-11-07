"""Performance metrics and monitoring utilities.

This module provides utilities for measuring and tracking performance
metrics across the application, including timing operations, resource
usage, and custom metrics.
"""

import time
import functools
from contextlib import contextmanager
from typing import Callable, Any, Optional, Dict
from app.utils.logging import get_logger

logger = get_logger('metrics')


@contextmanager
def measure_time(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager to measure and log operation duration.

    Args:
        operation: Name of the operation being measured
        metadata: Additional metadata to include in the log

    Yields:
        Dictionary that can be updated with additional metrics during execution

    Example:
        >>> with measure_time('database_query', {'table': 'users'}):
        ...     result = db.query(...)
        ...
        # Logs: Operation completed - database_query (123.45ms)
    """
    start_time = time.time()
    metrics_data: Dict[str, Any] = metadata or {}

    try:
        # Yield the metrics dict so caller can add more data during execution
        yield metrics_data
    finally:
        duration_ms = (time.time() - start_time) * 1000

        log_data = {
            'operation': operation,
            'duration_ms': round(duration_ms, 2),
            'success': True,
            **metrics_data
        }

        logger.info(
            f'Operation completed: {operation}',
            extra=log_data
        )


@contextmanager
def measure_time_with_error(operation: str, metadata: Optional[Dict[str, Any]] = None):
    """Context manager to measure operation duration and capture errors.

    Similar to measure_time but logs errors if they occur during the operation.

    Args:
        operation: Name of the operation being measured
        metadata: Additional metadata to include in the log

    Yields:
        Dictionary that can be updated with additional metrics during execution

    Example:
        >>> with measure_time_with_error('api_call', {'endpoint': '/users'}):
        ...     response = requests.get(url)
        ...
    """
    start_time = time.time()
    metrics_data: Dict[str, Any] = metadata or {}
    success = True
    error_message = None

    try:
        yield metrics_data
    except Exception as exc:
        success = False
        error_message = str(exc)
        raise  # Re-raise the exception after logging
    finally:
        duration_ms = (time.time() - start_time) * 1000

        log_data = {
            'operation': operation,
            'duration_ms': round(duration_ms, 2),
            'success': success,
            **metrics_data
        }

        if error_message:
            log_data['error'] = error_message

        if success:
            logger.info(
                f'Operation completed: {operation}',
                extra=log_data
            )
        else:
            logger.error(
                f'Operation failed: {operation}',
                extra=log_data
            )


def timed(operation_name: Optional[str] = None):
    """Decorator to automatically measure function execution time.

    Args:
        operation_name: Custom name for the operation (defaults to function name)

    Example:
        >>> @timed('complex_calculation')
        ... def calculate_metrics(data):
        ...     # ... complex logic ...
        ...     return result
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f'{func.__module__}.{func.__name__}'

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            with measure_time(op_name):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            with measure_time(op_name):
                return await func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if functools.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class MetricsCollector:
    """Collector for custom metrics during operation execution.

    Useful for collecting multiple metrics during a single operation.
    """

    def __init__(self, operation: str):
        """Initialize the metrics collector.

        Args:
            operation: Name of the operation
        """
        self.operation = operation
        self.start_time = time.time()
        self.metrics: Dict[str, Any] = {}

    def add_metric(self, key: str, value: Any) -> None:
        """Add a custom metric.

        Args:
            key: Metric name
            value: Metric value
        """
        self.metrics[key] = value

    def increment(self, key: str, amount: int = 1) -> None:
        """Increment a counter metric.

        Args:
            key: Counter name
            amount: Amount to increment by
        """
        self.metrics[key] = self.metrics.get(key, 0) + amount

    def finalize(self, success: bool = True, error: Optional[str] = None) -> None:
        """Finalize and log all collected metrics.

        Args:
            success: Whether the operation succeeded
            error: Error message if failed
        """
        duration_ms = (time.time() - self.start_time) * 1000

        log_data = {
            'operation': self.operation,
            'duration_ms': round(duration_ms, 2),
            'success': success,
            **self.metrics
        }

        if error:
            log_data['error'] = error

        if success:
            logger.info(
                f'Operation completed: {self.operation}',
                extra=log_data
            )
        else:
            logger.error(
                f'Operation failed: {self.operation}',
                extra=log_data
            )


def log_slow_operation(operation: str, duration_ms: float, threshold_ms: float = 1000) -> None:
    """Log a warning if an operation exceeds a duration threshold.

    Args:
        operation: Name of the operation
        duration_ms: Actual duration in milliseconds
        threshold_ms: Warning threshold in milliseconds
    """
    if duration_ms > threshold_ms:
        logger.warning(
            f'Slow operation detected: {operation}',
            extra={
                'operation': operation,
                'duration_ms': round(duration_ms, 2),
                'threshold_ms': threshold_ms,
                'exceeded_by_ms': round(duration_ms - threshold_ms, 2)
            }
        )


@contextmanager
def track_resource_usage(operation: str):
    """Track CPU and memory usage for an operation (requires psutil).

    Args:
        operation: Name of the operation

    Yields:
        None

    Note:
        This requires the psutil library. If not available, only time is tracked.
    """
    start_time = time.time()

    try:
        import psutil
        process = psutil.Process()
        start_cpu = process.cpu_percent()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB

        yield

        end_cpu = process.cpu_percent()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            f'Resource usage: {operation}',
            extra={
                'operation': operation,
                'duration_ms': round(duration_ms, 2),
                'cpu_percent': round(end_cpu, 2),
                'memory_mb': round(end_memory, 2),
                'memory_delta_mb': round(end_memory - start_memory, 2)
            }
        )
    except ImportError:
        # psutil not available, just track time
        yield
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f'Operation duration: {operation}',
            extra={
                'operation': operation,
                'duration_ms': round(duration_ms, 2)
            }
        )
