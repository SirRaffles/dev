# Logging & Observability

## Overview

The V42 Prefill API implements comprehensive structured logging and observability features to enable:
- Real-time monitoring and debugging
- Performance analysis and optimization
- Business analytics and user behavior tracking
- Distributed tracing across services
- Error tracking and alerting

## Architecture

### Components

1. **Structured Logging** (`app/utils/logging.py`)
   - JSON-formatted logs for machine parsing
   - Context-aware logging with trace IDs
   - Multiple log levels and formatters

2. **Logging Middleware** (`app/middleware/logging_middleware.py`)
   - Request/response logging
   - Automatic trace ID generation
   - Request duration tracking

3. **Event Tracking** (`app/utils/events.py`)
   - Business event logging
   - User interaction tracking
   - System operation monitoring

4. **Performance Metrics** (`app/utils/metrics.py`)
   - Operation timing
   - Resource usage tracking
   - Slow query detection

## Structured Logging

### Log Format

All logs are output in JSON format with the following structure:

```json
{
  "timestamp": "2025-11-07T10:30:45.123456Z",
  "level": "INFO",
  "logger": "app.routers.v42_prefills",
  "message": "Prefill validated successfully",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "session_id": "session-456",
  "question_id": "q1",
  "action": "accept"
}
```

### Key Fields

- **timestamp**: ISO 8601 UTC timestamp with millisecond precision
- **level**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **logger**: Python logger name (module path)
- **message**: Human-readable log message
- **trace_id**: Unique request identifier for distributed tracing
- **user_id**: Authenticated user ID or 'anonymous'
- **Extra fields**: Any additional context-specific data

### Usage

```python
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Basic logging
logger.info("Operation completed")

# Logging with extra fields
logger.info(
    "Prefill validated",
    extra={
        'session_id': 'session-123',
        'question_id': 'q1',
        'action': 'accept',
        'time_to_decision_ms': 1500
    }
)

# Error logging with exception
try:
    risky_operation()
except Exception as exc:
    logger.error(
        "Operation failed",
        extra={'operation': 'risky_operation'},
        exc_info=True
    )
```

## Request Tracing

### Trace IDs

Every HTTP request is assigned a unique trace ID (UUID) that:
- Propagates through the entire request lifecycle
- Is included in all log entries for that request
- Is returned in the `X-Trace-ID` response header
- Enables correlation of logs across services

### Context Variables

Trace context is managed using Python's `contextvars` for thread-safe and async-safe propagation:

```python
from app.utils.logging import set_trace_context, get_trace_id

# Set trace context (done automatically by middleware)
set_trace_context('trace-abc-123', 'user-456')

# Get current trace ID anywhere in the request
trace_id = get_trace_id()
```

### Middleware Integration

The `LoggingMiddleware` automatically:
1. Generates a unique trace ID for each request
2. Sets trace context using context variables
3. Logs request start with method, path, and client info
4. Logs request completion with status code and duration
5. Logs request failures with error details
6. Adds `X-Trace-ID` header to responses

Example log sequence:

```json
// Request started
{
  "timestamp": "2025-11-07T10:30:45.000Z",
  "level": "INFO",
  "message": "Request started",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "method": "POST",
  "path": "/api/v1/prefills/validate/session-123/q1",
  "client_ip": "192.168.1.100"
}

// Request completed
{
  "timestamp": "2025-11-07T10:30:45.234Z",
  "level": "INFO",
  "message": "Request completed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "status_code": 200,
  "duration_ms": 234.56
}
```

## Event Tracking

### Event Types

The system tracks these key events:

#### Prefill Events
- `prefill_shown`: AI suggestion displayed to user
- `prefill_accepted`: User accepts prefill
- `prefill_rejected`: User rejects prefill
- `prefill_modified`: User modifies prefill
- `prefill_created`: New prefill generated

#### User Actions
- `bulk_validation`: Bulk accept/reject operations
- `undo_operation`: Undo action performed
- `manual_edit`: User manually edits field

#### Session Events
- `session_started`: Assessment session begins
- `session_completed`: Assessment session finishes
- `session_abandoned`: Session left incomplete

### Usage

```python
from app.utils.events import (
    track_event,
    track_prefill_validation,
    track_bulk_operation,
    EventType,
    EventCategory
)

# Track prefill acceptance
track_prefill_validation(
    session_id='session-123',
    question_id='q1',
    action='accept',
    time_to_decision_ms=1500,
    company_name='Acme Corp'
)

# Track bulk operation
track_bulk_operation(
    session_id='session-123',
    operation='accept',
    question_ids=['q1', 'q2', 'q3'],
    section_name='Financial Information',
    success_count=3,
    failure_count=0
)

# Track custom event
track_event(
    EventType.SESSION_COMPLETED,
    data={
        'session_id': 'session-123',
        'duration_minutes': 45,
        'completion_rate': 0.95
    },
    category=EventCategory.BUSINESS_METRIC
)
```

### Event Log Format

```json
{
  "timestamp": "2025-11-07T10:30:45.123Z",
  "level": "INFO",
  "logger": "events",
  "message": "Event: prefill_accepted",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "prefill_accepted",
  "category": "business_metric",
  "session_id": "session-123",
  "question_id": "q1",
  "action": "accept",
  "time_to_decision_ms": 1500,
  "company_name": "Acme Corp"
}
```

## Performance Metrics

### Timing Operations

```python
from app.utils.metrics import measure_time, timed

# Context manager
with measure_time('database_query'):
    results = db.query(Model).all()

# With metadata
with measure_time('api_call', {'endpoint': '/external-api'}) as metrics:
    response = requests.get(url)
    metrics['status_code'] = response.status_code

# Decorator
@timed('complex_calculation')
async def calculate_metrics(data):
    # ... computation ...
    return result
```

### Collecting Multiple Metrics

```python
from app.utils.metrics import MetricsCollector

collector = MetricsCollector('bulk_processing')

for item in items:
    try:
        process(item)
        collector.increment('processed')
    except Exception:
        collector.increment('errors')

collector.add_metric('total_items', len(items))
collector.finalize(success=True)
```

### Slow Operation Detection

```python
from app.utils.metrics import log_slow_operation

duration_ms = measure_operation()
log_slow_operation('database_query', duration_ms, threshold_ms=1000)
```

## Configuration

### Environment Variables

```bash
# Logging configuration
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT=json             # json or text
LOG_FILE=/var/log/v42-api/app.log
EVENT_LOG_FILE=/var/log/v42-api/events.log

# Performance thresholds
SLOW_QUERY_THRESHOLD_MS=1000

# Feature flags
ENABLE_DETAILED_LOGGING=true
ENABLE_PERFORMANCE_TRACKING=true
ENABLE_EVENT_TRACKING=true
```

### Logging Configuration File

See `logging.conf` for advanced configuration including:
- Multiple log handlers (console, file, event file)
- Logger hierarchies
- Formatter customization
- Log file rotation (when using RotatingFileHandler)

## Log Aggregation & Analysis

### Supported Platforms

The structured JSON logs can be shipped to:

#### Grafana Loki
```bash
# Promtail configuration
- job_name: v42-api
  static_configs:
  - targets:
    - localhost
    labels:
      job: v42-api
      __path__: /var/log/v42-api/*.log
```

#### AWS CloudWatch
```python
# Using watchtower
import watchtower
import logging

handler = watchtower.CloudWatchLogHandler(
    log_group='v42-api',
    stream_name='production'
)
logging.getLogger().addHandler(handler)
```

#### Elasticsearch/Kibana
```bash
# Filebeat configuration
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/v42-api/*.log
  json.keys_under_root: true
  json.add_error_key: true
```

### Querying Logs

#### By Trace ID (following a single request)
```bash
# Using jq
cat app.log | jq 'select(.trace_id == "550e8400-e29b-41d4-a716-446655440000")'

# Using Loki
{job="v42-api"} | json | trace_id="550e8400-e29b-41d4-a716-446655440000"
```

#### By Event Type
```bash
# Get all prefill acceptances
cat events.log | jq 'select(.event_type == "prefill_accepted")'

# Count acceptances by company
cat events.log | jq -r 'select(.event_type == "prefill_accepted") | .company_name' | sort | uniq -c
```

#### By Performance
```bash
# Find slow requests (>1000ms)
cat app.log | jq 'select(.duration_ms > 1000)'

# Average request duration
cat app.log | jq -s '[.[] | select(.duration_ms) | .duration_ms] | add/length'
```

#### By Error Type
```bash
# All errors
cat app.log | jq 'select(.level == "ERROR")'

# Specific error types
cat app.log | jq 'select(.error_type == "ValidationError")'
```

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Request Metrics**
   - Request rate (requests/second)
   - Error rate (errors/total requests)
   - Average response time
   - P95/P99 response times

2. **Business Metrics**
   - Prefill acceptance rate
   - Session completion rate
   - Time to decision (avg)
   - Daily active sessions

3. **Performance Metrics**
   - Slow queries (>1s)
   - Database query count per request
   - Cache hit rate
   - Memory usage

### Alert Examples

```yaml
# Prometheus alerting rules
groups:
- name: v42_api_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(v42_api_errors_total[5m]) > 0.05
    annotations:
      summary: "High error rate detected"

  - alert: SlowRequests
    expr: histogram_quantile(0.95, v42_api_request_duration_seconds) > 2
    annotations:
      summary: "95th percentile latency > 2s"
```

## Best Practices

### DO

- Include relevant context in extra fields
- Use structured logging over string formatting
- Log at appropriate levels (INFO for normal operations, ERROR for failures)
- Include timing information for operations
- Use trace IDs to correlate related logs
- Track business events for analytics

### DON'T

- Log sensitive data (passwords, API keys, PII)
- Log excessively in tight loops
- Use print() statements (use logger instead)
- Log at DEBUG level in production
- Include stack traces in INFO logs

### Example: Good Logging

```python
logger.info(
    "Bulk validation completed",
    extra={
        'session_id': session_id,
        'section': section_name,
        'success_count': success_count,
        'failure_count': failure_count,
        'duration_ms': duration_ms
    }
)
```

### Example: Bad Logging

```python
# DON'T: String formatting, no structure
logger.info(f"Validated {success_count} items in {duration_ms}ms")

# DON'T: Sensitive data
logger.info(f"User password: {password}")  # NEVER

# DON'T: Excessive logging
for item in items:
    logger.debug(f"Processing {item}")  # Too noisy
```

## Troubleshooting

### No logs appearing

1. Check LOG_LEVEL environment variable
2. Verify log directory exists and is writable
3. Check that setup_logging() is called in main.py
4. Verify logger name is correct

### Trace IDs not appearing

1. Ensure LoggingMiddleware is registered
2. Check that middleware is added last (wraps other middleware)
3. Verify context variables are being set

### Events not tracking

1. Check ENABLE_EVENT_TRACKING environment variable
2. Verify events logger is configured
3. Check that track_event() is being called

## Future Enhancements

- Integration with Sentry for error tracking
- Integration with Datadog/New Relic for APM
- Custom Grafana dashboards
- Real-time alerting via PagerDuty/Slack
- Log retention and archival policies
- Machine learning for anomaly detection

## Related Documentation

- [API Reference](API.md)
- [Performance Optimization](PERFORMANCE.md)
- [Deployment Guide](DEPLOYMENT.md)
