"""B7 endpoint: read the learning log for the Activity timeline."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

# Import the MODULE, not the constant — tests reload services.learning to
# repoint LEARNING_LOG_PATH at the icloud_base fixture's tmp path. Importing
# the constant directly would capture the production path at module load.
from services import learning

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])

MAX_LIMIT = 500


@router.get("/log")
async def get_learning_log(
    since: Optional[str] = Query(None, description="ISO timestamp lower bound (inclusive)"),
    type: Optional[str] = Query(None, description="Event type filter (embedding_update, glossary_add, insight_added, ...)"),
    limit: int = Query(100, ge=1, le=MAX_LIMIT, description="Max events to return (cap 500)"),
    offset: int = Query(0, ge=0, description="Skip the first N most-recent events"),
):
    """Return learning events, most recent first."""
    log_path = learning.LEARNING_LOG_PATH  # resolved per-request, not at import
    if not log_path.is_file():
        return {"events": [], "total": 0, "offset": offset, "limit": limit}

    matching: list = []
    try:
        with open(log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if type and record.get("type") != type:
                    continue
                if since and record.get("ts", "") < since:
                    continue
                matching.append(record)
    except OSError:
        logger.warning("learning_log read failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not read learning log")

    matching.reverse()  # most-recent first
    total = len(matching)
    page = matching[offset:offset + limit]
    return {"events": page, "total": total, "offset": offset, "limit": limit}
