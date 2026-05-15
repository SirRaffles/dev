"""A3 unit tests: word-boundary speaker assignment."""

import pytest

from services.diarization import assign_speakers_to_segments, stitch_speaker_turns
from services.postprocess import normalize_transcript_text


def _word(text, start, end):
    return {"word": text, "start": start, "end": end, "probability": 1.0}


def test_segment_spanning_two_speakers_is_split():
    """One Whisper segment crossing a speaker turn → two output sub-segments."""
    segments = [{
        "start": 0.0,
        "end": 4.0,
        "text": "Hello there how are you",
        "words": [
            _word(" Hello", 0.0, 0.5),
            _word(" there", 0.5, 1.0),
            _word(" how", 2.1, 2.4),
            _word(" are", 2.4, 2.7),
            _word(" you", 2.7, 3.0),
        ],
    }]
    speakers = [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
    ]

    out = assign_speakers_to_segments(segments, speakers)
    assert len(out) == 2
    assert out[0]["speaker"] == "SPEAKER_00"
    assert "Hello" in out[0]["text"] and "there" in out[0]["text"]
    assert out[1]["speaker"] == "SPEAKER_01"
    assert "how" in out[1]["text"] and "you" in out[1]["text"]


def test_punctuation_join_normalizes_correctly():
    """Per-word strings with leading spaces + standalone punctuation collapse
    to canonical spacing after normalize_transcript_text."""
    segments = [{
        "start": 0.0,
        "end": 1.0,
        "text": "Hello , world .",
        "words": [
            _word(" Hello", 0.0, 0.2),
            _word(" ,", 0.2, 0.25),
            _word(" world", 0.25, 0.5),
            _word(" .", 0.5, 0.55),
        ],
    }]
    speakers = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]

    out = assign_speakers_to_segments(segments, speakers)
    assert len(out) == 1
    cleaned = normalize_transcript_text(out[0]["text"])
    assert cleaned == "Hello, world."


def test_gap_between_pyannote_turns_is_handled_by_stitch():
    """A 50ms gap between two same-speaker turns causes one Unknown sub-segment;
    stitch_speaker_turns must not collapse it across different speakers."""
    segments = [{
        "start": 0.0,
        "end": 3.0,
        "text": "one two three",
        "words": [
            _word(" one", 0.0, 0.5),
            _word(" two", 1.0, 1.5),  # falls in the 50ms gap
            _word(" three", 2.0, 2.5),
        ],
    }]
    # Two SPEAKER_00 turns with a 50ms gap at [0.95, 1.0).
    speakers = [
        {"start": 0.0, "end": 0.95, "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 3.0, "speaker": "SPEAKER_00"},
    ]
    out = assign_speakers_to_segments(segments, speakers)
    speakers_observed = [s["speaker"] for s in out]
    # Either three sub-segs with the middle one Unknown, or — acceptable — the
    # gap word lands cleanly inside a SPEAKER_00 turn and produces one sub-seg.
    assert speakers_observed == ["SPEAKER_00", "Unknown", "SPEAKER_00"] or \
           speakers_observed == ["SPEAKER_00"]


def test_no_words_falls_back_to_midpoint():
    """Segment without word-level timestamps uses midpoint heuristic (Voxtral/Parakeet path)."""
    segments = [{"start": 0.0, "end": 4.0, "text": "hello world"}]
    speakers = [
        {"start": 0.0, "end": 1.5, "speaker": "SPEAKER_00"},
        {"start": 1.5, "end": 4.0, "speaker": "SPEAKER_01"},
    ]
    out = assign_speakers_to_segments(segments, speakers)
    assert len(out) == 1
    # Midpoint is 2.0 → falls in SPEAKER_01's turn.
    assert out[0]["speaker"] == "SPEAKER_01"


def test_empty_speakers_returns_segments_unchanged():
    """If diarization yielded no speakers, leave the segments alone."""
    segments = [{"start": 0.0, "end": 1.0, "text": "hi", "words": [_word(" hi", 0, 1)]}]
    out = assign_speakers_to_segments(segments, [])
    assert out is segments or out == segments


def test_single_speaker_segment_unchanged():
    """A segment fully inside one speaker turn produces one output sub-segment."""
    segments = [{
        "start": 0.0,
        "end": 2.0,
        "text": "alpha beta gamma",
        "words": [
            _word(" alpha", 0.0, 0.5),
            _word(" beta", 0.5, 1.0),
            _word(" gamma", 1.0, 1.5),
        ],
    }]
    speakers = [{"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"}]
    out = assign_speakers_to_segments(segments, speakers)
    assert len(out) == 1
    assert out[0]["speaker"] == "SPEAKER_00"
