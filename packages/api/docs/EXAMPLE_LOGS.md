# Example Log Output

This document shows example log output from the V42 Prefill API with structured logging enabled.

## Request Lifecycle Logs

### 1. Request Started

```json
{
  "timestamp": "2025-11-07T10:30:45.000123Z",
  "level": "INFO",
  "logger": "app.middleware.logging_middleware",
  "message": "Request started",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-12345",
  "method": "POST",
  "path": "/api/v1/prefills/validate/session-abc-123/q1",
  "query_params": "",
  "client_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

### 2. Endpoint Processing

```json
{
  "timestamp": "2025-11-07T10:30:45.050234Z",
  "level": "INFO",
  "logger": "app.routers.v42_prefills",
  "message": "Validating prefill for question q1",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-12345",
  "session_id": "session-abc-123",
  "question_id": "q1",
  "action": "accept"
}
```

### 3. Event Tracking

```json
{
  "timestamp": "2025-11-07T10:30:45.120456Z",
  "level": "INFO",
  "logger": "events",
  "message": "Event: prefill_accepted",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-12345",
  "event_type": "prefill_accepted",
  "category": "business_metric",
  "session_id": "session-abc-123",
  "question_id": "q1",
  "action": "accept",
  "time_to_decision_ms": 1500,
  "company_name": "Acme Corporation"
}
```

### 4. Performance Metrics

```json
{
  "timestamp": "2025-11-07T10:30:45.180567Z",
  "level": "INFO",
  "logger": "metrics",
  "message": "Operation completed: validate_single_prefill",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-12345",
  "operation": "validate_single_prefill",
  "duration_ms": 156.42,
  "success": true
}
```

### 5. Request Completed

```json
{
  "timestamp": "2025-11-07T10:30:45.234678Z",
  "level": "INFO",
  "logger": "app.middleware.logging_middleware",
  "message": "Request completed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-12345",
  "status_code": 200,
  "method": "POST",
  "path": "/api/v1/prefills/validate/session-abc-123/q1",
  "duration_ms": 234.56
}
```

## Bulk Operation Logs

### Bulk Validation Started

```json
{
  "timestamp": "2025-11-07T11:15:30.000000Z",
  "level": "INFO",
  "logger": "app.routers.v42_prefills",
  "message": "Starting bulk validation",
  "trace_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "user_id": "user-12345",
  "session_id": "session-abc-123",
  "company_name": "Acme Corporation",
  "section": "Financial Information",
  "question_count": 15,
  "action": "accepted"
}
```

### Database Operation Timing

```json
{
  "timestamp": "2025-11-07T11:15:30.250000Z",
  "level": "INFO",
  "logger": "metrics",
  "message": "Operation completed: bulk_validate_database_operation",
  "trace_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "user_id": "user-12345",
  "operation": "bulk_validate_database_operation",
  "duration_ms": 245.67,
  "session_id": "session-abc-123",
  "question_count": 15,
  "success": true
}
```

### Bulk Event Tracking

```json
{
  "timestamp": "2025-11-07T11:15:30.300000Z",
  "level": "INFO",
  "logger": "events",
  "message": "Event: bulk_validation",
  "trace_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "user_id": "user-12345",
  "event_type": "bulk_validation",
  "category": "user_interaction",
  "session_id": "session-abc-123",
  "operation": "accepted",
  "question_count": 15,
  "section_name": "Financial Information",
  "success_count": 15,
  "failure_count": 0
}
```

## Error Handling Logs

### Request Failure

```json
{
  "timestamp": "2025-11-07T12:30:45.000000Z",
  "level": "ERROR",
  "logger": "app.middleware.logging_middleware",
  "message": "Request failed",
  "trace_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "user_id": "user-12345",
  "method": "POST",
  "path": "/api/v1/prefills/validate/session-xyz/q99",
  "duration_ms": 45.23,
  "error_type": "HTTPException",
  "error_message": "Prefill not found",
  "exception": "Traceback (most recent call last):\n  File \"app/routers/v42_prefills.py\", line 85, in validate_single_prefill\n    prefill = get_prefill(question_id)\nHTTPException: 404: Prefill not found"
}
```

### Application Error

```json
{
  "timestamp": "2025-11-07T12:35:22.000000Z",
  "level": "ERROR",
  "logger": "app.routers.v42_prefills",
  "message": "Failed to validate prefill",
  "trace_id": "9b7d8c3e-2f51-4a9c-8e7b-6d4f1a2c9e8b",
  "user_id": "user-12345",
  "session_id": "session-abc-123",
  "question_id": "q5",
  "error": "Database connection lost",
  "exception": "Traceback (most recent call last):\n  File \"app/routers/v42_prefills.py\", line 92, in validate_single_prefill\n    db.commit()\nOperationalError: connection lost"
}
```

## Performance Analysis Logs

### Slow Query Warning

```json
{
  "timestamp": "2025-11-07T13:20:15.000000Z",
  "level": "WARNING",
  "logger": "metrics",
  "message": "Slow operation detected: database_query",
  "trace_id": "1a2b3c4d-5e6f-7g8h-9i0j-k1l2m3n4o5p6",
  "user_id": "user-12345",
  "operation": "database_query",
  "duration_ms": 1534.67,
  "threshold_ms": 1000,
  "exceeded_by_ms": 534.67
}
```

### Database Query Profiling

```json
{
  "timestamp": "2025-11-07T13:25:30.000000Z",
  "level": "INFO",
  "logger": "metrics",
  "message": "Operation completed: database_query_prefills",
  "trace_id": "a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6",
  "user_id": "user-12345",
  "operation": "database_query_prefills",
  "duration_ms": 23.45,
  "session_id": "session-abc-123",
  "company_name": "Acme Corporation",
  "success": true
}
```

## Session Lifecycle Events

### Session Started

```json
{
  "timestamp": "2025-11-07T09:00:00.000000Z",
  "level": "INFO",
  "logger": "events",
  "message": "Event: session_started",
  "trace_id": "f1e2d3c4-b5a6-9807-8796-a5b4c3d2e1f0",
  "user_id": "user-12345",
  "event_type": "session_started",
  "category": "business_metric",
  "session_id": "session-abc-123",
  "company_name": "Acme Corporation"
}
```

### Session Completed

```json
{
  "timestamp": "2025-11-07T10:45:00.000000Z",
  "level": "INFO",
  "logger": "events",
  "message": "Event: session_completed",
  "trace_id": "a9b8c7d6-e5f4-3g2h-1i0j-k9l8m7n6o5p4",
  "user_id": "user-12345",
  "event_type": "session_completed",
  "category": "business_metric",
  "session_id": "session-abc-123",
  "duration_minutes": 105,
  "completion_rate": 0.95,
  "questions_answered": 95,
  "prefills_accepted": 82,
  "prefills_rejected": 8,
  "prefills_modified": 5
}
```

## Log Querying Examples

### Query by Trace ID (Follow Single Request)

```bash
cat app.log | jq 'select(.trace_id == "550e8400-e29b-41d4-a716-446655440000")'
```

### Query Acceptance Rate

```bash
# Count prefill acceptances
cat events.log | jq -r 'select(.event_type == "prefill_accepted")' | wc -l

# Group by company
cat events.log | jq -r 'select(.event_type == "prefill_accepted") | .company_name' | sort | uniq -c
```

### Query Performance Metrics

```bash
# Average request duration
cat app.log | jq -s '[.[] | select(.duration_ms) | .duration_ms] | add/length'

# Slow requests (>1000ms)
cat app.log | jq 'select(.duration_ms > 1000) | {path, duration_ms, trace_id}'
```

### Query Error Rate

```bash
# Total errors by type
cat app.log | jq -r 'select(.level == "ERROR") | .error_type' | sort | uniq -c

# Errors in last hour
cat app.log | jq 'select(.level == "ERROR" and (.timestamp | fromdateiso8601) > (now - 3600))'
```

## Grafana Loki Query Examples

```logql
# All logs for a specific trace
{job="v42-api"} | json | trace_id="550e8400-e29b-41d4-a716-446655440000"

# Error rate over time
sum(rate({job="v42-api"} | json | level="ERROR" [5m]))

# Average request duration
avg_over_time({job="v42-api"} | json | unwrap duration_ms [5m])

# Prefill acceptance rate
sum(rate({logger="events"} | json | event_type="prefill_accepted" [5m]))
/
sum(rate({logger="events"} | json | event_type=~"prefill_.*" [5m]))

# Top slow operations
topk(10,
  sum by (operation) (
    rate({job="v42-api", logger="metrics"}
      | json
      | unwrap duration_ms
      | duration_ms > 1000 [5m])
  )
)
```

## Response Headers

Every HTTP response includes the trace ID for correlation:

```
HTTP/1.1 200 OK
Content-Type: application/json
X-Trace-ID: 550e8400-e29b-41d4-a716-446655440000

{
  "success": true,
  "message": "Prefill accepted successfully",
  ...
}
```

This allows frontend applications to include the trace ID in error reports,
making it easy to find all related backend logs for debugging.
