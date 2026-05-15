"""A3 unit tests: word-boundary speaker assignment."""

from services.diarization import assign_speakers_to_segments
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


def test_gap_between_same_speaker_turns_is_absorbed():
    """A 50ms gap between two same-speaker pyannote turns must be absorbed by
    the tolerance window in speaker_at — no Unknown sub-segment leaks out."""
    segments = [{
        "start": 0.0,
        "end": 3.0,
        "text": "one two three",
        "words": [
            _word(" one", 0.0, 0.5),
            _word(" two", 0.97, 1.5),  # falls inside the [0.95, 1.0) gap
            _word(" three", 2.0, 2.5),
        ],
    }]
    speakers = [
        {"start": 0.0, "end": 0.95, "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 3.0, "speaker": "SPEAKER_00"},
    ]
    out = assign_speakers_to_segments(segments, speakers)
    speakers_observed = [s["speaker"] for s in out]
    # With ±50ms tolerance, the gap-word at t=0.97 maps to SPEAKER_00 (it falls
    # within [0.95-0.05, 0.95+0.05] = [0.90, 1.00] of the first turn's end).
    assert speakers_observed == ["SPEAKER_00"], \
        f"Expected gap to be absorbed into one sub-segment, got {speakers_observed}"


def test_large_gap_between_turns_leaks_unknown():
    """A gap LARGER than the 50ms tolerance must still produce an Unknown
    sub-segment between turns. Locks in that the tolerance doesn't swallow
    real silences."""
    segments = [{
        "start": 0.0,
        "end": 4.0,
        "text": "alpha beta gamma",
        "words": [
            _word(" alpha", 0.0, 0.5),
            _word(" beta", 2.0, 2.5),  # in a wide gap
            _word(" gamma", 3.5, 4.0),
        ],
    }]
    # 1.5s gap between turns is well beyond the 50ms tolerance.
    speakers = [
        {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"},
        {"start": 3.0, "end": 4.0, "speaker": "SPEAKER_01"},
    ]
    out = assign_speakers_to_segments(segments, speakers)
    speakers_observed = [s["speaker"] for s in out]
    assert speakers_observed == ["SPEAKER_00", "Unknown", "SPEAKER_01"]


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
