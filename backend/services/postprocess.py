"""
Transcript post-processing: safe, meaning-preserving text normalization
and optional readable-mode transformations.
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


# ---------------------------------------------------------------------------
# Readable-mode transformations (only when output_mode == "readable")
# ---------------------------------------------------------------------------

# Multi-word filler phrases (matched case-insensitively at word boundaries)
FILLER_PHRASES = [
    "you know", "I mean", "sort of", "kind of", "as it were",
    "if you will", "so to speak", "you see", "I guess",
    "I suppose", "to be honest", "to be fair", "at the end of the day",
]

# Single-word fillers (only removed at segment start/end or between commas)
FILLER_WORDS = ["um", "uh", "er", "ah", "hmm", "hm", "mm"]

# Sound effect markers in brackets
_SOUND_MARKERS_RE = re.compile(
    r"\[(?:snorts?|laughs?|coughs?|sighs?|clears?\s+throat|inaudible|crosstalk)\]",
    re.IGNORECASE,
)

# Pre-compiled filler phrase patterns (built once at import time)
_FILLER_PHRASE_PATTERNS = [
    re.compile(r",?\s*\b" + re.escape(phrase) + r"\b\s*,?", re.IGNORECASE)
    for phrase in FILLER_PHRASES
]

# Pre-compiled single-word filler patterns
_FILLER_WORD_PATTERNS_START = [
    re.compile(r"^" + re.escape(w) + r"\b[,.]?\s*", re.IGNORECASE)
    for w in FILLER_WORDS
]
_FILLER_WORD_PATTERNS_END = [
    re.compile(r"[,.]?\s*\b" + re.escape(w) + r"\s*$", re.IGNORECASE)
    for w in FILLER_WORDS
]
_FILLER_WORD_PATTERNS_MID = [
    re.compile(r",\s*\b" + re.escape(w) + r"\b\s*,", re.IGNORECASE)
    for w in FILLER_WORDS
]


def remove_filler_words(text: str) -> str:
    """Remove filler words, phrases, and sound markers from text.

    Conservative approach:
    - Multi-word fillers removed wherever they appear
    - Single-word fillers only at segment start/end or between commas
    - "like" never removed (too ambiguous without POS tagging)
    """
    if not text:
        return text

    # 1. Remove sound markers: [snorts], [laughs], etc.
    text = _SOUND_MARKERS_RE.sub("", text)

    # 2. Remove multi-word filler phrases
    for pattern in _FILLER_PHRASE_PATTERNS:
        text = pattern.sub(" ", text)

    # 3. Remove single-word fillers at boundaries only
    for p in _FILLER_WORD_PATTERNS_START:
        text = p.sub("", text)
    for p in _FILLER_WORD_PATTERNS_END:
        text = p.sub("", text)
    for p in _FILLER_WORD_PATTERNS_MID:
        text = p.sub(",", text)

    # Clean up residual double spaces, leading/trailing commas
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"^\s*,\s*", "", text)
    text = re.sub(r"\s*,\s*$", "", text)

    return text.strip()


def ensure_sentence_boundaries(text: str) -> str:
    """Ensure text has proper sentence structure.

    - Capitalize first character
    - Add terminal punctuation if missing
    - Capitalize letter after sentence-ending punctuation
    """
    if not text:
        return text

    # Capitalize first letter
    if len(text) > 1:
        text = text[0].upper() + text[1:]
    else:
        text = text.upper()

    # Add period if text doesn't end with terminal punctuation
    if text and text[-1] not in ".!?":
        text += "."

    # Capitalize letter after sentence-ending punctuation + space
    def _cap_after_period(match):
        return match.group(1) + match.group(2).upper()

    text = re.sub(r"([.!?]\s+)([a-z])", _cap_after_period, text)

    return text


# Currency patterns: spoken form -> symbol form
_CURRENCY_PATTERNS = [
    # "767 pounds 5 pence" / "767 pounds and 5 pence" / "767 pounds and 5p"
    (re.compile(r"(\d+)\s+pounds?\s+(?:and\s+)?(\d+)\s*(?:pence|p)\b", re.IGNORECASE), r"£\1.\2"),
    # "767 pounds" (no pence)
    (re.compile(r"(\d+)\s+pounds?\b", re.IGNORECASE), r"£\1"),
    # "767 dollars 50 cents" / "767 dollars and 50 cents"
    (re.compile(r"(\d+)\s+dollars?\s+(?:and\s+)?(\d+)\s*cents?\b", re.IGNORECASE), r"$\1.\2"),
    # "767 dollars" (no cents)
    (re.compile(r"(\d+)\s+dollars?\b", re.IGNORECASE), r"$\1"),
    # "767 euros 50 cents" / "767 euros and 50 cents"
    (re.compile(r"(\d+)\s+euros?\s+(?:and\s+)?(\d+)\s*cents?\b", re.IGNORECASE), "\u20ac\\1.\\2"),
    # "767 euros" (no cents)
    (re.compile(r"(\d+)\s+euros?\b", re.IGNORECASE), "\u20ac\\1"),
    # "25 percent" / "25 per cent"
    (re.compile(r"(\d+)\s+per\s*cent\b", re.IGNORECASE), r"\1%"),
]

# Pad single-digit decimal after currency symbol: £767.5 -> £767.05
_CURRENCY_PAD_RE = re.compile(r"([£$€])(\d+)\.(\d)(?!\d)")


def format_numbers_and_currency(text: str) -> str:
    """Format spoken currency and number patterns into symbols."""
    if not text:
        return text

    for pattern, replacement in _CURRENCY_PATTERNS:
        text = pattern.sub(replacement, text)

    # Pad single-digit pence/cents: £767.5 -> £767.05
    text = _CURRENCY_PAD_RE.sub(r"\g<1>\g<2>.0\g<3>", text)

    return text


# Paragraph detection threshold (seconds of silence between segments)
PARAGRAPH_GAP_THRESHOLD = 2.0


def detect_paragraph_breaks(segments: List[dict]) -> List[dict]:
    """Add paragraph_break metadata to segments based on timing gaps.

    A segment gets paragraph_break=True if:
    - Gap >= PARAGRAPH_GAP_THRESHOLD seconds before it, OR
    - Speaker changed from the previous segment

    Mutates segments in place. Returns the list for convenience.
    """
    for i in range(1, len(segments)):
        prev = segments[i - 1]
        curr = segments[i]

        gap = curr.get("start", 0) - prev.get("end", 0)
        speaker_changed = (
            curr.get("speaker") and prev.get("speaker")
            and curr["speaker"] != prev["speaker"]
        )

        if gap >= PARAGRAPH_GAP_THRESHOLD or speaker_changed:
            curr["paragraph_break"] = True

    return segments


def apply_readable_mode(segments: List[dict], detect_paragraphs: bool = True) -> List[dict]:
    """Apply all readable-mode transformations to segments.

    Called only when output_mode == "readable".
    Transforms text within each segment (preserves timestamps/boundaries).
    Optionally adds paragraph_break metadata based on timing gaps.

    Args:
        segments: List of segment dicts with "text" keys.
        detect_paragraphs: If True, run gap-based paragraph detection.
            Set to False for pre-merged captions that already have paragraph flags.

    Returns the same list (mutated) for convenience.
    """
    # 1. Per-segment text transformations
    for seg in segments:
        text = seg.get("text", "")
        if not text:
            continue

        text = remove_filler_words(text)
        text = format_numbers_and_currency(text)
        text = ensure_sentence_boundaries(text)
        seg["text"] = text

    # 2. Cross-segment analysis: paragraph breaks
    if detect_paragraphs:
        detect_paragraph_breaks(segments)

    return segments


# ---------------------------------------------------------------------------
# YouTube caption merging (display-lines -> sentences)
# ---------------------------------------------------------------------------

# Max words in a single sentence before forcing a break (handles unpunctuated captions)
_MAX_SENTENCE_WORDS = 150

# Default time interval between paragraph breaks for merged captions
CAPTION_PARAGRAPH_INTERVAL = 45.0  # seconds


def merge_caption_segments(
    segments: List[dict],
    paragraph_interval: float = CAPTION_PARAGRAPH_INTERVAL,
) -> List[dict]:
    """Merge YouTube caption display-lines into sentence-based segments.

    YouTube captions are short overlapping display lines that break mid-sentence.
    This function:
    1. Interpolates per-word timestamps from caption timing
    2. Groups words into full sentences (split on .!? followed by capital letter)
    3. Adds paragraph_break flags at regular time intervals

    Args:
        segments: Caption segments with text, start, end (overlapping timestamps).
        paragraph_interval: Seconds between paragraph breaks (0 to disable).

    Returns:
        New list of sentence-level segments with proper timestamps and paragraph flags.
    """
    if not segments:
        return segments

    # 1. Build word-to-time mapping via linear interpolation within each caption
    words_with_times: List[tuple] = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        words = text.split()
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        dur = max(end - start, 0.01)
        for i, w in enumerate(words):
            t = start + dur * (i / max(len(words) - 1, 1))
            words_with_times.append((w, t))

    if not words_with_times:
        return segments

    # 2. Group words into sentences
    result: List[dict] = []
    buf: List[str] = []
    buf_start = words_with_times[0][1]

    for idx, (word, t) in enumerate(words_with_times):
        buf.append(word)

        # Check for sentence-ending punctuation
        stripped = word.rstrip("\"')\u201d\u2019")
        is_terminal = bool(stripped) and stripped[-1] in ".!?"

        # Next word starts with uppercase (new sentence)
        next_cap = False
        if idx + 1 < len(words_with_times):
            nw = words_with_times[idx + 1][0]
            next_cap = bool(nw) and nw[0].isupper()

        is_last = idx + 1 >= len(words_with_times)
        force_break = len(buf) >= _MAX_SENTENCE_WORDS

        if (is_terminal and (next_cap or is_last)) or force_break:
            result.append({
                "text": " ".join(buf),
                "start": round(buf_start, 2),
                "end": round(t, 2),
            })
            buf = []
            if not is_last:
                buf_start = words_with_times[idx + 1][1]

    # Remaining words without terminal punctuation
    if buf:
        result.append({
            "text": " ".join(buf),
            "start": round(buf_start, 2),
            "end": round(words_with_times[-1][1], 2),
        })

    # 3. Add paragraph breaks at regular time intervals
    if result and paragraph_interval > 0:
        last_para_time = result[0].get("start", 0)
        for sent in result[1:]:
            if sent.get("start", 0) - last_para_time >= paragraph_interval:
                sent["paragraph_break"] = True
                last_para_time = sent.get("start", 0)

    return result
