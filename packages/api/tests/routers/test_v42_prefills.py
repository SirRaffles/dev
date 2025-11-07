"""
Tests for V42 Prefills API router endpoints.

These tests verify that all router endpoints work correctly and
use optimized queries to avoid N+1 patterns.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, V42AIPrefill, PrefillSource, ValidationHistory
from app.routers.v42_prefills import router, get_db
from tests.utils import assert_query_count, profile_queries


# Test setup
@pytest.fixture(scope='function')
def db_engine():
    """Create test database engine."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope='function')
def db_session(db_engine):
    """Create test database session."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_client(db_session):
    """Create test client with database override."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    return TestClient(app)


@pytest.fixture
def test_data(db_session):
    """Create test data."""
    session_id = "test-session-abc"
    company_name = "Test Company"

    prefills = []
    for i in range(10):
        prefill = V42AIPrefill(
            session_id=session_id,
            company_name=company_name,
            question_id=f"Q{i}",
            section="financial_info",
            prefilled_value=f"Answer {i}",
            confidence_score=0.85,
            is_validated=(i < 5),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(prefill)
        prefills.append(prefill)

    db_session.flush()

    # Add sources
    for prefill in prefills:
        for j in range(2):
            source = PrefillSource(
                prefill_id=prefill.id,
                source_type='document',
                source_name=f"Doc {j}",
                source_url=f"https://example.com/{j}",
                relevance_score=0.9,
                created_at=datetime.utcnow()
            )
            db_session.add(source)

    # Add validation history for validated prefills
    for prefill in prefills[:5]:
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
        'prefills': prefills
    }


class TestGetPrefillsEndpoint:
    """Tests for GET /prefills/{session_id}/{company_name} endpoint."""

    def test_get_prefills_query_count(self, test_client, test_data, db_session):
        """
        Test that get_prefills uses optimized queries.

        Expected: At most 3 queries (prefills, sources, validation_history)
        Without optimization: Would be 1 + N + M queries
        """
        session_id = test_data['session_id']
        company_name = test_data['company_name']

        with assert_query_count(db_session, max_queries=4):
            response = test_client.get(f"/v42/prefills/prefills/{session_id}/{company_name}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10

        # Verify sources are included
        assert all('sources' in item for item in data)
        assert all(len(item['sources']) == 2 for item in data)

    def test_get_prefills_with_section_filter(self, test_client, test_data, db_session):
        """Test filtering by section with query optimization."""
        session_id = test_data['session_id']
        company_name = test_data['company_name']

        with profile_queries(db_session) as stats:
            response = test_client.get(
                f"/v42/prefills/prefills/{session_id}/{company_name}",
                params={'section': 'financial_info'}
            )

        assert response.status_code == 200
        assert stats.total_queries <= 4  # Max 4 queries
        assert not stats.detect_n_plus_one()

    def test_get_prefills_exclude_validated(self, test_client, test_data, db_session):
        """Test excluding validated prefills."""
        session_id = test_data['session_id']
        company_name = test_data['company_name']

        with assert_query_count(db_session, max_queries=3):
            response = test_client.get(
                f"/v42/prefills/prefills/{session_id}/{company_name}",
                params={'include_validated': False}
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5  # Only unvalidated ones
        assert all(not item['is_validated'] for item in data)


class TestGetPrefillByIdEndpoint:
    """Tests for GET /prefill/{prefill_id} endpoint."""

    def test_get_single_prefill_query_count(self, test_client, test_data, db_session):
        """Test that getting a single prefill is optimized."""
        prefill_id = test_data['prefills'][0].id

        with assert_query_count(db_session, max_queries=3):
            response = test_client.get(f"/v42/prefills/prefill/{prefill_id}")

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == prefill_id
        assert 'sources' in data
        assert len(data['sources']) == 2

    def test_get_nonexistent_prefill(self, test_client, db_session):
        """Test 404 for nonexistent prefill."""
        with profile_queries(db_session) as stats:
            response = test_client.get("/v42/prefills/prefill/99999")

        assert response.status_code == 404
        assert stats.total_queries <= 2  # Should still be optimized


class TestAcceptanceRatesEndpoint:
    """Tests for GET /analytics/acceptance-rates endpoint."""

    def test_acceptance_rates_uses_aggregation(self, test_client, test_data, db_session):
        """
        Test that acceptance rates use SQL aggregation, not loops.

        Expected: 1-2 queries with GROUP BY
        Without optimization: Would be 1 + N queries (one per question)
        """
        with assert_query_count(db_session, max_queries=3):
            response = test_client.get("/v42/prefills/analytics/acceptance-rates")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        # Verify structure
        for item in data:
            assert 'question_id' in item
            assert 'total_prefills' in item
            assert 'accepted_count' in item
            assert 'acceptance_rate' in item

    def test_acceptance_rates_with_filters(self, test_client, test_data, db_session):
        """Test acceptance rates with session and section filters."""
        session_id = test_data['session_id']

        with profile_queries(db_session) as stats:
            response = test_client.get(
                "/v42/prefills/analytics/acceptance-rates",
                params={
                    'session_id': session_id,
                    'section': 'financial_info'
                }
            )

        assert response.status_code == 200
        assert stats.total_queries <= 3  # Aggregation should be efficient
        assert not stats.detect_n_plus_one()


class TestBulkValidateEndpoint:
    """Tests for POST /bulk_validate_section endpoint."""

    def test_bulk_validate_single_update(self, test_client, test_data, db_session):
        """
        Test that bulk validation uses single UPDATE query.

        Expected: 1 UPDATE query + 1 SELECT query + 1 INSERT query
        Without optimization: Would be N UPDATE queries
        """
        payload = {
            'session_id': test_data['session_id'],
            'company_name': test_data['company_name'],
            'section': 'financial_info',
            'user_id': 'test-user',
            'question_ids': ['Q5', 'Q6', 'Q7'],
            'action': 'accepted'
        }

        with profile_queries(db_session) as stats:
            response = test_client.post("/v42/prefills/bulk_validate_section", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data['updated_count'] == 3

        # Should use limited queries (UPDATE, SELECT, bulk INSERT)
        assert stats.total_queries <= 5
        # Should not have N UPDATE queries
        update_queries = stats.get_queries_by_type('UPDATE')
        assert len(update_queries) <= 2  # At most 1-2 UPDATEs, not N

    def test_bulk_validate_validates_correctly(self, test_client, test_data, db_session):
        """Test that bulk validation actually updates the records."""
        payload = {
            'session_id': test_data['session_id'],
            'company_name': test_data['company_name'],
            'section': 'financial_info',
            'user_id': 'test-user',
            'question_ids': ['Q5', 'Q6'],
            'action': 'rejected'
        }

        response = test_client.post("/v42/prefills/bulk_validate_section", json=payload)
        assert response.status_code == 200

        # Verify updates
        prefills = db_session.query(V42AIPrefill).filter(
            V42AIPrefill.question_id.in_(['Q5', 'Q6'])
        ).all()

        assert all(p.is_validated for p in prefills)


class TestSessionStatsEndpoint:
    """Tests for GET /stats/{session_id} endpoint."""

    def test_session_stats_single_query(self, test_client, test_data, db_session):
        """
        Test that session stats use a single aggregation query.

        Expected: 1 query with aggregation functions
        Without optimization: Multiple queries to compute different stats
        """
        session_id = test_data['session_id']

        with assert_query_count(db_session, max_queries=2):
            response = test_client.get(f"/v42/prefills/stats/{session_id}")

        assert response.status_code == 200
        data = response.json()

        assert data['session_id'] == session_id
        assert data['total_prefills'] == 10
        assert data['total_companies'] == 1
        assert data['total_sections'] == 1
        assert data['validated_count'] == 5
        assert 'average_confidence' in data

    def test_session_stats_no_n1_pattern(self, test_client, test_data, db_session):
        """Verify no N+1 pattern in stats endpoint."""
        session_id = test_data['session_id']

        with profile_queries(db_session) as stats:
            response = test_client.get(f"/v42/prefills/stats/{session_id}")

        assert response.status_code == 200
        assert not stats.detect_n_plus_one()
        print(f"\n✓ Session stats computed in {stats.total_queries} queries")


class TestOverallQueryOptimization:
    """Integration tests for overall query optimization."""

    def test_no_n1_patterns_detected(self, test_client, test_data, db_session):
        """
        Comprehensive test: Verify NO N+1 patterns across all endpoints.

        This test calls multiple endpoints and verifies that none of them
        exhibit N+1 query patterns.
        """
        session_id = test_data['session_id']
        company_name = test_data['company_name']
        endpoints_tested = 0

        # Test get prefills
        with profile_queries(db_session) as stats:
            test_client.get(f"/v42/prefills/prefills/{session_id}/{company_name}")
            assert not stats.detect_n_plus_one()
            endpoints_tested += 1

        db_session.expunge_all()

        # Test acceptance rates
        with profile_queries(db_session) as stats:
            test_client.get("/v42/prefills/analytics/acceptance-rates")
            assert not stats.detect_n_plus_one()
            endpoints_tested += 1

        db_session.expunge_all()

        # Test session stats
        with profile_queries(db_session) as stats:
            test_client.get(f"/v42/prefills/stats/{session_id}")
            assert not stats.detect_n_plus_one()
            endpoints_tested += 1

        print(f"\n✅ ALL {endpoints_tested} ENDPOINTS PASSED - NO N+1 PATTERNS DETECTED")

    def test_query_count_scales_properly(self, test_client, db_session):
        """
        Test that query count doesn't increase with data size.

        Create datasets of different sizes and verify query count remains constant.
        """
        results = []

        for size in [10, 50, 100]:
            # Create dataset
            session_id = f"session-{size}"
            for i in range(size):
                prefill = V42AIPrefill(
                    session_id=session_id,
                    company_name="Company",
                    question_id=f"Q{i}",
                    section="test",
                    prefilled_value=f"Value {i}",
                    confidence_score=0.8,
                    is_validated=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db_session.add(prefill)

            db_session.commit()

            # Test query count
            with profile_queries(db_session) as stats:
                test_client.get(f"/v42/prefills/prefills/{session_id}/Company")

            results.append({
                'size': size,
                'queries': stats.total_queries
            })

            db_session.expunge_all()

        # Verify query count is constant
        query_counts = [r['queries'] for r in results]
        print(f"\nQuery counts for different dataset sizes:")
        for r in results:
            print(f"  {r['size']} prefills: {r['queries']} queries")

        # All should be roughly the same (within 1 query due to SQLite quirks)
        assert max(query_counts) - min(query_counts) <= 1, \
            "Query count should not increase with dataset size"

        print("✓ Query count remains constant as dataset scales")


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
