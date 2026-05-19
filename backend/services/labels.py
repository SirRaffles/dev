"""Shared helpers for speaker-label classification.

`is_anonymous_label` is the single source of truth for deciding whether a
diarization label still needs a real name. Used by both the orchestrator
(pre-refinement gate decision) and the routes layer (insights extraction,
re-refine validation, learning-source filtering).

Mirror of the frontend regex at src/components/TranscriptView.tsx:13-15.
Keep the two in lockstep when changing — anonymous-vs-named is a contract
boundary between FE and BE that must agree.
"""

import re
from typing import Optional

# `SPEAKER_00`, `Speaker 1`, `Unknown` — case-insensitive. Anything else
# is treated as a real human name.
ANON_SPEAKER_RE = re.compile(r"^(?:SPEAKER_\d+|Speaker\s*\d+|Unknown)$", re.IGNORECASE)


def is_anonymous_label(name: Optional[str]) -> bool:
    """True iff `name` is missing or matches an anonymous diarization label."""
    if not name:
        return True
    return bool(ANON_SPEAKER_RE.match(name.strip()))
