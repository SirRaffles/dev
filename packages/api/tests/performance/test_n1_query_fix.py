"""
Performance benchmark tests for N+1 query elimination.

This module contains tests that verify the N+1 query optimizations are working
correctly. It compares naive (N+1) approaches with optimized approaches using
eager loading strategies.

Run with: pytest tests/performance/test_n1_query_fix.py -v
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, selectinload
from typing import List

from app.models import Base, V42AIPrefill, PrefillSource, ValidationHistory
from tests.utils import (
    profile_queries,
    assert_query_count,
    compare_query_performance,
    print_comparison
)


# Test database setup (using SQLite in-memory for tests)
@pytest.fixture(scope='function')
def db_engine():
    """Create a test database engine."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope='function')
def db_session(db_engine):
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_data(db_session: Session):
    """
    Create sample test data with 100 prefills, each having 3 sources.

    This represents a typical dataset that would expose N+1 query patterns
    if not properly optimized.
    """
    session_id = "test-session-123"
    company_name = "Acme Corp"

    prefills = []
    for i in range(100):
        prefill = V42AIPrefill(
            session_id=session_id,
            company_name=company_name,
            question_id=f"Q{i:03d}",
            section=f"Section{i % 5}",  # 5 sections
            prefilled_value=f"Answer to question {i}",
            confidence_score=0.85 + (i % 15) * 0.01,
            is_validated=(i % 3 == 0),  # Every 3rd is validated
            created_at=datetime.utcnow() - timedelta(hours=i),
            updated_at=datetime.utcnow() - timedelta(hours=i)
        )
        db_session.add(prefill)
        prefills.append(prefill)

    db_session.flush()  # Flush to get IDs

    # Add 3 sources per prefill (300 total sources)
    for prefill in prefills:
        for j in range(3):
            source = PrefillSource(
                prefill_id=prefill.id,
                source_type='document' if j == 0 else 'api',
                source_name=f"Source {j} for {prefill.question_id}",
                source_url=f"https://example.com/source/{prefill.id}/{j}",
                relevance_score=0.9 - (j * 0.1),
                excerpt=f"Excerpt from source {j}...",
                created_at=datetime.utcnow()
            )
            db_session.add(source)

    # Add validation history for validated prefills
    for prefill in prefills:
        if prefill.is_validated:
            history = ValidationHistory(
                prefill_id=prefill.id,
                user_id="test-user",
                action='accepted',
                previous_value=prefill.prefilled_value,
                new_value=prefill.prefilled_value,
                validated_at=datetime.utcnow()
            )
            db_session.add(history)

    db_session.commit()

    return {
        'session_id': session_id,
        'company_name': company_name,
        'prefill_count': len(prefills),
        'source_count': len(prefills) * 3
    }


class TestN1QueryElimination:
    """Test suite for N+1 query elimination."""

    def test_naive_approach_has_n1_pattern(self, db_session: Session, sample_data):
        """
        Baseline test: Demonstrate the N+1 query pattern with naive approach.

        This test fetches prefills WITHOUT eager loading and then accesses
        sources for each prefill in a loop. This should result in:
        - 1 query to fetch all prefills
        - N queries to fetch sources (one per prefill)
        Total: 1 + N queries (101 queries for 100 prefills)
        """
        with profile_queries(db_session) as stats:
            # Fetch prefills WITHOUT eager loading
            prefills = db_session.query(V42AIPrefill).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).all()

            # Access sources for each prefill (triggers lazy loading)
            for prefill in prefills:
                _ = prefill.sources  # This triggers a new query each time!

        # Verify N+1 pattern exists
        assert stats.total_queries > 100, f"Expected N+1 pattern (>100 queries), got {stats.total_queries}"
        assert stats.detect_n_plus_one(), "N+1 pattern should be detected"

        stats.print_summary()
        print(f"⚠️  NAIVE APPROACH: {stats.total_queries} queries for {sample_data['prefill_count']} prefills")

    def test_optimized_approach_eliminates_n1(self, db_session: Session, sample_data):
        """
        Optimized test: Demonstrate N+1 elimination with selectinload().

        This test uses SQLAlchemy's selectinload() to fetch all data efficiently:
        - 1 query to fetch all prefills
        - 1 query to fetch all sources (using IN clause)
        Total: 2 queries regardless of N

        This is a >98% reduction in queries for 100 prefills (2 vs 101).
        """
        with assert_query_count(db_session, max_queries=2):
            # Fetch prefills WITH eager loading using selectinload()
            prefills = db_session.query(V42AIPrefill).options(
                selectinload(V42AIPrefill.sources)
            ).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).all()

            # Access sources - should NOT trigger additional queries
            for prefill in prefills:
                _ = prefill.sources  # Data already loaded!

        print(f"✓ OPTIMIZED APPROACH: 2 queries for {sample_data['prefill_count']} prefills")

    def test_comparison_before_after(self, db_session: Session, sample_data):
        """
        Compare naive vs optimized approach side-by-side.

        Demonstrates the dramatic improvement in query count and validates
        that we achieve >90% query reduction.
        """
        # BEFORE: Naive approach
        with profile_queries(db_session) as stats_before:
            prefills = db_session.query(V42AIPrefill).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).all()
            for prefill in prefills:
                _ = prefill.sources

        # Clear session to simulate fresh request
        db_session.expunge_all()

        # AFTER: Optimized approach
        with profile_queries(db_session) as stats_after:
            prefills = db_session.query(V42AIPrefill).options(
                selectinload(V42AIPrefill.sources)
            ).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).all()
            for prefill in prefills:
                _ = prefill.sources

        # Compare performance
        comparison = compare_query_performance(stats_before, stats_after)
        print_comparison(comparison)

        # Assertions
        assert comparison['improvements']['query_reduction_pct'] > 90, \
            f"Expected >90% query reduction, got {comparison['improvements']['query_reduction_pct']:.1f}%"
        assert comparison['improvements']['n_plus_one_eliminated'], \
            "N+1 pattern should be eliminated"
        assert comparison['after']['total_queries'] == 2, \
            f"Optimized approach should use exactly 2 queries, got {comparison['after']['total_queries']}"

        print(f"\n✅ SUCCESS: Achieved {comparison['improvements']['query_reduction_pct']:.1f}% query reduction!")

    def test_bulk_validation_single_update(self, db_session: Session, sample_data):
        """
        Test that bulk validation uses a single UPDATE query, not a loop.

        Before optimization: N UPDATE queries (one per prefill)
        After optimization: 1 UPDATE query with WHERE IN clause

        Query reduction: From N to 1 (>99% for 100 prefills)
        """
        # Get 50 prefills to validate
        prefills = db_session.query(V42AIPrefill).filter(
            V42AIPrefill.session_id == sample_data['session_id'],
            V42AIPrefill.is_validated == False
        ).limit(50).all()

        question_ids = [p.question_id for p in prefills]

        # Track queries for bulk update
        with assert_query_count(db_session, max_queries=3, query_type='UPDATE'):
            # Single UPDATE query for all prefills
            from sqlalchemy import update, and_
            stmt = update(V42AIPrefill).where(
                and_(
                    V42AIPrefill.session_id == sample_data['session_id'],
                    V42AIPrefill.question_id.in_(question_ids)
                )
            ).values(
                is_validated=True,
                updated_at=datetime.utcnow()
            )
            db_session.execute(stmt)
            db_session.commit()

        print(f"✓ Bulk validated {len(question_ids)} prefills with 1 UPDATE query")

    def test_analytics_aggregation_efficient(self, db_session: Session, sample_data):
        """
        Test that analytics use SQL aggregation instead of Python loops.

        Before: Fetch all records and count in Python (1 + N queries)
        After: Use SQL COUNT, GROUP BY (1 query)
        """
        with assert_query_count(db_session, max_queries=3):
            # Efficient aggregation query
            from sqlalchemy import func
            stats = db_session.query(
                V42AIPrefill.section,
                func.count(V42AIPrefill.id).label('total'),
                func.sum(func.case((V42AIPrefill.is_validated == True, 1), else_=0)).label('validated'),
                func.avg(V42AIPrefill.confidence_score).label('avg_confidence')
            ).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).group_by(
                V42AIPrefill.section
            ).all()

            assert len(stats) == 5  # 5 sections
            for section_stats in stats:
                assert section_stats.total > 0
                assert section_stats.avg_confidence is not None

        print(f"✓ Computed analytics for {len(stats)} sections with 1 aggregation query")

    def test_multiple_relationships_eager_loaded(self, db_session: Session, sample_data):
        """
        Test eager loading of multiple relationships simultaneously.

        Loading prefills with both sources AND validation history should use:
        - 1 query for prefills
        - 1 query for sources
        - 1 query for validation history
        Total: 3 queries (not 1 + N + M)
        """
        with assert_query_count(db_session, max_queries=3):
            prefills = db_session.query(V42AIPrefill).options(
                selectinload(V42AIPrefill.sources),
                selectinload(V42AIPrefill.validation_history)
            ).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).all()

            # Access both relationships - should not trigger additional queries
            for prefill in prefills:
                _ = prefill.sources
                _ = prefill.validation_history

        print(f"✓ Loaded {len(prefills)} prefills with sources and validation history in 3 queries")


class TestPerformanceBenchmarks:
    """Performance benchmarks with timing measurements."""

    def test_benchmark_100_prefills_with_sources(self, db_session: Session, sample_data):
        """
        Benchmark: Load 100 prefills with sources.

        Target: <50ms for optimized query (excluding network/disk I/O)
        """
        import time

        # Warm up
        db_session.query(V42AIPrefill).first()

        # Benchmark optimized approach
        start = time.perf_counter()
        with profile_queries(db_session) as stats:
            prefills = db_session.query(V42AIPrefill).options(
                selectinload(V42AIPrefill.sources)
            ).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).all()

            # Access all sources
            total_sources = sum(len(p.sources) for p in prefills)

        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\n{'='*60}")
        print(f"BENCHMARK RESULTS")
        print(f"{'='*60}")
        print(f"Loaded {len(prefills)} prefills with {total_sources} sources")
        print(f"Total queries: {stats.total_queries}")
        print(f"Total time: {duration_ms:.2f}ms")
        print(f"Time per prefill: {duration_ms / len(prefills):.3f}ms")
        print(f"{'='*60}\n")

        # Assertions
        assert stats.total_queries == 2, "Should use exactly 2 queries"
        assert total_sources == 300, "Should load all 300 sources"
        assert not stats.detect_n_plus_one(), "No N+1 pattern should exist"

    def test_benchmark_session_stats_aggregation(self, db_session: Session, sample_data):
        """
        Benchmark: Compute session statistics with SQL aggregation.

        Target: Single query, <10ms
        """
        import time

        start = time.perf_counter()
        with profile_queries(db_session) as stats:
            from sqlalchemy import func
            result = db_session.query(
                func.count(V42AIPrefill.id).label('total'),
                func.count(func.distinct(V42AIPrefill.section)).label('sections'),
                func.sum(func.case((V42AIPrefill.is_validated == True, 1), else_=0)).label('validated'),
                func.avg(V42AIPrefill.confidence_score).label('avg_confidence')
            ).filter(
                V42AIPrefill.session_id == sample_data['session_id']
            ).first()

        duration_ms = (time.perf_counter() - start) * 1000

        print(f"\nSession Stats Computed in {duration_ms:.2f}ms with {stats.total_queries} query")
        print(f"  Total prefills: {result.total}")
        print(f"  Sections: {result.sections}")
        print(f"  Validated: {result.validated}")
        print(f"  Avg confidence: {result.avg_confidence:.2f}")

        assert stats.total_queries == 1, "Should use exactly 1 aggregation query"


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/performance/test_n1_query_fix.py -v -s
    pytest.main([__file__, '-v', '-s'])
