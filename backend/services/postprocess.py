"""
Transcript post-processing: safe, meaning-preserving text normalization.
"""

import re
from typing import List


# ---------------------------------------------------------------------------
# Verbatim-mode normalization (always applied, meaning-preserving)
# ---------------------------------------------------------------------------

def normalize_transcript_text(text: str) -> str:
    """Apply safe formatting normalization to transcript text.

    Operations (all meaning-preserving):
    1. Collapse multiple spaces to single space
    2. Fix spacing around punctuation
    3. Collapse stutters (3+ consecutive identical words)
    4. Strip leading/trailing whitespace
    """
    if not text:
        return text

    # 1. Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)

    # 2. Fix spacing around punctuation:
    #    Remove space before sentence-ending punctuation
    text = re.sub(r"\s+([.!?,;:])", r"\1", text)
    #    Ensure space after punctuation (unless end of string or another punctuation)
    text = re.sub(r"([.!?,;:])([A-Za-z])", r"\1 \2", text)

    # 3. Collapse stutters: 3+ consecutive identical words -> single word
    #    e.g. "the the the cat" -> "the cat"
    text = re.sub(
        r"\b(\w+)(?:\s+\1){2,}\b",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )

    # 4. Strip
    text = text.strip()

    return text


def normalize_segments(segments: List[dict]) -> List[dict]:
    """Apply text normalization to all segments in place.

    Returns the same list (mutated) for convenience.
    """
    for seg in segments:
        if seg.get("text"):
            seg["text"] = normalize_transcript_text(seg["text"])
    return segments
