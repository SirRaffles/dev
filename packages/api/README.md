# V42 Prefill API

FastAPI-based REST API for V42 form prefill suggestions with comprehensive structured logging and observability.

## Features

- **Structured JSON Logging**: Machine-parseable logs with full context
- **Request Tracing**: UUID-based trace IDs for distributed tracing
- **Event Tracking**: Business metrics and user interaction tracking
- **Performance Metrics**: Operation timing and resource monitoring
- **N+1 Query Optimization**: Efficient database queries with SQLAlchemy eager loading

## Quick Start

### Installation

```bash
cd packages/api
pip install -r requirements.txt
```

### Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Database
DATABASE_URL=postgresql://user:password@localhost/v42_prefills
```

### Run the API

```bash
# Development mode
python -m app.main

# Or with uvicorn directly
uvicorn app.main:app --reload --port 8000
```

### Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/utils/test_logging.py -v
```

## Project Structure

```
packages/api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── logging_middleware.py  # Request tracing middleware
│   ├── models/
│   │   ├── __init__.py
│   │   └── v42_prefill.py      # SQLAlchemy ORM models
│   ├── routers/
│   │   ├── __init__.py
│   │   └── v42_prefills.py     # Prefill API endpoints
│   └── utils/
│       ├── __init__.py
│       ├── logging.py          # Structured logging utilities
│       ├── events.py           # Event tracking system
│       └── metrics.py          # Performance metrics
├── tests/
│   ├── __init__.py
│   ├── middleware/
│   │   └── test_logging_middleware.py
│   └── utils/
│       ├── test_logging.py
│       ├── test_events.py
│       └── test_metrics.py
├── docs/
│   └── LOGGING.md             # Comprehensive logging documentation
├── .env.example               # Environment variables template
├── logging.conf               # Logging configuration
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## API Endpoints

### Health Check
```
GET /health
```

### Prefill Management
```
GET  /api/v1/prefills/session/{session_id}
POST /api/v1/prefills/validate/{session_id}/{question_id}
POST /api/v1/prefills/bulk-validate/{session_id}
POST /api/v1/prefills/undo/{session_id}
POST /api/v1/prefills/session/{session_id}/complete
```

## Observability

### Structured Logs

All logs are output in JSON format:

```json
{
  "timestamp": "2025-11-07T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.routers.v42_prefills",
  "message": "Prefill validated successfully",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user-123",
  "session_id": "session-456",
  "question_id": "q1"
}
```

### Event Tracking

Track business events:

```python
from app.utils.events import track_prefill_validation

track_prefill_validation(
    session_id='session-123',
    question_id='q1',
    action='accept',
    time_to_decision_ms=1500
)
```

### Performance Metrics

Measure operation performance:

```python
from app.utils.metrics import measure_time

with measure_time('database_query'):
    results = db.query(Model).all()
```

## Documentation

- **[Logging & Observability](docs/LOGGING.md)**: Complete guide to logging, tracing, and monitoring
- **[API Reference](http://localhost:8000/docs)**: Interactive Swagger UI (when running)
- **[ReDoc](http://localhost:8000/redoc)**: Alternative API documentation

## Development

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all public functions
- Keep functions focused and testable

### Testing

- Write tests for new features
- Maintain >80% code coverage
- Use mocks for external dependencies
- Test both success and error cases

### Logging Best Practices

- Use structured logging with extra fields
- Include trace_id for request correlation
- Log at appropriate levels
- Never log sensitive data

## Deployment

### Production Configuration

1. Set `LOG_FORMAT=json` for production
2. Configure log aggregation (Loki, CloudWatch, etc.)
3. Set up monitoring and alerting
4. Use environment variables for secrets
5. Enable database connection pooling

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Contributing

1. Create a feature branch
2. Make your changes
3. Write tests
4. Update documentation
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- Check [LOGGING.md](docs/LOGGING.md) for observability questions
- Review test files for usage examples
- Open an issue on GitHub
