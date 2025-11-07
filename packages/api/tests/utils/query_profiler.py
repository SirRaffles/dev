"""Database query profiling utilities for performance testing.

This module provides tools to profile and analyze database queries during tests,
helping identify N+1 query patterns and performance issues.
"""
from contextlib import contextmanager
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import re
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


@dataclass
class QueryProfile:
    """Profile information for a single database query."""
    statement: str
    params: tuple
    duration_ms: float
    timestamp: datetime
    stack_trace: str = ""

    @property
    def query_type(self) -> str:
        """Extract the query type (SELECT, INSERT, UPDATE, DELETE)."""
        match = re.match(r'^\s*(SELECT|INSERT|UPDATE|DELETE)', self.statement, re.IGNORECASE)
        return match.group(1).upper() if match else 'UNKNOWN'

    @property
    def is_select(self) -> bool:
        """Check if this is a SELECT query."""
        return self.query_type == 'SELECT'

    def __repr__(self):
        return f"<QueryProfile({self.query_type}, {self.duration_ms:.2f}ms)>"


@dataclass
class QueryStats:
    """Statistics for profiled queries."""
    queries: List[QueryProfile] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = None

    @property
    def total_queries(self) -> int:
        """Total number of queries executed."""
        return len(self.queries)

    @property
    def select_count(self) -> int:
        """Number of SELECT queries."""
        return sum(1 for q in self.queries if q.is_select)

    @property
    def total_duration_ms(self) -> float:
        """Total duration of all queries in milliseconds."""
        return sum(q.duration_ms for q in self.queries)

    @property
    def avg_duration_ms(self) -> float:
        """Average query duration in milliseconds."""
        return self.total_duration_ms / self.total_queries if self.total_queries > 0 else 0.0

    def get_queries_by_type(self, query_type: str) -> List[QueryProfile]:
        """Get all queries of a specific type."""
        return [q for q in self.queries if q.query_type == query_type]

    def detect_n_plus_one(self, threshold: int = 5) -> bool:
        """
        Detect potential N+1 query patterns.

        A simple heuristic: If there are many similar SELECT queries in sequence,
        it might indicate an N+1 pattern.

        Args:
            threshold: Number of similar queries to consider as N+1 pattern

        Returns:
            True if N+1 pattern detected
        """
        # Group similar queries (normalized by removing parameters)
        query_groups: Dict[str, int] = {}
        for query in self.queries:
            if query.is_select:
                # Normalize query by removing parameter values
                normalized = re.sub(r'\d+', '?', query.statement)
                normalized = re.sub(r"'[^']*'", '?', normalized)
                query_groups[normalized] = query_groups.get(normalized, 0) + 1

        # Check if any group exceeds threshold
        return any(count >= threshold for count in query_groups.values())

    def summary(self) -> Dict[str, Any]:
        """Get a summary of query statistics."""
        return {
            'total_queries': self.total_queries,
            'select_queries': self.select_count,
            'insert_queries': len(self.get_queries_by_type('INSERT')),
            'update_queries': len(self.get_queries_by_type('UPDATE')),
            'delete_queries': len(self.get_queries_by_type('DELETE')),
            'total_duration_ms': round(self.total_duration_ms, 2),
            'avg_duration_ms': round(self.avg_duration_ms, 2),
            'n_plus_one_detected': self.detect_n_plus_one()
        }

    def print_summary(self):
        """Print a formatted summary of query statistics."""
        print("\n" + "="*60)
        print("DATABASE QUERY PROFILE SUMMARY")
        print("="*60)
        summary = self.summary()
        print(f"Total Queries:       {summary['total_queries']}")
        print(f"  - SELECT:          {summary['select_queries']}")
        print(f"  - INSERT:          {summary['insert_queries']}")
        print(f"  - UPDATE:          {summary['update_queries']}")
        print(f"  - DELETE:          {summary['delete_queries']}")
        print(f"Total Duration:      {summary['total_duration_ms']:.2f}ms")
        print(f"Average Duration:    {summary['avg_duration_ms']:.2f}ms")
        print(f"N+1 Pattern:         {'DETECTED ⚠️' if summary['n_plus_one_detected'] else 'Not detected ✓'}")
        print("="*60 + "\n")


@contextmanager
def profile_queries(db_session: Session, verbose: bool = False):
    """
    Context manager to profile database queries.

    Usage:
        with profile_queries(db_session) as stats:
            # Execute your database operations
            results = db_session.query(Model).all()

        # After context, analyze stats
        print(f"Total queries: {stats.total_queries}")
        stats.print_summary()

    Args:
        db_session: SQLAlchemy session to profile
        verbose: If True, print each query as it executes

    Yields:
        QueryStats object containing all query information
    """
    stats = QueryStats()
    engine = db_session.bind

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query start time."""
        context._query_start_time = datetime.utcnow()
        if verbose:
            print(f"\n[QUERY START] {statement[:100]}...")

    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query completion and duration."""
        duration = (datetime.utcnow() - context._query_start_time).total_seconds() * 1000

        query = QueryProfile(
            statement=statement,
            params=parameters,
            duration_ms=duration,
            timestamp=datetime.utcnow()
        )
        stats.queries.append(query)

        if verbose:
            print(f"[QUERY END] {duration:.2f}ms - {query.query_type}")

    # Attach event listeners
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    event.listen(engine, "after_cursor_execute", after_cursor_execute)

    try:
        yield stats
    finally:
        stats.end_time = datetime.utcnow()
        # Remove event listeners
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
        event.remove(engine, "after_cursor_execute", after_cursor_execute)


@contextmanager
def assert_query_count(db_session: Session, max_queries: int, query_type: str = None):
    """
    Context manager that asserts a maximum number of queries.

    Useful for testing that optimizations are working correctly.

    Usage:
        with assert_query_count(db_session, max_queries=2):
            # This should execute at most 2 queries
            results = db_session.query(Model).options(
                selectinload(Model.related)
            ).all()

    Args:
        db_session: SQLAlchemy session to profile
        max_queries: Maximum number of queries allowed
        query_type: If specified, only count queries of this type (e.g., 'SELECT')

    Raises:
        AssertionError: If query count exceeds max_queries
    """
    with profile_queries(db_session) as stats:
        yield stats

    if query_type:
        actual_count = len(stats.get_queries_by_type(query_type))
        query_desc = f"{query_type} queries"
    else:
        actual_count = stats.total_queries
        query_desc = "queries"

    if actual_count > max_queries:
        stats.print_summary()
        raise AssertionError(
            f"Expected at most {max_queries} {query_desc}, but got {actual_count}. "
            f"This may indicate an N+1 query pattern!"
        )


def compare_query_performance(
    stats_before: QueryStats,
    stats_after: QueryStats,
    improvement_threshold: float = 0.5
) -> Dict[str, Any]:
    """
    Compare two query profiles to measure performance improvement.

    Args:
        stats_before: Query stats before optimization
        stats_after: Query stats after optimization
        improvement_threshold: Expected improvement ratio (0.5 = 50% reduction)

    Returns:
        Dictionary with comparison metrics
    """
    query_reduction = (stats_before.total_queries - stats_after.total_queries) / stats_before.total_queries if stats_before.total_queries > 0 else 0
    time_reduction = (stats_before.total_duration_ms - stats_after.total_duration_ms) / stats_before.total_duration_ms if stats_before.total_duration_ms > 0 else 0

    comparison = {
        'before': {
            'total_queries': stats_before.total_queries,
            'total_duration_ms': round(stats_before.total_duration_ms, 2),
            'n_plus_one': stats_before.detect_n_plus_one()
        },
        'after': {
            'total_queries': stats_after.total_queries,
            'total_duration_ms': round(stats_after.total_duration_ms, 2),
            'n_plus_one': stats_after.detect_n_plus_one()
        },
        'improvements': {
            'query_reduction_pct': round(query_reduction * 100, 2),
            'time_reduction_pct': round(time_reduction * 100, 2),
            'n_plus_one_eliminated': stats_before.detect_n_plus_one() and not stats_after.detect_n_plus_one()
        },
        'meets_threshold': query_reduction >= improvement_threshold or time_reduction >= improvement_threshold
    }

    return comparison


def print_comparison(comparison: Dict[str, Any]):
    """Print a formatted comparison of before/after query performance."""
    print("\n" + "="*60)
    print("QUERY PERFORMANCE COMPARISON")
    print("="*60)

    print("\nBEFORE OPTIMIZATION:")
    print(f"  Total Queries:     {comparison['before']['total_queries']}")
    print(f"  Total Duration:    {comparison['before']['total_duration_ms']:.2f}ms")
    print(f"  N+1 Pattern:       {'YES ⚠️' if comparison['before']['n_plus_one'] else 'NO'}")

    print("\nAFTER OPTIMIZATION:")
    print(f"  Total Queries:     {comparison['after']['total_queries']}")
    print(f"  Total Duration:    {comparison['after']['total_duration_ms']:.2f}ms")
    print(f"  N+1 Pattern:       {'YES ⚠️' if comparison['after']['n_plus_one'] else 'NO'}")

    print("\nIMPROVEMENTS:")
    imp = comparison['improvements']
    print(f"  Query Reduction:   {imp['query_reduction_pct']:.1f}%")
    print(f"  Time Reduction:    {imp['time_reduction_pct']:.1f}%")
    print(f"  N+1 Eliminated:    {'YES ✓' if imp['n_plus_one_eliminated'] else 'N/A'}")
    print(f"  Meets Threshold:   {'YES ✓' if comparison['meets_threshold'] else 'NO ⚠️'}")

    print("="*60 + "\n")
