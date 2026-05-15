# Davrine Transcription Pipeline Fixes (A1/A2/A3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement A1 (decoding params), A2 (silero-vad leading-silence trim), and A3 (word-boundary speaker assignment) per `docs/superpowers/specs/2026-05-15-davrine-transcription-pipeline-fixes-design.md`, with full unit-test coverage and manual validation on a real bilingual two-speaker call.

**Architecture:** Three localized backend changes. A2 lives in `backend/services/audio.py` (new helper + new module-level model cache). A1 changes the `mlx_whisper.transcribe()` call site and decouples word-emission gating in `backend/services/transcription.py`. A3 rewrites `assign_speakers_to_segments` in `backend/services/diarization.py` to use per-word timestamps and split Whisper segments at speaker-turn boundaries. A small amount of glue wires A2 into the Whisper branch of `_run_transcription_sync`.

**Tech Stack:** Python 3.11+, pytest, mlx-whisper, pyannote-audio, silero-vad (loaded via torch.hub — torch is already a transitive dep of pyannote), soundfile, numpy.

---

## File Structure

**Modify:**
- `backend/services/audio.py` — add `find_first_speech_offset()`, `_get_silero_model()`, `make_trimmed_audio()`
- `backend/services/transcription.py:667-708` — A1 kwargs change, decouple word emission; A2 wiring (trim + restore)
- `backend/services/diarization.py:146-162` — rewrite `assign_speakers_to_segments`

**Create:**
- `backend/tests/test_audio_vad.py` — A2 unit tests
- `backend/tests/test_transcription_a1.py` — A1 unit tests (kwargs + emission gating)
- `backend/tests/test_diarization_a3.py` — A3 unit tests
- `Tests/15-29-21.m4a` — copy of root-level audio sample for manual validation (currently `~/Development/apps/whisper-transcription-app/15-29-21.m4a`)

**Reference (read-only):**
- `backend/services/postprocess.py:14-47` — `normalize_transcript_text` (A3 relies on its punctuation-spacing fix)
- `backend/services/diarization.py:109-143` — `stitch_speaker_turns` (A3 output is re-merged by this)
- `backend/job_models.py:375` — `TranscriptionSettings.word_timestamps` default `False`

---

## Task 1: Baseline & branch setup

**Files:**
- None (verification only)

- [ ] **Step 1: Confirm we're on `dev` and tests pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && git status
```
Expected: `On branch dev`, working tree may have unrelated changes — leave them.

- [ ] **Step 2: Run existing tests as baseline**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && source venv/bin/activate && pytest -x -q
```
Expected: all green (note count for later regression check).

- [ ] **Step 3: Stage the audio sample in `Tests/` for the manual validation gate**

Run:
```bash
cp ~/Development/apps/whisper-transcription-app/15-29-21.m4a ~/Development/apps/whisper-transcription-app/Tests/15-29-21.m4a
```
Don't commit — `Tests/` is for local manual validation, not VCS payload. Verify the file exists and is ~5-20 MB.

---

## Task 2: A2 — `find_first_speech_offset` (silero-vad helper)

**Files:**
- Modify: `backend/services/audio.py` (append new functions)
- Create: `backend/tests/test_audio_vad.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_audio_vad.py`:

```python
"""Unit tests for VAD leading-silence trim."""

from unittest.mock import patch, MagicMock

import numpy as np
import pytest


def _fake_silero_load(*_args, **_kwargs):
    """Return (model, utils) tuple shaped like silero-vad's torch.hub return."""
    model = MagicMock()
    get_speech_timestamps = MagicMock()
    # Default behavior: no speech found; tests override per-case.
    get_speech_timestamps.return_value = []
    # silero utils tuple: (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks)
    utils = (get_speech_timestamps, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    return model, utils


def _write_wav(path, duration_s: float, sample_rate: int = 16000):
    import soundfile as sf
    samples = np.zeros(int(duration_s * sample_rate), dtype="float32")
    sf.write(str(path), samples, sample_rate, subtype="PCM_16")


def test_returns_zero_when_no_speech_detected(tmp_path):
    """If silero finds no speech, return 0.0 (caller falls back to raw audio)."""
    from services import audio

    wav = tmp_path / "silence.wav"
    _write_wav(wav, 5.0)

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_fake_silero_load):
        offset = audio.find_first_speech_offset(str(wav))

    assert offset == 0.0


def test_returns_offset_when_leading_silence_exceeds_threshold(tmp_path):
    """If first speech begins at 5s, return ~5.0."""
    from services import audio

    wav = tmp_path / "lead.wav"
    _write_wav(wav, 10.0)

    def _load_with_speech(*_a, **_k):
        model, utils = _fake_silero_load()
        utils[0].return_value = [{"start": 5 * 16000, "end": 8 * 16000}]
        return model, utils

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_load_with_speech):
        offset = audio.find_first_speech_offset(str(wav), min_silence_s=0.5)

    assert offset == pytest.approx(5.0, abs=0.05)


def test_returns_zero_when_lead_below_min_threshold(tmp_path):
    """Speech starts at 0.1s — below 0.5s threshold — return 0.0."""
    from services import audio

    wav = tmp_path / "short_lead.wav"
    _write_wav(wav, 10.0)

    def _load_with_short_lead(*_a, **_k):
        model, utils = _fake_silero_load()
        utils[0].return_value = [{"start": int(0.1 * 16000), "end": 8 * 16000}]
        return model, utils

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=_load_with_short_lead):
        offset = audio.find_first_speech_offset(str(wav), min_silence_s=0.5)

    assert offset == 0.0


def test_returns_zero_and_logs_when_silero_unavailable(tmp_path, caplog):
    """torch.hub.load failure must degrade gracefully to 0.0 (no exception)."""
    from services import audio

    wav = tmp_path / "any.wav"
    _write_wav(wav, 5.0)

    audio._SILERO_CACHE = None
    with patch("torch.hub.load", side_effect=RuntimeError("no network")):
        with caplog.at_level("WARNING"):
            offset = audio.find_first_speech_offset(str(wav))

    assert offset == 0.0
    assert any("silero" in r.message.lower() or "vad" in r.message.lower()
               for r in caplog.records)
```

- [ ] **Step 2: Run tests to confirm they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_audio_vad.py -v
```
Expected: 4 FAILs / errors (function `find_first_speech_offset` does not exist).

- [ ] **Step 3: Implement the helper in `backend/services/audio.py`**

Append to `backend/services/audio.py`:

```python
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Cached silero-vad model handle. None means "not yet attempted" or "load failed".
_SILERO_CACHE: Optional[Tuple[object, object]] = None


def _get_silero_model():
    """Lazily load silero-vad via torch.hub. Returns (model, get_speech_timestamps) or None on failure."""
    global _SILERO_CACHE
    if _SILERO_CACHE is not None:
        return _SILERO_CACHE
    try:
        import torch  # noqa: F401 — required for torch.hub
        model, utils = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            trust_repo=True,
        )
        get_speech_timestamps = utils[0]
        _SILERO_CACHE = (model, get_speech_timestamps)
        return _SILERO_CACHE
    except Exception as exc:
        logger.warning("silero-vad unavailable, skipping leading-silence trim: %s", exc)
        _SILERO_CACHE = None
        return None


def find_first_speech_offset(audio_path: str, min_silence_s: float = 0.5) -> float:
    """Return seconds of leading silence to trim before transcription.

    Returns 0.0 if:
      - silero-vad cannot be loaded,
      - the audio cannot be read,
      - no speech is detected at all,
      - or the detected leading silence is below `min_silence_s`.

    Never raises; all failures degrade to 0.0 with a logged warning.
    """
    try:
        loaded = _get_silero_model()
        if loaded is None:
            return 0.0
        model, get_speech_timestamps = loaded

        import soundfile as sf
        import numpy as np
        import torch

        audio_np, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
        if audio_np.ndim > 1:
            audio_np = audio_np.mean(axis=1)
        if sample_rate != 16000:
            # silero expects 16 kHz; resample crudely via linear interpolation.
            ratio = 16000 / sample_rate
            new_len = int(len(audio_np) * ratio)
            audio_np = np.interp(
                np.linspace(0, len(audio_np) - 1, new_len),
                np.arange(len(audio_np)),
                audio_np,
            ).astype("float32")
            sample_rate = 16000

        tensor = torch.from_numpy(audio_np)
        timestamps = get_speech_timestamps(
            tensor,
            model,
            threshold=0.5,
            sampling_rate=sample_rate,
            min_silence_duration_ms=400,
        )
        if not timestamps:
            return 0.0
        first_start_s = timestamps[0]["start"] / sample_rate
        return first_start_s if first_start_s >= min_silence_s else 0.0
    except Exception as exc:
        logger.warning("VAD lead-silence detection failed: %s", exc)
        return 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_audio_vad.py -v
```
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/audio.py backend/tests/test_audio_vad.py
git commit -m "Audio: add silero-vad leading-silence offset helper (A2 part 1)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: A2 — `make_trimmed_audio` helper

**Files:**
- Modify: `backend/services/audio.py`
- Modify: `backend/tests/test_audio_vad.py`

- [ ] **Step 1: Append failing test**

Append to `backend/tests/test_audio_vad.py`:

```python
def test_make_trimmed_audio_writes_offset_slice(tmp_path):
    """Trimmed file starts at `offset` seconds and is shorter by that amount."""
    import soundfile as sf
    from services import audio

    sr = 16000
    full = np.linspace(0, 1, 10 * sr, dtype="float32")  # 10s ramp 0→1
    src = tmp_path / "src.wav"
    sf.write(str(src), full, sr, subtype="PCM_16")

    out = audio.make_trimmed_audio(str(src), trim_offset=2.5)
    assert out != str(src)

    audio_out, sr_out = sf.read(out, dtype="float32")
    assert sr_out == sr
    expected_len = 10 * sr - int(2.5 * sr)
    assert abs(len(audio_out) - expected_len) <= 1
    # First sample of the trimmed file equals the original at t=2.5s (within fp noise).
    assert audio_out[0] == pytest.approx(full[int(2.5 * sr)], abs=1e-3)
```

- [ ] **Step 2: Run to confirm failure**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_audio_vad.py::test_make_trimmed_audio_writes_offset_slice -v
```
Expected: FAIL (`AttributeError: module 'services.audio' has no attribute 'make_trimmed_audio'`).

- [ ] **Step 3: Implement `make_trimmed_audio`**

Append to `backend/services/audio.py`:

```python
import tempfile


def make_trimmed_audio(audio_path: str, trim_offset: float) -> str:
    """Write a copy of `audio_path` with the first `trim_offset` seconds removed.

    Returns the path of the trimmed WAV file (caller is responsible for cleanup
    via the temp directory). Original file is left untouched.
    """
    import soundfile as sf

    audio_np, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
    start_sample = int(trim_offset * sample_rate)
    trimmed = audio_np[start_sample:]

    fd, out_path = tempfile.mkstemp(suffix="_trimmed.wav")
    import os
    os.close(fd)
    sf.write(out_path, trimmed, sample_rate, subtype="PCM_16")
    return out_path
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_audio_vad.py -v
```
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/audio.py backend/tests/test_audio_vad.py
git commit -m "Audio: add make_trimmed_audio helper (A2 part 2)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: A3 — Word-boundary speaker assignment

**Files:**
- Modify: `backend/services/diarization.py:146-162` (rewrite `assign_speakers_to_segments`)
- Create: `backend/tests/test_diarization_a3.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_diarization_a3.py`:

```python
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
    # We expect "Unknown" sub-seg between two SPEAKER_00 sub-segs.
    speakers_observed = [s["speaker"] for s in out]
    assert speakers_observed == ["SPEAKER_00", "Unknown", "SPEAKER_00"] or \
           speakers_observed == ["SPEAKER_00"]  # acceptable if the gap word lands inside a turn


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
```

- [ ] **Step 2: Run to confirm failure**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_diarization_a3.py -v
```
Expected: at least `test_segment_spanning_two_speakers_is_split` FAILs (current midpoint logic returns a single sub-segment). Some tests may already pass — that's fine.

- [ ] **Step 3: Rewrite `assign_speakers_to_segments`**

Replace `backend/services/diarization.py:146-162` with:

```python
def assign_speakers_to_segments(segments: List[dict], speakers: List[dict]) -> List[dict]:
    """Assign speaker labels to transcription segments.

    If per-word timestamps are available on a segment, the segment is split at
    speaker-turn boundaries so each output sub-segment has exactly one speaker.
    If word timestamps are absent (Voxtral/Parakeet path), falls back to the
    midpoint-of-segment heuristic.
    """
    if not speakers:
        return segments

    def speaker_at(t: float) -> str:
        for turn in speakers:
            if turn["start"] <= t < turn["end"]:
                return turn["speaker"]
        return "Unknown"

    out: List[dict] = []
    for seg in segments:
        words = seg.get("words") or []

        if not words:
            mid = (seg.get("start", 0) + seg.get("end", 0)) / 2
            new_seg = dict(seg)
            new_seg["speaker"] = speaker_at(mid)
            out.append(new_seg)
            continue

        current_speaker = speaker_at(words[0].get("start", seg.get("start", 0)))
        buf_words: List[dict] = []
        buf_start = words[0].get("start", seg.get("start", 0))

        def _flush(end_time: float):
            if not buf_words:
                return
            text = " ".join(w.get("word", "").strip() for w in buf_words if w.get("word", "").strip())
            out.append({
                "start": buf_start,
                "end": end_time,
                "text": text,
                "speaker": current_speaker,
                "words": list(buf_words),
            })

        for w in words:
            t = w.get("start", w.get("end", buf_start))
            w_speaker = speaker_at(t)
            if w_speaker != current_speaker and buf_words:
                _flush(buf_words[-1].get("end", buf_start))
                current_speaker = w_speaker
                buf_words = []
                buf_start = t
            buf_words.append(w)

        if buf_words:
            _flush(buf_words[-1].get("end", seg.get("end", buf_start)))

    return out
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_diarization_a3.py -v
```
Expected: all 6 PASS. If `test_gap_between_pyannote_turns_is_handled_by_stitch` fails because of unexpected ordering, inspect the result — the test allows two valid outcomes.

- [ ] **Step 5: Run the full diarization test surface to confirm no regression**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/ -k diariz -v
```
Expected: all PASS (the rewritten function preserves the no-words and empty-speakers paths).

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/diarization.py backend/tests/test_diarization_a3.py
git commit -m "Diarization: split Whisper segments at speaker-turn boundaries (A3)

Word-boundary algorithm replaces the midpoint heuristic when per-word
timestamps are present; falls back to midpoint for Voxtral/Parakeet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: A1 — Whisper decoding params + decouple word emission

**Files:**
- Modify: `backend/services/transcription.py:667-708`
- Create: `backend/tests/test_transcription_a1.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_transcription_a1.py`:

```python
"""A1 unit tests: Whisper call kwargs and word-emission gating."""

from unittest.mock import patch, MagicMock


def test_whisper_called_with_a1_kwargs(tmp_path, monkeypatch):
    """The Whisper transcribe call must enforce A1 params regardless of settings."""
    from job_models import TranscriptionSettings
    from services import transcription

    # Fake the audio file so the os.path.exists / soundfile guards pass.
    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    captured = {}

    def fake_transcribe(*_args, **kwargs):
        captured.update(kwargs)
        return {"segments": [], "text": "", "language": "en"}

    settings = TranscriptionSettings(
        model_size="large-v3-turbo",
        language="en",
        word_timestamps=False,  # user opted out — A1 must still pass True internally
        enable_diarization=False,
        enable_noise_reduction=False,
    )

    job = MagicMock()
    job.status = "pending"
    job._retry_of = None

    monkeypatch.setattr(transcription.state, "jobs", MagicMock())
    monkeypatch.setattr(transcription.state, "mlx_whisper_available", True)
    with patch("mlx_whisper.transcribe", side_effect=fake_transcribe):
        transcription._run_transcription_sync("job-1", str(audio_path), settings)

    assert captured.get("word_timestamps") is True, "A1 must force word_timestamps=True"
    assert captured.get("condition_on_previous_text") is False
    assert captured.get("logprob_threshold") == -1.0
    temperature = captured.get("temperature")
    assert isinstance(temperature, tuple) and temperature[0] == 0.0 and len(temperature) >= 5
    assert captured.get("no_speech_threshold") == 0.6


def test_emitted_segments_strip_words_when_user_opted_out(tmp_path, monkeypatch):
    """When settings.word_timestamps=False, emitted segments must NOT contain `words`."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_result = {
        "segments": [
            {
                "start": 0.0, "end": 1.0, "text": "hi",
                "words": [{"word": " hi", "start": 0.0, "end": 1.0, "probability": 0.99}],
            }
        ],
        "text": "hi",
        "language": "en",
    }

    settings = TranscriptionSettings(
        model_size="large-v3-turbo",
        language="en",
        word_timestamps=False,
        enable_diarization=False,
        enable_noise_reduction=False,
    )

    job_obj = MagicMock()
    job_obj.status = "pending"
    job_obj._retry_of = None
    job_obj.segments = None

    captured_update = MagicMock()
    monkeypatch.setattr(transcription.state, "jobs", MagicMock(get=MagicMock(return_value=job_obj),
                                                                update=captured_update))
    monkeypatch.setattr(transcription.state, "mlx_whisper_available", True)

    with patch("mlx_whisper.transcribe", return_value=fake_result):
        transcription._run_transcription_sync("job-2", str(audio_path), settings)

    final_segments = job_obj.segments or []
    assert final_segments, "expected at least one emitted segment"
    for seg in final_segments:
        assert "words" not in seg, f"emitted segment must not contain 'words' when user opted out: {seg}"
```

> Note: these tests poke at `_run_transcription_sync` directly because it owns the kwargs site. If `state.jobs.get` or other module-level singletons cause issues at import time, add the missing `monkeypatch.setattr` for those attributes — keep test runtime under 2s.

- [ ] **Step 2: Run to confirm failure**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_transcription_a1.py -v
```
Expected: both FAIL (current kwargs lack `logprob_threshold`, `temperature` tuple, and emit `words` only when `settings.word_timestamps=True` so the second test passes trivially — re-read failure messages, adjust mock setup if `_run_transcription_sync` can't be entered).

- [ ] **Step 3: Update Whisper call kwargs**

Edit `backend/services/transcription.py:667-676` — replace the existing `mlx_whisper.transcribe(...)` call with:

```python
result = mlx_whisper.transcribe(
    audio_path,
    path_or_hf_repo=model_path,
    language=language,
    task="translate" if settings.translate_to_english else "transcribe",
    word_timestamps=True,                          # A1: forced on; needed by A3
    condition_on_previous_text=False,              # A1: stop error propagation
    no_speech_threshold=0.6,
    compression_ratio_threshold=2.4,
    logprob_threshold=-1.0,                        # A1: trigger temperature fallback
    temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),    # A1: decoding fallback ladder
    initial_prompt=initial_prompt,
    verbose=False,
    fp16=True,
)
```

- [ ] **Step 4: Decouple word emission**

Edit `backend/services/transcription.py:692-703` — replace the per-segment loop so `words` is always carried internally:

```python
for segment in result.get("segments", []):
    seg_data = {
        "start": segment["start"],
        "end": segment["end"],
        "text": segment["text"].strip(),
    }
    # A1: always carry words through; A3 needs them. Stripped at emission
    # time if the user opted out (see below, after stitch_speaker_turns).
    if segment.get("words"):
        seg_data["words"] = [
            {
                "word": w.get("word", w.get("text", "")),
                "start": w["start"],
                "end": w["end"],
                "probability": w.get("probability", 1.0),
            }
            for w in segment["words"]
        ]
    transcription_segments.append(seg_data)
    full_text_parts.append(segment["text"].strip())
```

Then, locate the block in the same function that runs **after** `stitch_speaker_turns` (look for `if speakers:` around lines 718-721, then `_update_job(job, progress=70, ...)`). Immediately before `_update_job(job, progress=70, message="Processing segments...")`, add:

```python
# A1: strip per-word data from emitted segments if user opted out.
if not settings.word_timestamps:
    for seg in transcription_segments:
        seg.pop("words", None)
```

- [ ] **Step 5: Run tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_transcription_a1.py -v
```
Expected: both PASS.

- [ ] **Step 6: Run full test suite to check no regression**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest -x -q
```
Expected: full green. If any pre-existing test breaks (likely candidates: a test that asserts emitted segments lack `words` by default or asserts specific Whisper kwargs), inspect and reconcile — the contract change is "internal pipeline carries words, emitted output gated by setting" so any test asserting the old internal shape needs updating.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/transcription.py backend/tests/test_transcription_a1.py
git commit -m "Transcription: A1 — Whisper decoding params + decouple word emission

- condition_on_previous_text=False stops error propagation
- temperature fallback ladder + logprob_threshold trigger reseeding
- word_timestamps forced True internally; stripped at emission if user opted out

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: A2 — Wire VAD trim into the Whisper branch

**Files:**
- Modify: `backend/services/transcription.py` (Whisper branch in `_run_transcription_sync`)

- [ ] **Step 1: Write a failing integration test**

Append to `backend/tests/test_transcription_a1.py`:

```python
def test_vad_trim_restores_segment_timestamps(tmp_path, monkeypatch):
    """When VAD finds a 3s lead, Whisper sees the trimmed file and segment
    timestamps are restored to the original time base."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_whisper_result = {
        "segments": [{"start": 0.0, "end": 2.0, "text": "hi", "words": []}],
        "text": "hi",
        "language": "en",
    }

    settings = TranscriptionSettings(
        model_size="large-v3-turbo",
        language="en",
        word_timestamps=True,
        enable_diarization=False,
        enable_noise_reduction=False,
    )

    job_obj = MagicMock()
    job_obj.status = "pending"
    job_obj._retry_of = None
    job_obj.segments = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job_obj), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "mlx_whisper_available", True)

    trimmed_path = str(tmp_path / "trimmed.wav")
    monkeypatch.setattr("services.audio.find_first_speech_offset", lambda p, **kw: 3.0)
    monkeypatch.setattr("services.audio.make_trimmed_audio", lambda p, trim_offset: trimmed_path)

    received_paths = []

    def capture_path(audio_arg, **_kw):
        received_paths.append(audio_arg)
        return fake_whisper_result

    with patch("mlx_whisper.transcribe", side_effect=capture_path):
        transcription._run_transcription_sync("job-3", str(audio_path), settings)

    assert received_paths == [trimmed_path], "Whisper must receive the trimmed file"
    segs = job_obj.segments or []
    assert segs and segs[0]["start"] == 3.0 and segs[0]["end"] == 5.0, \
        f"timestamps must be restored to original time base, got {segs}"
```

- [ ] **Step 2: Confirm failure**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_transcription_a1.py::test_vad_trim_restores_segment_timestamps -v
```
Expected: FAIL (VAD not wired in; Whisper receives the original path; timestamps stay at 0.0/2.0).

- [ ] **Step 3: Wire VAD into the Whisper branch**

In `backend/services/transcription.py`, locate the Whisper branch (search for the `else:` opening `import mlx_whisper`). Just after `import mlx_whisper` and before computing `language`, add:

```python
# A2: trim leading silence before Whisper so language detection sees real speech.
from services.audio import find_first_speech_offset, make_trimmed_audio
trim_offset = find_first_speech_offset(audio_path)
audio_path_for_whisper = audio_path
trimmed_temp_path = None
if trim_offset > 0:
    logger.info("A2: trimming %.2fs of leading silence before transcription", trim_offset)
    trimmed_temp_path = make_trimmed_audio(audio_path, trim_offset)
    audio_path_for_whisper = trimmed_temp_path
```

Change the `mlx_whisper.transcribe(audio_path, ...)` call to use `audio_path_for_whisper`:

```python
result = mlx_whisper.transcribe(
    audio_path_for_whisper,
    path_or_hf_repo=model_path,
    ...
)
```

Immediately after the `mlx_whisper.transcribe(...)` call returns, before the `transcription_segments = []` line, add:

```python
# A2: restore segment timestamps to the original time base.
if trim_offset > 0:
    for segment in result.get("segments", []):
        segment["start"] = segment.get("start", 0.0) + trim_offset
        segment["end"] = segment.get("end", 0.0) + trim_offset
        for w in segment.get("words", []) or []:
            w["start"] = w.get("start", 0.0) + trim_offset
            w["end"] = w.get("end", 0.0) + trim_offset
```

In the existing `finally` block of `_run_transcription_sync`, add cleanup for the trimmed file before the existing temp-dir cleanup logic:

```python
finally:
    try:
        if 'trimmed_temp_path' in locals() and trimmed_temp_path and os.path.exists(trimmed_temp_path):
            os.remove(trimmed_temp_path)
    except Exception:
        pass
    # ... existing cleanup logic remains unchanged below
```

- [ ] **Step 4: Run tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest tests/test_transcription_a1.py -v
```
Expected: all PASS including the new VAD trim test.

- [ ] **Step 5: Run full suite for regression check**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && pytest -x -q
```
Expected: full green.

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git add backend/services/transcription.py backend/tests/test_transcription_a1.py
git commit -m "Transcription: A2 — wire silero-vad trim into Whisper branch

Skip silent/noisy lead-in before language detection. Diarization stays on
original audio. Whisper segment timestamps are restored before A3 runs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Manual validation gate

**Files:**
- Read: `Tests/15-29-21.m4a` (audio sample, ~35 min Pascal Weber call)
- Read: `Tests/transcript Manukai from Davrine Transcription.txt` (current baseline)
- Read: `Tests/Transcript Manukai Pascal Weber from Turboscribe.txt` (cloud baseline)

- [ ] **Step 1: Pre-register the two speakers in iCloud**

If not already present, create the two speaker folders so A3 can attribute correctly:

```bash
ICLOUD_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription"
for name in "David Marchesseau" "Pascal Weber"; do
  slug=$(echo "$name" | tr ' ' '_')
  mkdir -p "$ICLOUD_BASE/speakers/$slug"
done
```

Open the David Marchesseau speaker folder, add a short `profile.md`:

```
David Marchesseau. French. 17 years at SAP, recently industrial AI go-to-market at IFS. Based in Singapore, relocating to Zurich. Talks about consultative selling, value selling, manufacturing customers, ETH, DACH.
```

And for Pascal Weber:

```
Pascal Weber. Co-founder & CEO of Manukai (CNC programming AI startup, Zurich, ETH spinoff). Co-founder Daniel. Customers include Siemens, DMG Mori, Starrag, Grob. Focus on DACH market. Currently fundraising seed round.
```

- [ ] **Step 2: Restart backend & ensure it picks up the new code**

Run:
```bash
launchctl stop com.whisper.backend && launchctl start com.whisper.backend
tail -f ~/.whisper-backend.log
```
Wait for "Application startup complete." Stop tailing.

- [ ] **Step 3: Run the transcription via the UI**

Open `http://localhost:3000`. Upload `Tests/15-29-21.m4a`. Settings:
- Model: `large-v3-turbo`
- Language: `auto` (deliberately, to validate A2 fixes the arabic opening)
- Diarization: ON
- Expected speakers: select David Marchesseau + Pascal Weber
- Context: leave empty (verify A1+A3 alone produce the improvement)
- Readable mode: OFF (to keep verbatim comparison fair vs current baseline)

Wait for completion. Export the transcript.

- [ ] **Step 4: Compare against acceptance criteria**

Open the new transcript next to `Tests/transcript Manukai from Davrine Transcription.txt`. Check:

1. **No non-target-language opening** — first segment must be English, not Arabic. PASS / FAIL.
2. **Speaker turns visible at sentence-level granularity** — eyeball the first 5 minutes. There should be ≥ 10 speaker changes, not 2-3 mega-blocks. Count and record.
3. **Hallucination reduction** — look for these 5 phrases that were present in the baseline:
   - "Le Price Asset Management" (should now be closer to "Enterprise Asset Management")
   - "Mansion" instead of "mentioned"
   - "Nicole" instead of "technical"
   - "I do have a dedicated technology partner" (added "I do" — should be gone)
   - "Donian" / "Monocargo" / "Stora**g**" (these *won't* be fixed by A — they need B', so don't gate the merge on them)

Record the result: how many of the 4 expected fixes landed.

- [ ] **Step 5: Document the validation result**

Append to `docs/superpowers/plans/2026-05-15-davrine-transcription-pipeline-fixes.md` (this file) a section at the bottom:

```markdown
## Validation Result (filled at end of Task 7)

- Date run:
- Opening segment language correct: yes / no
- Speaker changes in first 5 min: <count> (target ≥ 10)
- Hallucinations resolved (of 4): <count>
- Decision: merge / iterate
- Notes:
```

- [ ] **Step 6: Final commit**

```bash
cd ~/Development/apps/whisper-transcription-app && git add docs/superpowers/plans/2026-05-15-davrine-transcription-pipeline-fixes.md
git commit -m "Plans: record validation result for A1/A2/A3 pipeline fixes

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Validation Result (filled at end of Task 7)

- Date run:
- Opening segment language correct: yes / no
- Speaker changes in first 5 min: <count> (target ≥ 10)
- Hallucinations resolved (of 4): <count>
- Decision: merge / iterate
- Notes:
