"""Refinement mode normalization and decision helpers."""

from dataclasses import dataclass
from typing import Literal, Optional

from job_models import TranscriptionSettings

RefinementMode = Literal["auto", "always", "off"]


@dataclass(frozen=True)
class RefinementPolicy:
    mode: RefinementMode
    should_refine: bool
    reason: str
    speaker_ids: list[str]


def normalize_refinement_mode(
    refinement_mode: Optional[str] = None,
    auto_refine: Optional[bool] = None,
) -> RefinementMode:
    """Prefer the explicit enum; fall back to the legacy tri-state bool."""
    if refinement_mode in ("auto", "always", "off"):
        return refinement_mode
    if auto_refine is True:
        return "always"
    if auto_refine is False:
        return "off"
    return "auto"


def _matched_speaker_ids(job) -> list[str]:
    matches = getattr(job, "auto_speaker_matches", None) or {}
    ids: list[str] = []
    for match in matches.values():
        if not isinstance(match, dict):
            continue
        speaker_id = match.get("speaker_id")
        if match.get("matched") is True and speaker_id:
            ids.append(speaker_id)
    return ids


def build_refinement_policy(settings: TranscriptionSettings, job=None) -> RefinementPolicy:
    mode = normalize_refinement_mode(settings.refinement_mode, settings.auto_refine)
    explicit_speaker_ids = settings.speaker_ids or []
    matched_speaker_ids = _matched_speaker_ids(job) if job is not None else []
    speaker_ids = list(dict.fromkeys([*explicit_speaker_ids, *matched_speaker_ids]))

    if mode == "always":
        return RefinementPolicy(mode=mode, should_refine=True,
                                reason="forced", speaker_ids=speaker_ids)
    if mode == "off":
        return RefinementPolicy(mode=mode, should_refine=False,
                                reason="off", speaker_ids=speaker_ids)
    if settings.context_path:
        return RefinementPolicy(mode=mode, should_refine=True,
                                reason="context", speaker_ids=speaker_ids)
    if explicit_speaker_ids:
        return RefinementPolicy(mode=mode, should_refine=True,
                                reason="expected_speakers", speaker_ids=speaker_ids)
    if matched_speaker_ids:
        return RefinementPolicy(mode=mode, should_refine=True,
                                reason="recognized_speaker", speaker_ids=speaker_ids)
    return RefinementPolicy(mode=mode, should_refine=False,
                            reason="no_context_or_speakers", speaker_ids=speaker_ids)
