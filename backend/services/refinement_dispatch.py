"""Refinement dispatch service.

Owns `dispatch_refinement_for_job` (create/reset refinement state + submit the
worker once) and its shared `_set_refinement_status` helper. Relocated out of
`routes/refinement.py` so `services/orchestrator.py` no longer imports a route.

Import discipline: this module imports `state` and (lazily, as the original
route did) `services.transcription` and the route's `_run_refinement_for_job`.
It must NOT import anything from `routes` at module load — the lazy import
inside `dispatch_refinement_for_job` keeps the route's worker reachable without
creating a module-load cycle.
"""

import logging
from typing import List, Optional

import state

logger = logging.getLogger(__name__)


def _set_refinement_status(job, status: str) -> None:
    """Mirror refinement_status onto the in-memory job and persist via state.jobs.update.

    Logs (debug) and swallows on persistence failure -- the in-memory attribute
    is what UI polls.
    """
    if job is None:
        return
    job.refinement_status = status
    try:
        state.jobs.update(job)
    except Exception:
        logger.debug("jobs.update mirror failed for job %s", job.job_id, exc_info=True)


def dispatch_refinement_for_job(
    job,
    speaker_ids: Optional[List[str]] = None,
    context_path: Optional[str] = None,
    audio_path: Optional[str] = None,
) -> None:
    """Create/reset refinement state and submit the worker once."""
    if not job:
        raise ValueError("job is required")
    state.refinement_store.create(job.job_id)
    _set_refinement_status(job, "pending")
    from services.transcription import _update_job
    _update_job(job, phase="refining")
    job._defer_audio_cleanup = True
    # Lazy import: the worker lives in routes.refinement. Importing it here
    # (call time, not module load) keeps this service free of a route import
    # cycle while preserving the original dispatch behaviour.
    from routes.refinement import _run_refinement_for_job
    state.transcription_executor.submit(
        _run_refinement_for_job,
        job.job_id,
        speaker_ids,
        context_path,
        audio_path,
    )
