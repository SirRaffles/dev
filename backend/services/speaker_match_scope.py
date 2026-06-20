"""Speaker auto-match scope resolution."""

from typing import Optional


def resolve_match_scope(settings: Optional[dict]) -> tuple[Optional[list], Optional[list], str]:
    """Decide how auto-match should scope its candidate pool based on the
    job's pre-transcription picks vs the declared speaker count.

    Returns (restrict_to_ids, prefer_ids, mode) where mode is one of:
      "scoped"          - picks.length == num_speakers > 0
      "global-prefer"   - picks present but fewer than num_speakers (or auto)
      "global"          - no picks at all
    """
    picks = (settings or {}).get("speaker_ids") or []
    num_raw = (settings or {}).get("num_speakers")
    try:
        num = int(num_raw) if num_raw not in (None, "", "auto") else None
    except (TypeError, ValueError):
        num = None

    if num is not None and num > 0 and len(picks) == num:
        return picks, None, "scoped"
    if picks:
        return None, picks, "global-prefer"
    return None, None, "global"
