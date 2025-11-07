"""V42 Prefills API Router.

This router implements optimized database queries to avoid N+1 query patterns.
All endpoints use SQLAlchemy's eager loading strategies (selectinload, joinedload)
to fetch related data efficiently.

Performance Optimizations:
- GET /prefills/{session_id}/{company_name}: Uses selectinload() for sources
- GET /analytics/acceptance-rates: Uses aggregated queries with group_by()
- POST /bulk_validate_section: Uses single UPDATE query, not loops

Observability:
- Structured logging for all operations
- Event tracking for user actions
- Performance metrics for database operations
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_, update
from sqlalchemy.orm import Session, selectinload, joinedload
from pydantic import BaseModel, Field

from ..models import V42AIPrefill, PrefillSource, ValidationHistory
from ..utils.logging import get_logger
from ..utils.events import (
    track_event, track_prefill_validation, track_bulk_operation,
    EventType, EventCategory
)
from ..utils.metrics import measure_time, timed

logger = get_logger(__name__)
router = APIRouter(prefix="/v42/prefills", tags=["prefills"])


# Pydantic schemas for request/response
class SourceResponse(BaseModel):
    id: int
    source_type: str
    source_name: str
    source_url: Optional[str]
    relevance_score: Optional[float]
    excerpt: Optional[str]

    class Config:
        from_attributes = True


class ValidationHistoryResponse(BaseModel):
    id: int
    user_id: str
    action: str
    previous_value: Optional[str]
    new_value: Optional[str]
    feedback: Optional[str]
    validated_at: datetime

    class Config:
        from_attributes = True


class PrefillResponse(BaseModel):
    id: int
    session_id: str
    company_name: str
    question_id: str
    section: str
    prefilled_value: Optional[str]
    confidence_score: Optional[float]
    is_validated: bool
    sources: List[SourceResponse] = []
    validation_history: List[ValidationHistoryResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AcceptanceRateResponse(BaseModel):
    question_id: str
    section: str
    total_prefills: int
    accepted_count: int
    rejected_count: int
    modified_count: int
    acceptance_rate: float


class BulkValidateRequest(BaseModel):
    session_id: str
    company_name: str
    section: str
    user_id: str
    question_ids: List[str]
    action: str = Field(..., pattern="^(accepted|rejected)$")


# Dependency to get database session (mock for now)
def get_db():
    """Get database session. Replace with actual DB session factory."""
    # This would be replaced with actual database session
    # For now, this is a placeholder
    raise NotImplementedError("Database session dependency not configured")


@router.get(
    "/prefills/{session_id}/{company_name}",
    response_model=List[PrefillResponse],
    summary="Get prefills for session and company (N+1 OPTIMIZED)"
)
@timed("get_prefills")
async def get_prefills(
    session_id: str,
    company_name: str,
    section: Optional[str] = None,
    include_validated: bool = Query(default=True),
    db: Session = Depends(get_db)
):
    """
    Get all prefills for a session and company.

    OPTIMIZATION: Uses selectinload() to fetch all sources in 2 queries total:
    - Query 1: Fetch all matching prefills
    - Query 2: Fetch all sources for those prefills (single IN query)

    Before optimization: 1 + N queries (1 for prefills + 1 per prefill for sources)
    After optimization: 2 queries total regardless of N

    If include_validated=True, also fetches validation history (adds 1 more query).
    Total: 3 queries for complete dataset vs 1 + N + N without optimization.
    """
    logger.info(
        "Fetching prefills",
        extra={
            'session_id': session_id,
            'company_name': company_name,
            'section': section,
            'include_validated': include_validated
        }
    )

    try:
        with measure_time('database_query_prefills', {
            'session_id': session_id,
            'company_name': company_name
        }):
            # Build query with eager loading
            query = db.query(V42AIPrefill).options(
                # selectinload uses IN query to fetch all sources efficiently
                selectinload(V42AIPrefill.sources)
            )

            # Apply filters
            query = query.filter(
                and_(
                    V42AIPrefill.session_id == session_id,
                    V42AIPrefill.company_name == company_name
                )
            )

            if section:
                query = query.filter(V42AIPrefill.section == section)

            if not include_validated:
                query = query.filter(V42AIPrefill.is_validated == False)

            # If validation history is needed, add another selectinload
            if include_validated:
                query = query.options(
                    selectinload(V42AIPrefill.validation_history)
                )

            # Execute query - all related data fetched efficiently
            prefills = query.all()

        if not prefills:
            logger.warning(
                "No prefills found",
                extra={
                    'session_id': session_id,
                    'company_name': company_name
                }
            )
            raise HTTPException(status_code=404, detail="No prefills found")

        logger.info(
            f"Retrieved {len(prefills)} prefills",
            extra={
                'session_id': session_id,
                'company_name': company_name,
                'count': len(prefills)
            }
        )

        return prefills

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch prefills",
            extra={
                'session_id': session_id,
                'company_name': company_name,
                'error': str(exc)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/prefill/{prefill_id}",
    response_model=PrefillResponse,
    summary="Get single prefill with sources (N+1 OPTIMIZED)"
)
async def get_prefill_by_id(
    prefill_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a single prefill by ID with all related data.

    OPTIMIZATION: Uses joinedload() for one-to-one or small relationships,
    selectinload() for one-to-many to avoid cartesian product issues.
    """
    prefill = db.query(V42AIPrefill).options(
        selectinload(V42AIPrefill.sources),
        selectinload(V42AIPrefill.validation_history)
    ).filter(V42AIPrefill.id == prefill_id).first()

    if not prefill:
        raise HTTPException(status_code=404, message="Prefill not found")

    return prefill


@router.get(
    "/analytics/acceptance-rates",
    response_model=List[AcceptanceRateResponse],
    summary="Get acceptance rates by question (N+1 OPTIMIZED)"
)
async def get_acceptance_rates(
    session_id: Optional[str] = None,
    section: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get acceptance rates for prefills aggregated by question.

    OPTIMIZATION: Uses SQL aggregation with COUNT and GROUP BY instead of
    fetching all records and counting in Python loops.

    Before optimization: 1 query to get all prefills + N queries to count validations
    After optimization: 1 query with aggregation

    Query reduction: From 1 + N to 1 (>90% reduction for 10+ questions)
    """
    # Subquery to get validation actions
    validation_subquery = db.query(
        ValidationHistory.prefill_id,
        ValidationHistory.action,
        func.count(ValidationHistory.id).label('action_count')
    ).group_by(
        ValidationHistory.prefill_id,
        ValidationHistory.action
    ).subquery()

    # Main query with aggregation
    query = db.query(
        V42AIPrefill.question_id,
        V42AIPrefill.section,
        func.count(V42AIPrefill.id).label('total_prefills'),
        func.sum(
            func.case(
                (validation_subquery.c.action == 'accepted', validation_subquery.c.action_count),
                else_=0
            )
        ).label('accepted_count'),
        func.sum(
            func.case(
                (validation_subquery.c.action == 'rejected', validation_subquery.c.action_count),
                else_=0
            )
        ).label('rejected_count'),
        func.sum(
            func.case(
                (validation_subquery.c.action == 'modified', validation_subquery.c.action_count),
                else_=0
            )
        ).label('modified_count')
    ).outerjoin(
        validation_subquery,
        V42AIPrefill.id == validation_subquery.c.prefill_id
    ).group_by(
        V42AIPrefill.question_id,
        V42AIPrefill.section
    )

    # Apply filters
    if session_id:
        query = query.filter(V42AIPrefill.session_id == session_id)
    if section:
        query = query.filter(V42AIPrefill.section == section)

    results = query.all()

    # Calculate acceptance rates
    response = []
    for row in results:
        total = row.total_prefills
        accepted = row.accepted_count or 0
        rejected = row.rejected_count or 0
        modified = row.modified_count or 0

        acceptance_rate = (accepted / total * 100) if total > 0 else 0.0

        response.append(AcceptanceRateResponse(
            question_id=row.question_id,
            section=row.section,
            total_prefills=total,
            accepted_count=accepted,
            rejected_count=rejected,
            modified_count=modified,
            acceptance_rate=round(acceptance_rate, 2)
        ))

    return response


@router.post(
    "/bulk_validate_section",
    summary="Bulk validate prefills in a section (N+1 OPTIMIZED)"
)
async def bulk_validate_section(
    request: BulkValidateRequest,
    db: Session = Depends(get_db)
):
    """
    Bulk validate multiple prefills in a single operation.

    OPTIMIZATION: Uses single UPDATE query with WHERE IN clause instead of
    looping through prefills and updating one by one.

    Before optimization: N UPDATE queries (one per prefill)
    After optimization: 1 UPDATE query

    Query reduction: From N to 1 (>90% reduction)
    """
    logger.info(
        "Starting bulk validation",
        extra={
            'session_id': request.session_id,
            'company_name': request.company_name,
            'section': request.section,
            'question_count': len(request.question_ids),
            'action': request.action
        }
    )

    try:
        with measure_time('bulk_validate_database_operation', {
            'session_id': request.session_id,
            'question_count': len(request.question_ids)
        }):
            # Single UPDATE query for all matching prefills
            stmt = update(V42AIPrefill).where(
                and_(
                    V42AIPrefill.session_id == request.session_id,
                    V42AIPrefill.company_name == request.company_name,
                    V42AIPrefill.section == request.section,
                    V42AIPrefill.question_id.in_(request.question_ids)
                )
            ).values(
                is_validated=True,
                updated_at=datetime.utcnow()
            )

            result = db.execute(stmt)
            db.commit()

            # Get the updated prefills to create validation history
            # Still use selectinload for efficient fetching
            prefills = db.query(V42AIPrefill).options(
                selectinload(V42AIPrefill.sources)
            ).filter(
                and_(
                    V42AIPrefill.session_id == request.session_id,
                    V42AIPrefill.company_name == request.company_name,
                    V42AIPrefill.section == request.section,
                    V42AIPrefill.question_id.in_(request.question_ids)
                )
            ).all()

            # Bulk insert validation history (single INSERT with multiple rows)
            validation_records = [
                ValidationHistory(
                    prefill_id=prefill.id,
                    user_id=request.user_id,
                    action=request.action,
                    previous_value=prefill.prefilled_value,
                    new_value=prefill.prefilled_value,
                    validated_at=datetime.utcnow()
                )
                for prefill in prefills
            ]

            db.bulk_save_objects(validation_records)
            db.commit()

        # Track bulk operation event
        track_bulk_operation(
            session_id=request.session_id,
            operation=request.action,
            question_ids=request.question_ids,
            section_name=request.section,
            success_count=len(prefills),
            failure_count=0
        )

        logger.info(
            "Bulk validation completed successfully",
            extra={
                'session_id': request.session_id,
                'updated_count': len(prefills),
                'section': request.section
            }
        )

        return {
            "message": f"Successfully validated {len(prefills)} prefills",
            "updated_count": len(prefills),
            "session_id": request.session_id,
            "section": request.section
        }

    except Exception as exc:
        logger.error(
            "Bulk validation failed",
            extra={
                'session_id': request.session_id,
                'section': request.section,
                'error': str(exc)
            },
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/stats/{session_id}",
    summary="Get session statistics (N+1 OPTIMIZED)"
)
async def get_session_stats(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get statistics for a session using aggregated queries.

    OPTIMIZATION: Single query with aggregations instead of multiple queries.
    """
    stats = db.query(
        func.count(V42AIPrefill.id).label('total_prefills'),
        func.count(func.distinct(V42AIPrefill.company_name)).label('companies'),
        func.count(func.distinct(V42AIPrefill.section)).label('sections'),
        func.sum(func.case((V42AIPrefill.is_validated == True, 1), else_=0)).label('validated'),
        func.avg(V42AIPrefill.confidence_score).label('avg_confidence')
    ).filter(
        V42AIPrefill.session_id == session_id
    ).first()

    return {
        "session_id": session_id,
        "total_prefills": stats.total_prefills or 0,
        "total_companies": stats.companies or 0,
        "total_sections": stats.sections or 0,
        "validated_count": stats.validated or 0,
        "average_confidence": round(stats.avg_confidence or 0.0, 2)
    }
