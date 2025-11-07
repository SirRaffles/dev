"""Tests for performance metrics utilities."""

import time
from unittest.mock import Mock, patch
import pytest

from app.utils.metrics import (
    measure_time,
    measure_time_with_error,
    timed,
    MetricsCollector,
    log_slow_operation
)


class TestMeasureTime:
    """Tests for measure_time context manager."""

    @patch('app.utils.metrics.logger')
    def test_measure_time_basic(self, mock_logger):
        """Test basic time measurement."""
        with measure_time('test_operation'):
            time.sleep(0.01)  # Sleep for 10ms

        # Verify logger was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        assert 'test_operation' in call_args[0][0]
        extra_data = call_args[1]['extra']

        assert extra_data['operation'] == 'test_operation'
        assert extra_data['duration_ms'] >= 10  # At least 10ms
        assert extra_data['success'] is True

    @patch('app.utils.metrics.logger')
    def test_measure_time_with_metadata(self, mock_logger):
        """Test time measurement with additional metadata."""
        with measure_time('test_operation', {'user_id': 'user-123'}) as metrics:
            metrics['rows_processed'] = 100
            time.sleep(0.01)

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['user_id'] == 'user-123'
        assert extra_data['rows_processed'] == 100

    @patch('app.utils.metrics.logger')
    def test_measure_time_logs_even_on_exception(self, mock_logger):
        """Test that timing is logged even when exception occurs."""
        try:
            with measure_time('failing_operation'):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Logger should still be called
        mock_logger.info.assert_called_once()


class TestMeasureTimeWithError:
    """Tests for measure_time_with_error context manager."""

    @patch('app.utils.metrics.logger')
    def test_measure_time_with_error_success(self, mock_logger):
        """Test successful operation logging."""
        with measure_time_with_error('test_operation'):
            time.sleep(0.01)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['success'] is True
        assert 'error' not in extra_data

    @patch('app.utils.metrics.logger')
    def test_measure_time_with_error_failure(self, mock_logger):
        """Test failed operation logging."""
        with pytest.raises(ValueError):
            with measure_time_with_error('failing_operation'):
                raise ValueError("Test error")

        # Should log error
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['success'] is False
        assert extra_data['error'] == 'Test error'

    @patch('app.utils.metrics.logger')
    def test_measure_time_with_error_and_metadata(self, mock_logger):
        """Test error tracking with metadata."""
        metadata = {'endpoint': '/api/test'}

        with pytest.raises(RuntimeError):
            with measure_time_with_error('api_call', metadata):
                raise RuntimeError("Connection failed")

        call_args = mock_logger.error.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['endpoint'] == '/api/test'
        assert extra_data['error'] == 'Connection failed'


class TestTimedDecorator:
    """Tests for @timed decorator."""

    @patch('app.utils.metrics.logger')
    def test_timed_decorator_sync_function(self, mock_logger):
        """Test @timed decorator on synchronous function."""
        @timed('sync_operation')
        def sync_func(x, y):
            time.sleep(0.01)
            return x + y

        result = sync_func(2, 3)

        assert result == 5
        mock_logger.info.assert_called_once()

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']
        assert extra_data['operation'] == 'sync_operation'

    @patch('app.utils.metrics.logger')
    @pytest.mark.asyncio
    async def test_timed_decorator_async_function(self, mock_logger):
        """Test @timed decorator on async function."""
        @timed('async_operation')
        async def async_func(x, y):
            await asyncio.sleep(0.01)
            return x + y

        import asyncio
        result = await async_func(5, 7)

        assert result == 12
        mock_logger.info.assert_called_once()

    @patch('app.utils.metrics.logger')
    def test_timed_decorator_uses_function_name(self, mock_logger):
        """Test that @timed uses function name when no name provided."""
        @timed()
        def my_function():
            return True

        my_function()

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']
        assert 'my_function' in extra_data['operation']


class TestMetricsCollector:
    """Tests for MetricsCollector class."""

    @patch('app.utils.metrics.logger')
    def test_metrics_collector_basic(self, mock_logger):
        """Test basic metrics collection."""
        collector = MetricsCollector('test_operation')
        collector.add_metric('rows', 100)
        collector.add_metric('status', 'success')

        time.sleep(0.01)
        collector.finalize(success=True)

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['operation'] == 'test_operation'
        assert extra_data['rows'] == 100
        assert extra_data['status'] == 'success'
        assert extra_data['duration_ms'] >= 10

    @patch('app.utils.metrics.logger')
    def test_metrics_collector_increment(self, mock_logger):
        """Test incrementing counter metrics."""
        collector = MetricsCollector('counter_test')
        collector.increment('processed')
        collector.increment('processed')
        collector.increment('processed', 3)

        collector.finalize(success=True)

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['processed'] == 5

    @patch('app.utils.metrics.logger')
    def test_metrics_collector_with_error(self, mock_logger):
        """Test metrics collector with error."""
        collector = MetricsCollector('failing_operation')
        collector.add_metric('attempt', 1)

        collector.finalize(success=False, error='Operation failed')

        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['success'] is False
        assert extra_data['error'] == 'Operation failed'
        assert extra_data['attempt'] == 1

    @patch('app.utils.metrics.logger')
    def test_metrics_collector_multiple_metrics(self, mock_logger):
        """Test collecting multiple metrics."""
        collector = MetricsCollector('complex_operation')

        collector.add_metric('input_size', 1000)
        collector.add_metric('output_size', 500)
        collector.increment('records_processed', 100)
        collector.increment('errors')
        collector.add_metric('cache_hit_rate', 0.85)

        collector.finalize(success=True)

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['input_size'] == 1000
        assert extra_data['output_size'] == 500
        assert extra_data['records_processed'] == 100
        assert extra_data['errors'] == 1
        assert extra_data['cache_hit_rate'] == 0.85


class TestLogSlowOperation:
    """Tests for log_slow_operation function."""

    @patch('app.utils.metrics.logger')
    def test_log_slow_operation_below_threshold(self, mock_logger):
        """Test that operations below threshold are not logged."""
        log_slow_operation('fast_operation', 500, threshold_ms=1000)

        # Should not log anything
        mock_logger.warning.assert_not_called()

    @patch('app.utils.metrics.logger')
    def test_log_slow_operation_above_threshold(self, mock_logger):
        """Test that slow operations are logged."""
        log_slow_operation('slow_operation', 1500, threshold_ms=1000)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['operation'] == 'slow_operation'
        assert extra_data['duration_ms'] == 1500
        assert extra_data['threshold_ms'] == 1000
        assert extra_data['exceeded_by_ms'] == 500

    @patch('app.utils.metrics.logger')
    def test_log_slow_operation_custom_threshold(self, mock_logger):
        """Test slow operation with custom threshold."""
        log_slow_operation('operation', 300, threshold_ms=200)

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['threshold_ms'] == 200
        assert extra_data['exceeded_by_ms'] == 100
