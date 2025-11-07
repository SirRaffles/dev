"""Tests for event tracking system."""

import json
import logging
from unittest.mock import Mock, patch
import pytest

from app.utils.events import (
    EventType,
    EventCategory,
    track_event,
    track_prefill_shown,
    track_prefill_validation,
    track_bulk_operation,
    track_performance_metric
)


class TestEventTracking:
    """Tests for event tracking functions."""

    @patch('app.utils.events.logger')
    def test_track_event_basic(self, mock_logger):
        """Test basic event tracking."""
        track_event(
            EventType.PREFILL_ACCEPTED,
            data={'question_id': 'q1', 'session_id': 'session-123'},
            category=EventCategory.USER_INTERACTION
        )

        # Verify logger was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        # Check message
        assert 'Event: prefill_accepted' in call_args[0][0]

        # Check extra data
        extra_data = call_args[1]['extra']
        assert extra_data['event_type'] == 'prefill_accepted'
        assert extra_data['category'] == 'user_interaction'
        assert extra_data['question_id'] == 'q1'
        assert extra_data['session_id'] == 'session-123'
        assert 'timestamp' in extra_data

    @patch('app.utils.events.logger')
    def test_track_event_with_user_and_session(self, mock_logger):
        """Test event tracking with user and session IDs."""
        track_event(
            EventType.SESSION_STARTED,
            data={'source': 'web'},
            user_id='user-456',
            session_id='session-789'
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['user_id'] == 'user-456'
        assert extra_data['session_id'] == 'session-789'
        assert extra_data['source'] == 'web'

    @patch('app.utils.events.logger')
    def test_track_prefill_shown(self, mock_logger):
        """Test tracking when a prefill is shown to user."""
        track_prefill_shown(
            session_id='session-123',
            question_id='q1',
            prefill_value='Test Value',
            confidence_score=0.95,
            data_source='ai_generated'
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['event_type'] == 'prefill_shown'
        assert extra_data['session_id'] == 'session-123'
        assert extra_data['question_id'] == 'q1'
        assert extra_data['confidence_score'] == 0.95
        assert extra_data['data_source'] == 'ai_generated'
        assert extra_data['has_value'] is True
        assert extra_data['prefill_value_length'] == 10

    @patch('app.utils.events.logger')
    def test_track_prefill_validation_accept(self, mock_logger):
        """Test tracking prefill acceptance."""
        track_prefill_validation(
            session_id='session-123',
            question_id='q1',
            action='accept',
            time_to_decision_ms=1500,
            company_name='Acme Corp'
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['event_type'] == 'prefill_accepted'
        assert extra_data['action'] == 'accept'
        assert extra_data['time_to_decision_ms'] == 1500
        assert extra_data['company_name'] == 'Acme Corp'

    @patch('app.utils.events.logger')
    def test_track_prefill_validation_reject(self, mock_logger):
        """Test tracking prefill rejection."""
        track_prefill_validation(
            session_id='session-123',
            question_id='q1',
            action='reject',
            time_to_decision_ms=500
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['event_type'] == 'prefill_rejected'
        assert extra_data['action'] == 'reject'

    @patch('app.utils.events.logger')
    def test_track_prefill_validation_modify(self, mock_logger):
        """Test tracking prefill modification."""
        track_prefill_validation(
            session_id='session-123',
            question_id='q1',
            action='modify',
            original_value='Original',
            modified_value='Modified',
            time_to_decision_ms=2000
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['event_type'] == 'prefill_modified'
        assert extra_data['was_modified'] is True

    @patch('app.utils.events.logger')
    def test_track_bulk_operation(self, mock_logger):
        """Test tracking bulk operations."""
        question_ids = ['q1', 'q2', 'q3', 'q4', 'q5']

        track_bulk_operation(
            session_id='session-123',
            operation='accept',
            question_ids=question_ids,
            section_name='Financial Information',
            success_count=5,
            failure_count=0
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['event_type'] == 'bulk_validation'
        assert extra_data['operation'] == 'accept'
        assert extra_data['question_count'] == 5
        assert extra_data['section_name'] == 'Financial Information'
        assert extra_data['success_count'] == 5
        assert extra_data['failure_count'] == 0

    @patch('app.utils.events.logger')
    def test_track_bulk_operation_with_failures(self, mock_logger):
        """Test tracking bulk operations with some failures."""
        question_ids = ['q1', 'q2', 'q3']

        track_bulk_operation(
            session_id='session-123',
            operation='validate',
            question_ids=question_ids,
            success_count=2,
            failure_count=1
        )

        call_args = mock_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['success_count'] == 2
        assert extra_data['failure_count'] == 1

    @patch('app.utils.logging.get_logger')
    def test_track_performance_metric(self, mock_get_logger):
        """Test tracking performance metrics."""
        mock_perf_logger = Mock()
        mock_get_logger.return_value = mock_perf_logger

        track_performance_metric(
            operation='database_query',
            duration_ms=45.67,
            success=True,
            metadata={'table': 'prefills', 'rows': 100}
        )

        mock_get_logger.assert_called_with('performance')
        mock_perf_logger.info.assert_called_once()

        call_args = mock_perf_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['operation'] == 'database_query'
        assert extra_data['duration_ms'] == 45.67
        assert extra_data['success'] is True
        assert extra_data['table'] == 'prefills'
        assert extra_data['rows'] == 100

    @patch('app.utils.logging.get_logger')
    def test_track_performance_metric_with_error(self, mock_get_logger):
        """Test tracking performance metrics with error."""
        mock_perf_logger = Mock()
        mock_get_logger.return_value = mock_perf_logger

        track_performance_metric(
            operation='api_call',
            duration_ms=1200.5,
            success=False,
            error='Connection timeout'
        )

        call_args = mock_perf_logger.info.call_args
        extra_data = call_args[1]['extra']

        assert extra_data['success'] is False
        assert extra_data['error'] == 'Connection timeout'


class TestEventTypes:
    """Tests for EventType enum."""

    def test_event_types_have_correct_values(self):
        """Test that event types have the expected string values."""
        assert EventType.PREFILL_SHOWN.value == 'prefill_shown'
        assert EventType.PREFILL_ACCEPTED.value == 'prefill_accepted'
        assert EventType.PREFILL_REJECTED.value == 'prefill_rejected'
        assert EventType.BULK_VALIDATION.value == 'bulk_validation'
        assert EventType.UNDO_OPERATION.value == 'undo_operation'

    def test_event_categories_have_correct_values(self):
        """Test that event categories have the expected string values."""
        assert EventCategory.USER_INTERACTION.value == 'user_interaction'
        assert EventCategory.BUSINESS_METRIC.value == 'business_metric'
        assert EventCategory.SYSTEM_OPERATION.value == 'system_operation'
        assert EventCategory.ERROR.value == 'error'
