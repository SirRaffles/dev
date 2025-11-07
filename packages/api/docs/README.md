# V42 Prefills API Documentation

This directory contains technical documentation for the V42 Prefills API.

## Performance Documentation

### [Phase 2: N+1 Query Elimination](PERFORMANCE_PHASE2_N1_ELIMINATION.md)

Comprehensive report on eliminating N+1 query patterns across all prefills endpoints.

**Key Achievements**:
- 98% query reduction for list endpoints
- 50-95% response time improvement
- Zero N+1 patterns detected
- Comprehensive test coverage

**Date**: 2025-11-07
**Status**: Complete

## Quick Links

- [Migration Guide](../migrations/README.md)
- [Performance Tests](../tests/performance/)
- [API Router](../app/routers/v42_prefills.py)
- [Database Models](../app/models/v42_prefill.py)

## Testing

Run performance benchmarks:

```bash
# All performance tests
pytest packages/api/tests/performance/ -v -s

# Specific N+1 elimination tests
pytest packages/api/tests/performance/test_n1_query_fix.py -v -s

# Router integration tests
pytest packages/api/tests/routers/test_v42_prefills.py -v -s
```

## Development Guidelines

### Avoiding N+1 Queries

Always use eager loading for relationships:

```python
# ✅ GOOD: Use selectinload() for one-to-many
prefills = db.query(V42AIPrefill).options(
    selectinload(V42AIPrefill.sources)
).all()

# ❌ BAD: Lazy loading in loop
prefills = db.query(V42AIPrefill).all()
for p in prefills:
    sources = p.sources  # Triggers new query!
```

### Use Aggregation for Analytics

```python
# ✅ GOOD: Database aggregation
stats = db.query(
    func.count(Model.id),
    func.avg(Model.score)
).group_by(Model.category).all()

# ❌ BAD: Python loop
for category in categories:
    count = len([m for m in models if m.category == category])
```

### Test Query Counts

```python
from tests.utils import assert_query_count

def test_endpoint(db_session):
    with assert_query_count(db_session, max_queries=2):
        # Your operation here
        results = fetch_data()
```

## Architecture

```
packages/api/
├── app/
│   ├── models/           # SQLAlchemy models
│   │   └── v42_prefill.py
│   ├── routers/          # FastAPI routers
│   │   └── v42_prefills.py
│   └── utils/            # Utilities
│       ├── logging.py
│       ├── events.py
│       └── metrics.py
├── tests/
│   ├── utils/            # Test utilities
│   │   └── query_profiler.py
│   ├── performance/      # Performance benchmarks
│   │   └── test_n1_query_fix.py
│   └── routers/          # Router tests
│       └── test_v42_prefills.py
├── migrations/           # Database migrations
│   └── 001_add_prefill_indexes.sql
└── docs/                 # Documentation
    └── PERFORMANCE_PHASE2_N1_ELIMINATION.md
```

## Contributing

When adding new endpoints or modifying queries:

1. Use eager loading for all relationships
2. Use SQL aggregation for analytics
3. Add appropriate database indexes
4. Write tests with query count assertions
5. Document performance characteristics
6. Run benchmarks before/after changes

## Support

For questions or issues:
- Review [Performance Documentation](PERFORMANCE_PHASE2_N1_ELIMINATION.md)
- Check [Test Examples](../tests/performance/test_n1_query_fix.py)
- Run profiling with `profile_queries()` utility
