"""A3-light unit tests: time-proportional speaker assignment for engines
without per-word timestamps (Parakeet, Voxtral). Mirror of test_diarization_a3.py
for the word-boundary case."""

from services.diarization import assign_speakers_time_proportional


def test_segment_fully_inside_one_turn_passes_through():
    """A segment that fits inside one pyannote turn keeps its full text."""
    segments = [{"start": 0.0, "end": 2.0, "text": "alpha beta gamma"}]
    turns = [{"start": 0.0, "end": 3.0, "speaker": "SPEAKER_00"}]
    out = assign_speakers_time_proportional(segments, turns)
    assert len(out) == 1
    assert out[0]["speaker"] == "SPEAKER_00"
    assert out[0]["text"] == "alpha beta gamma"


def test_segment_spanning_two_turns_splits_by_time_ratio():
    """A 10s segment with 5s in turn A + 5s in turn B → ~50/50 word split."""
    segments = [{"start": 0.0, "end": 10.0, "text": "one two three four five six seven eight nine ten"}]
    turns = [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
    ]
    out = assign_speakers_time_proportional(segments, turns)
    assert len(out) == 2
    assert out[0]["speaker"] == "SPEAKER_00"
    assert out[1]["speaker"] == "SPEAKER_01"
    # Word count must match input total exactly (no drop, no dup).
    total_words = sum(len(s["text"].split()) for s in out)
    assert total_words == 10
    # 5s/10s = 50% → 5 words first, 5 words second.
    assert len(out[0]["text"].split()) == 5
    assert len(out[1]["text"].split()) == 5


def test_segment_spanning_three_turns_produces_three_subsegments():
    """N-way safety: 10s segment with A=[0-3], B=[3-4], A=[4-10] → 3 sub-segments."""
    segments = [{"start": 0.0, "end": 10.0,
                 "text": "yes that is right what do you think about it"}]
    turns = [
        {"start": 0.0, "end": 3.0, "speaker": "A"},
        {"start": 3.0, "end": 4.0, "speaker": "B"},
        {"start": 4.0, "end": 10.0, "speaker": "A"},
    ]
    out = assign_speakers_time_proportional(segments, turns)
    assert len(out) == 3
    speakers = [s["speaker"] for s in out]
    assert speakers == ["A", "B", "A"]
    total_words = sum(len(s["text"].split()) for s in out)
    assert total_words == 10, f"word count must be preserved, got {total_words}"
    # Time ratios 3/10, 1/10, 6/10 → word splits approximately 3/1/6.
    counts = [len(s["text"].split()) for s in out]
    assert counts[1] == 1, f"middle (B) should get 1 word, got {counts}"


def test_empty_turns_returns_segments_unchanged():
    """If diarization yielded no turns, leave segments alone (mirrors A3)."""
    segments = [{"start": 0.0, "end": 1.0, "text": "hi"}]
    out = assign_speakers_time_proportional(segments, [])
    assert out == segments


def test_segment_fully_outside_any_turn_falls_back_to_unknown():
    """If a segment is entirely outside any pyannote turn (silence the model
    transcribed anyway), the whole segment gets speaker=Unknown."""
    segments = [{"start": 5.0, "end": 7.0, "text": "ghost text"}]
    turns = [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}]
    out = assign_speakers_time_proportional(segments, turns)
    assert len(out) == 1
    assert out[0]["speaker"] == "Unknown"
    assert out[0]["text"] == "ghost text"


def test_single_word_segment_does_not_overflow():
    """A 1-word segment split across 2 turns: ceil math must not duplicate the word."""
    segments = [{"start": 0.0, "end": 2.0, "text": "hello"}]
    turns = [
        {"start": 0.0, "end": 1.0, "speaker": "A"},
        {"start": 1.0, "end": 2.0, "speaker": "B"},
    ]
    out = assign_speakers_time_proportional(segments, turns)
    total_words = sum(len(s["text"].split()) for s in out)
    assert total_words == 1, "single word must not duplicate across split"


def test_empty_text_segment_emits_no_subsegments():
    """A segment with empty text produces no output rows (no whitespace junk)."""
    segments = [{"start": 0.0, "end": 2.0, "text": "   "}]
    turns = [{"start": 0.0, "end": 2.0, "speaker": "A"}]
    out = assign_speakers_time_proportional(segments, turns)
    assert out == []
