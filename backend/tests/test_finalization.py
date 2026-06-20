"""Characterization tests for orchestrator finalization helpers.

Pin the behaviour of `_all_labels_matched` (and the `_finalize_after_alignment`
review-status mapping) before S5 moves `dispatch_refinement_for_job` into a
service. These tests must pass against the current code.

`_all_labels_matched(job)` reads exactly two attributes:
- `job.segments`             -> list[dict] with a "speaker" key per segment
- `job.auto_speaker_matches` -> dict[label, {"matched": bool, ...}]
A label counts as "known" if it is a real (non-anonymous) name, or if it has a
matched=True entry in auto_speaker_matches. Empty segments are vacuously matched.
"""

from services.orchestrator import _all_labels_matched, _finalize_after_alignment
from job_models import (
    SPEAKER_REVIEW_NEEDS_REVIEW,
    SPEAKER_REVIEW_NOT_NEEDED,
)


class _Job:
    """Minimal stand-in exposing only the attributes the helpers read/write."""

    def __init__(self, segments=None, auto_speaker_matches=None):
        self.job_id = "job-test"
        self.segments = segments or []
        self.auto_speaker_matches = auto_speaker_matches or {}
        # Written by _finalize_after_alignment.
        self.speakers_resolved = None
        self.speaker_review_status = None


def test_all_labels_matched_true_when_no_anonymous():
    # Every segment label is a real human name -> all known.
    job = _Job(segments=[
        {"speaker": "Alice", "text": "hi"},
        {"speaker": "Bob", "text": "hello"},
    ])
    assert _all_labels_matched(job) is True


def test_all_labels_matched_true_when_anonymous_but_auto_matched():
    # Anonymous label, but B5 auto-match resolved it -> known.
    job = _Job(
        segments=[{"speaker": "SPEAKER_00", "text": "hi"}],
        auto_speaker_matches={"SPEAKER_00": {"matched": True, "name": "Alice"}},
    )
    assert _all_labels_matched(job) is True


def test_all_labels_matched_true_when_segments_empty():
    # Vacuously true — nothing to resolve.
    job = _Job(segments=[])
    assert _all_labels_matched(job) is True


def test_all_labels_matched_false_when_unresolved():
    # Anonymous label with no auto-match entry -> unresolved.
    job = _Job(segments=[
        {"speaker": "Alice", "text": "hi"},
        {"speaker": "SPEAKER_01", "text": "uh"},
    ])
    assert _all_labels_matched(job) is False


def test_all_labels_matched_false_when_auto_match_not_matched():
    # Entry exists but matched is False -> still unresolved.
    job = _Job(
        segments=[{"speaker": "SPEAKER_00", "text": "hi"}],
        auto_speaker_matches={"SPEAKER_00": {"matched": False}},
    )
    assert _all_labels_matched(job) is False


def test_finalize_sets_not_needed_when_matched(monkeypatch):
    """When all labels are known, finalization marks the job resolved and
    maps review status to NOT_NEEDED. Stub out _update_job, the policy, and
    refinement availability so only the review-status mapping is exercised."""
    import services.orchestrator as orch

    monkeypatch.setattr(orch, "_update_job", lambda job, **kw: None)

    class _Policy:
        should_refine = False
        reason = "test"
        speaker_ids = None

    monkeypatch.setattr(orch, "build_refinement_policy", lambda settings, job: _Policy())

    job = _Job(segments=[{"speaker": "Alice", "text": "hi"}])
    _finalize_after_alignment(job, settings=object(), audio_path=None, mode="best")

    assert job.speakers_resolved is True
    assert job.speaker_review_status == SPEAKER_REVIEW_NOT_NEEDED


def test_finalize_sets_needs_review_when_unresolved(monkeypatch):
    """Unresolved labels -> speakers_resolved False, status NEEDS_REVIEW."""
    import services.orchestrator as orch

    monkeypatch.setattr(orch, "_update_job", lambda job, **kw: None)

    class _Policy:
        should_refine = False
        reason = "test"
        speaker_ids = None

    monkeypatch.setattr(orch, "build_refinement_policy", lambda settings, job: _Policy())

    job = _Job(segments=[{"speaker": "SPEAKER_00", "text": "hi"}])
    _finalize_after_alignment(job, settings=object(), audio_path=None, mode="best")

    assert job.speakers_resolved is False
    assert job.speaker_review_status == SPEAKER_REVIEW_NEEDS_REVIEW
