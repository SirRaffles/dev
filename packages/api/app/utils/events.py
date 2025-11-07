"""Event tracking system for business analytics and observability.

This module provides structured event tracking for key user actions
and system events. Events are logged in a structured format suitable
for analytics, monitoring, and business intelligence.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum
from datetime import datetime
from app.utils.logging import get_logger

# Dedicated logger for events
logger = get_logger('events')


class EventType(Enum):
    """Enumeration of trackable events in the system.

    These events represent key user interactions and system operations
    that are important for analytics and monitoring.
    """

    # Prefill presentation events
    PREFILL_SHOWN = 'prefill_shown'
    PREFILL_HIDDEN = 'prefill_hidden'

    # Prefill validation events
    PREFILL_ACCEPTED = 'prefill_accepted'
    PREFILL_REJECTED = 'prefill_rejected'
    PREFILL_MODIFIED = 'prefill_modified'
    PREFILL_SKIPPED = 'prefill_skipped'

    # Bulk operations
    BULK_VALIDATION = 'bulk_validation'
    BULK_ACCEPT = 'bulk_accept'
    BULK_REJECT = 'bulk_reject'

    # User actions
    UNDO_OPERATION = 'undo_operation'
    REDO_OPERATION = 'redo_operation'
    MANUAL_EDIT = 'manual_edit'

    # Session events
    SESSION_STARTED = 'session_started'
    SESSION_COMPLETED = 'session_completed'
    SESSION_ABANDONED = 'session_abandoned'

    # Prefill generation
    PREFILL_CREATED = 'prefill_created'
    PREFILL_GENERATION_FAILED = 'prefill_generation_failed'

    # Data source events
    DATA_SOURCE_CONNECTED = 'data_source_connected'
    DATA_SOURCE_FAILED = 'data_source_failed'

    # Export events
    EXPORT_STARTED = 'export_started'
    EXPORT_COMPLETED = 'export_completed'
    EXPORT_FAILED = 'export_failed'


class EventCategory(Enum):
    """Categories for grouping related events."""

    USER_INTERACTION = 'user_interaction'
    SYSTEM_OPERATION = 'system_operation'
    BUSINESS_METRIC = 'business_metric'
    ERROR = 'error'
    PERFORMANCE = 'performance'


def track_event(
    event_type: EventType,
    data: Optional[Dict[str, Any]] = None,
    category: EventCategory = EventCategory.USER_INTERACTION,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> None:
    """Track a business or system event.

    Events are logged in structured JSON format for downstream processing
    by analytics systems, monitoring dashboards, or business intelligence tools.

    Args:
        event_type: The type of event being tracked
        data: Additional event-specific data
        category: Event category for grouping
        user_id: Optional user identifier (will use context if not provided)
        session_id: Optional session identifier

    Example:
        >>> track_event(
        ...     EventType.PREFILL_ACCEPTED,
        ...     data={
        ...         'question_id': 'q1',
        ...         'time_to_decision_ms': 1500,
        ...         'confidence_score': 0.95
        ...     },
        ...     session_id='session-123'
        ... )
    """
    event_data = {
        'event_type': event_type.value,
        'category': category.value,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
    }

    # Add user and session identifiers
    if user_id:
        event_data['user_id'] = user_id
    if session_id:
        event_data['session_id'] = session_id

    # Merge in custom event data
    if data:
        event_data.update(data)

    # Log the event
    logger.info(
        f'Event: {event_type.value}',
        extra=event_data
    )


def track_prefill_shown(
    session_id: str,
    question_id: str,
    prefill_value: Any,
    confidence_score: Optional[float] = None,
    data_source: Optional[str] = None
) -> None:
    """Track when a prefill suggestion is shown to the user.

    Args:
        session_id: Session identifier
        question_id: Question/field identifier
        prefill_value: The suggested prefill value
        confidence_score: AI confidence in the suggestion (0-1)
        data_source: Source of the prefill data
    """
    track_event(
        EventType.PREFILL_SHOWN,
        data={
            'session_id': session_id,
            'question_id': question_id,
            'prefill_value_length': len(str(prefill_value)),
            'has_value': bool(prefill_value),
            'confidence_score': confidence_score,
            'data_source': data_source
        },
        category=EventCategory.USER_INTERACTION
    )


def track_prefill_validation(
    session_id: str,
    question_id: str,
    action: str,
    time_to_decision_ms: Optional[int] = None,
    original_value: Optional[Any] = None,
    modified_value: Optional[Any] = None,
    company_name: Optional[str] = None
) -> None:
    """Track user validation of a prefill suggestion.

    Args:
        session_id: Session identifier
        question_id: Question/field identifier
        action: User action ('accept', 'reject', 'modify')
        time_to_decision_ms: Time taken to make decision
        original_value: Original prefilled value
        modified_value: Value after user modification
        company_name: Company being assessed
    """
    event_type = {
        'accept': EventType.PREFILL_ACCEPTED,
        'reject': EventType.PREFILL_REJECTED,
        'modify': EventType.PREFILL_MODIFIED
    }.get(action, EventType.MANUAL_EDIT)

    track_event(
        event_type,
        data={
            'session_id': session_id,
            'question_id': question_id,
            'action': action,
            'time_to_decision_ms': time_to_decision_ms,
            'was_modified': original_value != modified_value if modified_value else False,
            'company_name': company_name
        },
        category=EventCategory.BUSINESS_METRIC
    )


def track_bulk_operation(
    session_id: str,
    operation: str,
    question_ids: list,
    section_name: Optional[str] = None,
    success_count: Optional[int] = None,
    failure_count: Optional[int] = None
) -> None:
    """Track bulk validation operations.

    Args:
        session_id: Session identifier
        operation: Operation type ('accept', 'reject', 'validate')
        question_ids: List of affected question IDs
        section_name: Name of the section
        success_count: Number of successful operations
        failure_count: Number of failed operations
    """
    track_event(
        EventType.BULK_VALIDATION,
        data={
            'session_id': session_id,
            'operation': operation,
            'question_count': len(question_ids),
            'section_name': section_name,
            'success_count': success_count or len(question_ids),
            'failure_count': failure_count or 0
        },
        category=EventCategory.USER_INTERACTION
    )


def track_performance_metric(
    operation: str,
    duration_ms: float,
    success: bool = True,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Track performance metrics for operations.

    Args:
        operation: Name of the operation
        duration_ms: Duration in milliseconds
        success: Whether the operation succeeded
        error: Error message if failed
        metadata: Additional metadata
    """
    data = {
        'operation': operation,
        'duration_ms': round(duration_ms, 2),
        'success': success,
    }

    if error:
        data['error'] = error

    if metadata:
        data.update(metadata)

    # Use dedicated performance logger
    perf_logger = get_logger('performance')
    perf_logger.info(
        f'Performance: {operation}',
        extra=data
    )
