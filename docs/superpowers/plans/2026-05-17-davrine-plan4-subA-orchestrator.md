# Davrine Quality Dial — Plan 4 Sub-plan A (Orchestrator Backend + API Cutover) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the architectural pivot of spec `docs/superpowers/specs/2026-05-17-davrine-quality-dial-orchestration-design.md` — introduce a backend orchestrator that composes Best/Quick stacks, narrow the `engine` API surface to `Literal["auto-best", "auto-quick"]` with hard 400 rejection of legacy values, add a `phase` field to `TranscriptionJob` for the phased progress bar, and migrate the JPR watcher in lockstep so the always-on watcher daemon doesn't 400 on every submission.

**Architecture:** A small new module `backend/services/orchestrator.py` owns Best/Quick dispatch. The current inline Whisper branch (~lines 686-end of `services/transcription.py`) is first extracted into a `transcribe_with_whisper(audio_path, settings, job=None) -> dict` callable preserving A1/A2/A3 wiring exactly. A new `assign_speakers_time_proportional` helper in `services/diarization.py` provides A3-light for engines without word timestamps (N-way safe). After the refactor, `_run_transcription_sync` collapses to a tiny wrapper that routes by `settings.engine`; all legacy direct-engine branches (Voxtral Cloud, Voxtral Local, Whisper-direct, Parakeet-direct) are removed (call sites only — function definitions stay for Sub-plan D to delete). `TranscriptionSettings.engine` becomes a `Literal["auto-best", "auto-quick"]` default `"auto-best"`, `model_size` is dropped, and `TranscriptionJob` gains an in-memory `phase` field surfaced via `GET /job/{id}`. The query-param defaults + engine validation branches in `backend/routes/transcription.py` are rewritten to accept only the two new engine values. Critically, `watcher/config.py` is updated in the same plan so the launchd-managed JPR watcher keeps working at cut-over.

**Tech Stack:** Python 3.11+, FastAPI, pytest, pydantic, asyncio, ThreadPoolExecutor, mlx-whisper, pyannote-audio, parakeet-mlx.

---

## File Structure

**Create:**
- `backend/services/orchestrator.py` — `orchestrate_transcription(job_id, audio_path, settings, mode)` plus `_phases.PHASE_*` constants; thin coordinator that delegates to the existing transcription/diarization/refinement helpers
- `backend/tests/test_orchestrator.py` — unit tests for Best/Quick dispatch, parallel diarization wiring, phase transitions, refinement dispatch
- `backend/tests/test_diarization_time_proportional.py` — unit tests for the new N-way `assign_speakers_time_proportional` helper

**Modify:**
- `backend/services/transcription.py` — Task 2 extracts `transcribe_with_whisper`; Task 7 collapses `_run_transcription_sync` to a thin router; legacy direct-engine branches REMOVED at their call sites only (function defs `transcribe_with_voxtral`, `transcribe_with_voxtral_local`, `transcribe_with_parakeet` stay in place for Sub-plan D)
- `backend/services/diarization.py` — Task 3 adds `assign_speakers_time_proportional(segments, speaker_turns)` (the A3-light, N-way helper)
- `backend/job_models.py:18-36` — Task 4 adds `self.phase: Optional[str] = None` to `TranscriptionJob.__init__`
- `backend/job_models.py:385-409` — Task 5 narrows `TranscriptionSettings.engine` to `Literal["auto-best", "auto-quick"]` default `"auto-best"`; deletes `model_size` field
- `backend/services/transcription.py` `_update_job` (~lines 554-562) — Task 4 extends to accept an optional `phase` parameter
- `backend/routes/transcription.py:113, 117, 127-148, 248, 253, 270-291, 424, 428, 451-466, 638-648` — Task 6 + Task 8 rewrite query-param defaults + engine validation + GET response (surface `phase`)
- `watcher/config.py:23-32` — Task 9 changes `TRANSCRIPTION_SETTINGS["engine"]` → `"auto-best"` and removes `model_size` key
- `backend/tests/test_transcription_a1.py` (4 tests) — Task 10 fixture migration `engine="whisper"` → `engine="auto-best"`, drop `model_size` kwarg
- `backend/tests/test_inline_auto_match.py` (2 tests) — Task 10 fixture migration
- `backend/tests/test_auto_refine_orchestration.py` (3 tests at lines 190, 228, 264) — Task 10 fixture migration
- `backend/tests/test_file_validation.py` — Task 10 rewrite the invalid-engine test, update `?engine=whisper` query strings
- `backend/tests/test_diarization_a3.py` — Task 10 add a Voxtral/Parakeet-style coverage note to the docstring (no Voxtral-specific test currently lives here; the midpoint fallback test at line 109 stays as-is — it documents the path the new time-proportional helper REPLACES for Quick mode, so add a cross-reference comment)

**Reference (read-only):**
- `backend/services/transcription.py:34-208` — `load_context_document`, `derive_context_terms`, `load_speakers_context`, `merge_context_sources`, `build_initial_prompt`, `transcribe_with_parakeet` (already exist; the orchestrator reuses them)
- `backend/services/transcription.py:565-932` — current `_run_transcription_sync`; the Whisper branch (~lines 686-799) is the source for `transcribe_with_whisper`; the surrounding diarization parallelism + B5 auto-match (lines 627-840) becomes the orchestrator's shared post-transcribe pipeline
- `backend/services/diarization.py:146-222` — existing `assign_speakers_to_segments` (A3 word-boundary) and `stitch_speaker_turns`; the new helper mirrors the input/output shape
- `backend/routes/refinement.py:174-266` — `_run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)`; signature unchanged in Sub-plan A — Sub-plan B extends it internally to do diarization polish. Orchestrator's Best mode submits to this on `state.transcription_executor` after the verbatim transcript is ready.
- `backend/routes/refinement.py:53-100` — `_run_post_refinement_learning` (Plan 2 B7); orchestrator does not call this directly — `_run_refinement_for_job` already chains it
- `backend/state.py:72` — `transcription_executor = ThreadPoolExecutor(max_workers=1)` — orchestrator dispatches the async refinement here, same pool the transcription job ran on
- `backend/tests/conftest.py` — fixture patterns; `icloud_base`, `client`, `tmp_audio` already exist
- `docs/superpowers/specs/2026-05-17-davrine-quality-dial-orchestration-design.md` — authoritative spec; the Phase Lifecycle table (lines 215-224) is the single source of truth for `phase` transitions
- `docs/superpowers/plans/2026-05-17-davrine-plan4-subB-refinement-polish.md` — Sub-plan B (Combo C). Ships first. Best mode's refinement call assumes its extended schema is in place.

---

## Conventions for all tasks

- **Working tree:** assume ~22 WIP files are uncommitted. NEVER use `git add -A` / `git add .`. Always stage by exact path. The plan file itself was committed in the planning step; subsequent task commits stage only the files that task touches.
- **Branch:** all work lands on `dev`. The branch is already pushed (ahead 20 commits at plan-write time).
- **Venv:** run pytest from the backend venv:
  ```bash
  cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest <args>
  ```
  or invoke `./venv/bin/python` directly with absolute paths.
- **TDD discipline:** Use superpowers:test-driven-development. Failing test first, watch it fail with the expected error, implement minimum to pass, then commit.
- **Commit granularity:** one commit per task after all its tests pass. Use the format `Plan 4A: <task summary>` so the log is greppable for the orchestrator sub-plan.
- **No backend restart needed** between most tasks — pytest hits the code directly. Task 11 is the only end-to-end manual smoke; it requires `launchctl kickstart -k gui/$(id -u)/com.whisper.backend` AND restarting the watcher: `launchctl kickstart -k gui/$(id -u)/com.whisper.jpr-watcher`.
- **Ship-lockstep with Sub-plan C:** the backend's hard 400 on legacy `engine` values means the frontend MUST be sending `auto-best` / `auto-quick` by the time this plan's Task 11 runs. Coordinate the cut-over commit.

---

## Task 1: Baseline & spec re-read

**Files:**
- None (verification only)

- [ ] **Step 1: Confirm we're on `dev`**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && git status -sb | head -3
```
Expected: `## dev...origin/dev [ahead N]` (working tree may have WIP changes — leave them alone).

- [ ] **Step 2: Run existing backend tests as baseline**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: a clean pass count (record the number for regression check at Task 11). If anything fails on baseline, stop and investigate before touching code.

- [ ] **Step 3: Confirm Sub-plan B has shipped (code-side check, not log-side)**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && grep -n "speaker_corrections" backend/services/refinement.py backend/services/diarization.py 2>/dev/null
```
Expected: at least one hit in `backend/services/refinement.py` (Sub-plan B's diarization-polish writes corrections back via that field). Planning-doc commits do NOT satisfy this — only the actual code lookup does. If the grep is empty, STOP — Sub-plan B must ship first (the orchestrator's Best path assumes refinement performs diarization polish). Bonus check: `git log --oneline --all -- backend/services/refinement.py | head -5` should show a recent commit touching the file.

- [ ] **Step 4: Re-read the spec**

Re-read `docs/superpowers/specs/2026-05-17-davrine-quality-dial-orchestration-design.md` sections "Backend Orchestrator", "Phased Progress Bar" (the lifecycle table is authoritative), "Migration & Removal (no fallback)", and "Sub-plan A". Confirm acceptance criterion: a request with `engine="voxtral-local"` returns 400; a request with `engine="auto-best"` produces a Whisper-backed transcript with phase transitions `diarizing` → `transcribing` → `None` (completed) → `refining` → `learning` → `None`.

---

## Task 2: Extract `transcribe_with_whisper` (refactor prereq)

**Files:**
- Modify: `backend/services/transcription.py` (Whisper inline branch at ~lines 686-799 becomes a callable)
- Test: `backend/tests/test_transcription_a1.py` (existing tests stay green — they prove A1/A2 wiring is preserved)

The Whisper code currently lives inline inside `_run_transcription_sync`. Extracting it is the FIRST step because the orchestrator needs Whisper as a callable, not an inline branch. This task changes nothing else — `_run_transcription_sync` now calls `transcribe_with_whisper(...)` where it used to inline the body. All existing A1/A2 tests must stay green.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_transcription_a1.py` (append to the bottom):

```python
def test_transcribe_with_whisper_is_callable_and_returns_result_dict(tmp_path, monkeypatch):
    """Extraction proof: transcribe_with_whisper exists and returns
    {text, segments, language} preserving A1 kwargs."""
    from job_models import TranscriptionSettings
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    fake_result = {
        "segments": [{"start": 0.0, "end": 1.0, "text": "hi", "words": [
            {"word": " hi", "start": 0.0, "end": 1.0, "probability": 0.99}
        ]}],
        "text": "hi",
        "language": "en",
    }

    captured = {}

    def fake_whisper(*_args, **kwargs):
        captured.update(kwargs)
        return fake_result

    settings = TranscriptionSettings(
        model_size="large-v3-turbo",  # still accepted in Task 2 — Task 5 removes it
        language="en",
        word_timestamps=True,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="whisper",  # still legal in Task 2 — Task 5 narrows it
    )

    with patch("mlx_whisper.transcribe", side_effect=fake_whisper):
        out = transcription.transcribe_with_whisper(str(audio_path), settings, job=None)

    assert isinstance(out, dict), f"expected dict, got {type(out)}"
    assert "segments" in out and "text" in out and "language" in out
    assert captured.get("word_timestamps") is True
    assert captured.get("condition_on_previous_text") is False
    assert captured.get("logprob_threshold") == -1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_transcription_a1.py::test_transcribe_with_whisper_is_callable_and_returns_result_dict -v 2>&1 | tail -15
```
Expected: FAIL — `AttributeError: module 'services.transcription' has no attribute 'transcribe_with_whisper'`.

- [ ] **Step 3: Extract the Whisper branch into a function**

Open `backend/services/transcription.py`. Locate the Whisper inline branch — it lives in the `else:` clause inside `_run_transcription_sync` from `import mlx_whisper` (~line 687) through the end of `full_text = result.get("text", " ".join(full_text_parts))` (~line 781).

Insert a new function definition AFTER `transcribe_with_voxtral_local` and BEFORE `_should_auto_refine` (i.e. before `~line 544`). The function body is the extracted branch, with these adjustments: takes `(audio_path: str, settings, job=None)`, returns a dict shaped like `{"segments": [...], "text": str, "language": str}`, updates `job.language` and `job.language_probability` AT THE CALL SITE in `_run_transcription_sync` (not inside the helper) so the helper is reusable.

```python
def transcribe_with_whisper(audio_path: str, settings: TranscriptionSettings, job=None) -> dict:
    """Transcribe with MLX-Whisper, preserving A1 decoding params + A2 VAD trim + A3 word-timestamp carry.

    Returns {segments, text, language}. Words are carried INTERNALLY through
    each segment so A3 word-boundary speaker assignment downstream can split.
    The caller is responsible for the optional A1 strip of words from emitted
    segments when settings.word_timestamps is False.
    """
    import mlx_whisper

    # A2: trim leading silence before Whisper so language detection sees real speech.
    from services.audio import find_first_speech_offset, make_trimmed_audio
    trim_offset = find_first_speech_offset(audio_path)
    audio_path_for_whisper = audio_path
    trimmed_temp_path = None
    if trim_offset > 0:
        logger.info("A2: trimming %.2fs of leading silence before transcription", trim_offset)
        trimmed_temp_path = make_trimmed_audio(audio_path, trim_offset)
        audio_path_for_whisper = trimmed_temp_path

    language = None if settings.language == "auto" else settings.language

    # In Sub-plan A, settings.model_size is still present (Task 5 removes it).
    # Default to large-v3-turbo — the orchestrator's Best mode always uses Turbo.
    model_size = getattr(settings, "model_size", None) or "large-v3-turbo"
    model_info = MLX_MODELS.get(model_size, MLX_MODELS["large-v3-turbo"])
    model_path = model_info["path"]
    logger.info("Using model: %s (%s)", model_size, model_path)

    from services.glossary import load_global_glossary
    context_text = merge_context_sources(
        load_global_glossary(),
        load_context_document(settings.context_path),
        load_speakers_context(settings.speaker_ids),
    )
    initial_prompt = build_initial_prompt(context_text)
    if initial_prompt:
        logger.info("Using context document as initial_prompt (%d chars)", len(initial_prompt))

    try:
        result = mlx_whisper.transcribe(
            audio_path_for_whisper,
            path_or_hf_repo=model_path,
            language=language,
            task="translate" if settings.translate_to_english else "transcribe",
            word_timestamps=True,                          # A1: forced on; needed by A3
            condition_on_previous_text=False,              # A1
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,                        # A1
            temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),    # A1
            initial_prompt=initial_prompt,
            verbose=False,
            fp16=True,
        )
    finally:
        # A2: clean up the VAD-trimmed temp file we may have created.
        if trimmed_temp_path:
            try:
                os.remove(trimmed_temp_path)
            except OSError:
                pass

    # A2: restore segment timestamps to the original time base.
    if trim_offset > 0:
        for segment in result.get("segments", []):
            segment["start"] = segment.get("start", 0.0) + trim_offset
            segment["end"] = segment.get("end", 0.0) + trim_offset
            for w in segment.get("words", []) or []:
                w["start"] = w.get("start", 0.0) + trim_offset
                w["end"] = w.get("end", 0.0) + trim_offset

    transcription_segments = []
    full_text_parts = []
    for segment in result.get("segments", []):
        seg_data = {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"].strip(),
        }
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

    return {
        "segments": transcription_segments,
        "text": result.get("text", " ".join(full_text_parts)),
        "language": result.get("language", "unknown"),
    }
```

Then in `_run_transcription_sync`, replace the inline Whisper branch (the entire `else:` block starting `import mlx_whisper` ~line 687 through `full_text = result.get("text", " ".join(full_text_parts))` ~line 781) with:

```python
            else:
                _update_job(job, progress=20, message="Transcribing with MLX-Whisper (GPU-accelerated)...")
                result = transcribe_with_whisper(audio_path, settings, job=job)
                job.language = result.get("language", "unknown")
                job.language_probability = 0.99
                transcription_segments = result["segments"]
                full_text = result["text"]
```

Delete the now-orphaned `if 'trimmed_temp_path' in locals()` finally-clause cleanup at lines ~907-910 (the new helper owns the temp file). Leave the rest of the `finally:` block intact.

- [ ] **Step 4: Run all A1/A2 tests to verify nothing regressed**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_transcription_a1.py tests/test_audio_vad.py -v 2>&1 | tail -20
```
Expected: ALL tests pass — both the new extraction test and the four pre-existing A1 tests (`test_whisper_called_with_a1_kwargs`, `test_emitted_segments_strip_words_when_user_opted_out`, `test_emitted_segments_keep_words_when_user_opted_in`, `test_vad_trim_restores_segment_timestamps`).

- [ ] **Step 5: Run the broader unit suite to catch anything else**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/ -x -q --ignore=tests/test_calls_api.py 2>&1 | tail -10
```
Expected: pass count ≥ baseline from Task 1 Step 2. (`test_calls_api.py` may have unrelated WIP-flake; document if it fails so we don't chase a ghost.)

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/transcription.py backend/tests/test_transcription_a1.py
git commit -m "Plan 4A Task 2: extract transcribe_with_whisper helper from _run_transcription_sync"
```

---

## Task 3: Add `assign_speakers_time_proportional` (A3-light, N-way safe)

**Files:**
- Modify: `backend/services/diarization.py` (add new helper after `assign_speakers_to_segments`)
- Create: `backend/tests/test_diarization_time_proportional.py`

For engines without per-word timestamps (Parakeet in Quick mode, the now-deprecated Voxtral path), we cannot use the A3 word-boundary split. The fallback splits each segment at speaker-turn boundaries by time-proportional text ratio. A segment spanning 3 pyannote turns produces 3 sub-segments; a segment fully inside one turn passes through unchanged. Word allocation per sub-segment uses `ceil(N_words * (sub_duration / total_duration))` with a final-segment rounding fix to absorb the +ceil bias so total word count matches the input.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_diarization_time_proportional.py`:

```python
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
                 "text": "Hi yes that is right what do you think about it"}]
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_diarization_time_proportional.py -v 2>&1 | tail -15
```
Expected: ALL FAIL — `ImportError: cannot import name 'assign_speakers_time_proportional' from 'services.diarization'`.

- [ ] **Step 3: Implement the helper**

Add to the END of `backend/services/diarization.py`:

```python
def assign_speakers_time_proportional(segments: List[dict], speaker_turns: List[dict]) -> List[dict]:
    """A3-light: split each segment at speaker-turn boundaries by
    time-proportional text ratio.

    Used when the text engine does NOT emit per-word timestamps (Parakeet,
    Voxtral). Handles N-way splits: a segment spanning 3+ pyannote turns
    produces 3+ sub-segments. Word allocation per sub-segment uses
    ceil(N_words * (sub_duration / total_duration)) with a final-segment
    rounding fix to absorb the +ceil bias so total word count matches input.

    Args:
        segments: List of {start, end, text} segments (no word timestamps).
        speaker_turns: List of pyannote turns {start, end, speaker}.

    Returns:
        New list of sub-segments {start, end, text, speaker}. A segment
        fully inside one turn passes through unchanged (with speaker added).
        A segment outside all turns gets speaker="Unknown".
    """
    import math

    if not speaker_turns:
        return segments

    out: List[dict] = []

    for seg in segments:
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", 0.0))
        seg_text = (seg.get("text") or "").strip()
        if not seg_text:
            continue
        words = seg_text.split()
        n_words = len(words)
        seg_duration = max(seg_end - seg_start, 1e-6)

        # Compute the speaker-turn overlaps for this segment, in time order.
        spans = []  # list of (sub_start, sub_end, speaker)
        for turn in speaker_turns:
            t_start = float(turn["start"])
            t_end = float(turn["end"])
            overlap_start = max(seg_start, t_start)
            overlap_end = min(seg_end, t_end)
            if overlap_end > overlap_start:
                spans.append((overlap_start, overlap_end, turn["speaker"]))
        # Sort by start so output order is chronological.
        spans.sort(key=lambda s: s[0])

        if not spans:
            # Segment lives outside any pyannote turn.
            out.append({
                "start": seg_start,
                "end": seg_end,
                "text": seg_text,
                "speaker": "Unknown",
            })
            continue

        # Single-span fast path (and N=1 edge case where the whole segment
        # fits inside one turn): the full text belongs to one speaker.
        if len(spans) == 1:
            out.append({
                "start": seg_start,
                "end": seg_end,
                "text": seg_text,
                "speaker": spans[0][2],
            })
            continue

        # N-way split. Allocate words proportional to each span's duration.
        # ceil ensures every span gets >= 1 word when its duration > 0; the
        # final span's count is recomputed as the remainder so totals match.
        counts = []
        used = 0
        for i, (s_start, s_end, _spk) in enumerate(spans):
            if i == len(spans) - 1:
                counts.append(max(0, n_words - used))
            else:
                share = (s_end - s_start) / seg_duration
                c = min(n_words - used, max(1, math.ceil(n_words * share)))
                counts.append(c)
                used += c

        idx = 0
        for (s_start, s_end, spk), c in zip(spans, counts):
            if c <= 0:
                continue
            chunk = " ".join(words[idx:idx + c])
            idx += c
            if not chunk:
                continue
            out.append({
                "start": s_start,
                "end": s_end,
                "text": chunk,
                "speaker": spk,
            })

    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_diarization_time_proportional.py -v 2>&1 | tail -20
```
Expected: ALL 7 tests pass.

- [ ] **Step 5: Run the existing A3 suite to verify no regression**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_diarization_a3.py -v 2>&1 | tail -15
```
Expected: all existing A3 tests still pass.

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/diarization.py backend/tests/test_diarization_time_proportional.py
git commit -m "Plan 4A Task 3: add assign_speakers_time_proportional (A3-light, N-way safe)"
```

---

## Task 4: Add `phase` field to `TranscriptionJob` + extend `_update_job`

**Files:**
- Modify: `backend/job_models.py:18-36` (TranscriptionJob.__init__)
- Modify: `backend/services/transcription.py` (`_update_job` ~lines 554-562)
- Modify: `backend/routes/transcription.py:638-648` (GET `/job/{id}` response)
- Test: `backend/tests/test_orchestrator.py` (created in Task 7) covers phase transitions; this task only proves the field plumbs through

This task is plumbing-only. The actual phase WRITES happen in Tasks 6 (orchestrator) and 7 (route updates). Here we add the storage + surface it via the API.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_orchestrator.py` with this first test (more tests added in Task 7):

```python
"""Sub-plan A unit tests: orchestrator + phase field + Best/Quick dispatch."""

from unittest.mock import MagicMock

import pytest


def test_transcription_job_has_phase_field_defaulting_to_none():
    """TranscriptionJob must expose `phase` so the orchestrator can write it."""
    from job_models import TranscriptionJob
    job = TranscriptionJob("phase-1")
    assert hasattr(job, "phase"), "TranscriptionJob must declare a `phase` attribute"
    assert job.phase is None, "phase defaults to None pre-start"


def test_update_job_accepts_phase_kwarg(monkeypatch):
    """_update_job must accept an optional phase= argument and write it onto the job."""
    from job_models import TranscriptionJob
    from services import transcription

    job = TranscriptionJob("phase-2")
    monkeypatch.setattr(transcription.state, "jobs", MagicMock(update=MagicMock()))
    transcription._update_job(job, phase="diarizing")
    assert job.phase == "diarizing"


def test_update_job_phase_can_be_cleared_back_to_none(monkeypatch):
    """Setting phase=None must be respected (otherwise None is indistinguishable from 'not provided')."""
    from job_models import TranscriptionJob
    from services import transcription

    job = TranscriptionJob("phase-3")
    job.phase = "transcribing"
    monkeypatch.setattr(transcription.state, "jobs", MagicMock(update=MagicMock()))
    # Use a sentinel-distinct call to clear: pass phase=None explicitly.
    transcription._update_job(job, phase=None, _clear_phase=True)
    assert job.phase is None
```

The third test specifies a `_clear_phase=True` opt-in sentinel — None alone can't disambiguate "not passed" from "explicitly cleared". The orchestrator only needs to clear at end-of-pipeline; everywhere else it sets a real phase.

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -15
```
Expected: ALL fail — `AssertionError: TranscriptionJob must declare a 'phase' attribute` for the first; the rest fail because `_update_job` doesn't accept `phase=`.

- [ ] **Step 3: Add the `phase` field to `TranscriptionJob`**

In `backend/job_models.py:18-36`, append to the `__init__` body (after `self.learning_status = None`):

```python
        # Plan 4A: phase pill for the UI's phased progress bar (in-memory only,
        # not persisted to SQL). Values: None | "diarizing" | "transcribing" |
        # "aligning" | "refining" | "learning". None = no active phase.
        self.phase = None
```

- [ ] **Step 4: Extend `_update_job` to accept `phase`**

In `backend/services/transcription.py`, replace the existing `_update_job` (~lines 554-562) with:

```python
_PHASE_UNSET = object()  # sentinel — distinguishes "not provided" from explicit None


def _update_job(job, progress: int = None, message: str = None, status: str = None,
                phase=_PHASE_UNSET, _clear_phase: bool = False):
    """Update job fields and persist to DB so progress survives restarts.

    `phase` uses a sentinel because None has meaning (pre-start / done).
    Pass `_clear_phase=True` together with `phase=None` to explicitly clear.
    """
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.progress_message = message
    if phase is not _PHASE_UNSET:
        # Only assign if the caller actually passed the kwarg.
        if phase is None and not _clear_phase:
            # Defensive: a stray phase=None without _clear_phase is a no-op.
            pass
        else:
            job.phase = phase
    state.jobs.update(job)
```

- [ ] **Step 5: Surface `phase` in the GET /job/{id} response**

In `backend/routes/transcription.py:638-648`, in the `response = {...}` dict inside `get_job_status`, add a `"phase"` entry:

```python
    response = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "progress_message": job.progress_message,
        # Plan 4A: phase pill for phased progress bar
        "phase": getattr(job, "phase", None),
        # B2: surface auto-refine indicators for UI polling (None when not applicable)
        "refinement_status": getattr(job, "refinement_status", None),
        "auto_speaker_matches": getattr(job, "auto_speaker_matches", None),
        "learning_summary": getattr(job, "learning_summary", None),
        "learning_status": getattr(job, "learning_status", None),
    }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -10
```
Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/job_models.py backend/services/transcription.py backend/routes/transcription.py backend/tests/test_orchestrator.py
git commit -m "Plan 4A Task 4: add phase field to TranscriptionJob and surface in GET /job/{id}"
```

---

## Task 4b: Wire `phase="refining"` and `phase="learning"` in refinement.py

**Why:** Spec's Phase Lifecycle table (specs/2026-05-17-davrine-quality-dial-orchestration-design.md lines ~215-224) requires `phase="refining"` when refinement starts and `phase="learning"` when post-refinement learning kicks off, then `phase=None` when learning completes. Task 4 plumbs the FIELD; Task 6 wires the PRE-completion transitions (`diarizing`/`transcribing`/`aligning`) in the orchestrator. But the orchestrator clears phase to None at completion and then submits `_run_refinement_for_job` to the executor — `routes/refinement.py` itself never writes the post-completion phases. Without this task, the UI pill goes Diarizing → Transcribing → Aligning → (gone) and never shows Refining/Learning.

**Files:**
- Modify: `backend/routes/refinement.py:174-266` (`_run_refinement_for_job` — add `phase="refining"` at start)
- Modify: `backend/routes/refinement.py:53-171` (`_run_post_refinement_learning` — set `phase="learning"` at start, clear at end)
- Test: `backend/tests/test_orchestrator.py` (append two phase-transition tests)

This task slots in after Task 4 because it depends on `_update_job(phase=…, _clear_phase=…)` existing. It runs BEFORE Sub-plan B execution (which extends `_run_refinement_for_job` internally to do speaker correction); Sub-plan B's edits live inside the same function but after the phase write, so the two changes compose cleanly.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_orchestrator.py`:

```python
def test_run_refinement_for_job_sets_phase_refining(monkeypatch):
    """_run_refinement_for_job must set job.phase='refining' immediately after picking up the job."""
    from job_models import TranscriptionJob
    from routes import refinement as refmod

    job = TranscriptionJob("phase-ref-1")
    job.status = "completed"
    job.segments = [{"start": 0.0, "end": 1.0, "text": "hi", "speaker": "SPEAKER_00"}]

    fake_store = MagicMock()
    fake_store.get = MagicMock(return_value=job)
    fake_store.update = MagicMock()
    monkeypatch.setattr(refmod.state, "job_store", fake_store)
    monkeypatch.setattr(refmod.state, "jobs", fake_store)

    fake_ref_store = MagicMock()
    monkeypatch.setattr(refmod.state, "refinement_store", fake_ref_store)

    # Force an early return after the phase write — fail at refine() so the
    # finally block runs but we don't need a real RefinementService.
    fake_service = MagicMock()
    fake_service.refine.side_effect = RuntimeError("stop here")
    monkeypatch.setattr(refmod.state, "refinement_service", fake_service)

    # Stub the imports so we don't pull the world in.
    monkeypatch.setattr("services.transcription.load_context_document", lambda *_a, **_k: "")
    monkeypatch.setattr("services.transcription.load_speakers_context", lambda *_a, **_k: "")
    monkeypatch.setattr("services.transcription.merge_context_sources", lambda *_a, **_k: "")
    monkeypatch.setattr("services.glossary.load_global_glossary", lambda: "")
    monkeypatch.setattr("services.glossary.load_global_glossary_terms", lambda: None)

    refmod._run_refinement_for_job("phase-ref-1")

    assert job.phase == "refining", f"expected phase='refining', got {job.phase!r}"


def test_run_post_refinement_learning_sets_then_clears_phase(monkeypatch):
    """_run_post_refinement_learning must set phase='learning' at start and clear (None) at end."""
    from job_models import TranscriptionJob
    from routes import refinement as refmod

    job = TranscriptionJob("phase-learn-1")
    job.segments = [{"start": 0.0, "end": 1.0, "speaker": "Alice"}]
    job.speakers = []

    fake_store = MagicMock()
    fake_store.get = MagicMock(return_value=job)
    fake_store.update = MagicMock()
    monkeypatch.setattr(refmod.state, "jobs", fake_store)

    # Stub all three learning workers to no-op success.
    monkeypatch.setattr("services.learning.update_speaker_embeddings", lambda **_k: 0)
    monkeypatch.setattr("services.learning.extract_insights_auto", lambda **_k: 0)
    monkeypatch.setattr("services.learning.learn_glossary_terms", lambda **_k: 0)

    # Capture phase writes in order.
    phase_writes: list = []
    real_update_job = refmod.state.jobs.update  # MagicMock — track on job

    def track_phase(_job, **kwargs):
        if "phase" in kwargs:
            phase_writes.append(kwargs.get("phase"))
        return real_update_job(_job)

    # Patch _update_job (imported lazily in step 3) to capture phase order.
    from services import transcription as tx
    monkeypatch.setattr(tx, "_update_job", track_phase)

    refmod._run_post_refinement_learning(
        job_id="phase-learn-1", audio_path=None,
        segments=[{"start": 0.0, "end": 1.0, "speaker": "Alice"}],
        analysis={},
    )

    assert phase_writes[0] == "learning", f"first phase write should be 'learning', got {phase_writes!r}"
    assert phase_writes[-1] is None, f"last phase write should clear (None), got {phase_writes!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py::test_run_refinement_for_job_sets_phase_refining tests/test_orchestrator.py::test_run_post_refinement_learning_sets_then_clears_phase -v 2>&1 | tail -15
```
Expected: BOTH fail — phase never gets written.

- [ ] **Step 3: Add `phase="refining"` to `_run_refinement_for_job`**

In `backend/routes/refinement.py:174-266`, inside the `try:` block, immediately after `_set_refinement_status(job, "processing")` (~line 201), add:

```python
        # Plan 4A: phase pill — refinement is now active.
        from services.transcription import _update_job
        _update_job(job, phase="refining")
```

Place this BEFORE the `if job.status != "completed":` guard so even a fast-fail refinement still transitions the UI through the refining pill (Sub-plan B's diarization polish will extend this block; the phase write must happen first).

- [ ] **Step 4: Add `phase="learning"` start + clear in `_run_post_refinement_learning`**

In `backend/routes/refinement.py:53-171`:

**At the start of the function body** (before the `from services import learning` import, ~line 61), after a quick job fetch:

```python
def _run_post_refinement_learning(job_id: str, audio_path: Optional[str],
                                  segments: list, analysis: dict) -> None:
    """B7 orchestrator: ..."""
    # Plan 4A: phase pill — learning is now active.
    from services.transcription import _update_job
    _job = state.jobs.get(job_id)
    if _job is not None:
        _update_job(_job, phase="learning")

    from services import learning
    ...
```

**At the very end of the function** (after the existing `state.jobs.update(job)` call inside the `if job is not None:` block, ~line 172), add:

```python
        # Plan 4A: clear phase — learning workers are done, UI pill disappears.
        _update_job(job, phase=None, _clear_phase=True)
```

Note: the existing block already calls `state.jobs.update(job)`; the new `_update_job(...)` does its own write. That's a duplicate write but harmless — the alternative (interleaving) makes the diff messier than it's worth.

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -15
```
Expected: all 5 tests in `test_orchestrator.py` pass (3 from Task 4 + 2 new).

- [ ] **Step 6: Regression check — refinement-status tests still green**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_refinement.py tests/test_post_refinement_learning.py -v 2>&1 | tail -10
```
Expected: existing tests still pass — phase writes are additive and don't change the refinement_status / learning_status / learning_summary behaviors those tests assert on.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/refinement.py backend/tests/test_orchestrator.py
git commit -m "Plan 4A Task 4b: wire phase=refining and phase=learning in refinement.py"
```

---

## Task 5: Narrow `TranscriptionSettings.engine` and drop `model_size`

**Files:**
- Modify: `backend/job_models.py:385-409` (`TranscriptionSettings`)
- Test: `backend/tests/test_orchestrator.py` (append validation tests)

This is the breaking-change task. Old engine values become invalid. `model_size` field disappears. Tests that construct `TranscriptionSettings(engine="whisper", ...)` will now fail with a pydantic ValidationError — that's Task 10's job to fix. We do this BEFORE Task 6 (`_run_transcription_sync` collapse) so the type narrowing is the contract the router/worker enforce.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_orchestrator.py`:

```python
def test_engine_accepts_auto_best():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings(engine="auto-best")
    assert s.engine == "auto-best"


def test_engine_accepts_auto_quick():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings(engine="auto-quick")
    assert s.engine == "auto-quick"


def test_engine_default_is_auto_best():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings()
    assert s.engine == "auto-best", "default engine must be auto-best"


def test_engine_rejects_legacy_whisper():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="whisper")


def test_engine_rejects_legacy_voxtral_local():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="voxtral-local")


def test_engine_rejects_legacy_voxtral_api():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="voxtral-api")


def test_engine_rejects_legacy_parakeet():
    from job_models import TranscriptionSettings
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TranscriptionSettings(engine="parakeet")


def test_model_size_field_is_gone():
    """TranscriptionSettings no longer has a model_size field.

    Pydantic v2 by default IGNORES extra kwargs, so we assert on the dump
    rather than expecting a ValidationError. (If the field were still
    declared, it'd appear in model_dump().)
    """
    from job_models import TranscriptionSettings
    s = TranscriptionSettings()
    assert "model_size" not in s.model_dump()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -20
```
Expected: 7 of the 8 new tests fail (default is currently `voxtral-local`, model_size still present, no `Literal` constraint yet).

- [ ] **Step 3: Update `TranscriptionSettings`**

In `backend/job_models.py`, change the imports at the top to include `Literal`:

```python
from typing import Optional, List, Literal
```

Then in `TranscriptionSettings` (~line 385), apply these edits:
- DELETE the line `model_size: str = "voxtral-realtime-4b"` (~line 395)
- CHANGE `engine: str = "voxtral-local"` (~line 397) to:
  ```python
  engine: Literal["auto-best", "auto-quick"] = "auto-best"
  ```

The full updated class becomes:

```python
class TranscriptionSettings(BaseModel):
    beam_size: int = 5
    patience: float = 1.0
    best_of: int = 5
    vad_filter: bool = False
    word_timestamps: bool = False
    language: str = "auto"
    enable_diarization: bool = True
    num_speakers: Optional[int] = None
    enable_noise_reduction: bool = False
    translate_to_english: bool = False
    engine: Literal["auto-best", "auto-quick"] = "auto-best"
    context_terms: Optional[List[str]] = None
    context_path: Optional[str] = None
    speaker_ids: Optional[List[str]] = None
    original_filename: Optional[str] = None
    two_pass: bool = False
    output_mode: str = "verbatim"
    auto_refine: Optional[bool] = None
```

- [ ] **Step 4: Run the new tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -20
```
Expected: all orchestrator-suite tests pass.

- [ ] **Step 5: Acknowledge the broader suite will be RED until Task 10**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/ -q 2>&1 | tail -10
```
Expected: a wave of pydantic ValidationError failures from `test_transcription_a1.py`, `test_inline_auto_match.py`, `test_auto_refine_orchestration.py`, plus the integration tests that hit `/transcribe/file` with `engine=whisper`. This is fine and expected — Task 10 migrates them. Document the failure count so you can verify Task 10 brings the suite back to green.

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/job_models.py backend/tests/test_orchestrator.py
git commit -m "Plan 4A Task 5: narrow TranscriptionSettings.engine to Literal auto-best/auto-quick, drop model_size"
```

---

## Task 6: Introduce `backend/services/orchestrator.py`

**Files:**
- Create: `backend/services/orchestrator.py`
- Modify: `backend/tests/test_orchestrator.py` (append dispatch tests)

The orchestrator is a thin coordinator. It does NOT redo the work of `_run_transcription_sync` — it delegates to:
- `services.diarization.run_diarization` (unchanged)
- `services.transcription.transcribe_with_whisper` (Best, callable extracted in Task 2)
- `services.transcription.transcribe_with_parakeet` (Quick, already callable)
- `services.diarization.assign_speakers_to_segments` (Best — A3 word-boundary)
- `services.diarization.assign_speakers_time_proportional` (Quick — A3-light, added in Task 3)
- `routes.refinement._run_refinement_for_job` (unchanged signature; Sub-plan B extends it internally)

The orchestrator OWNS the phase transitions per the Phase Lifecycle table in the spec (lines 215-224).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_orchestrator.py`:

```python
def test_orchestrate_best_dispatches_whisper(tmp_path, monkeypatch):
    """Best mode calls transcribe_with_whisper, not transcribe_with_parakeet."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-best")
    job._retry_of = None
    calls = {"whisper": 0, "parakeet": 0}

    def fake_whisper(*a, **k):
        calls["whisper"] += 1
        return {"segments": [{"start": 0, "end": 1, "text": "hi"}], "text": "hi", "language": "en"}

    def fake_parakeet(*a, **k):
        calls["parakeet"] += 1
        return {"segments": [], "text": "", "language": "en"}

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper", fake_whisper)
    monkeypatch.setattr(orchestrator, "transcribe_with_parakeet", fake_parakeet)
    monkeypatch.setattr(orchestrator, "run_diarization", lambda *a, **k: [])
    monkeypatch.delenv("HF_TOKEN", raising=False)  # no diarization

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    orchestrator.orchestrate_transcription("orch-best", str(audio_path), settings, mode="best")

    assert calls["whisper"] == 1
    assert calls["parakeet"] == 0


def test_orchestrate_quick_dispatches_parakeet(tmp_path, monkeypatch):
    """Quick mode calls transcribe_with_parakeet (multilingual v3), not Whisper."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-quick")
    job._retry_of = None
    calls = {"whisper": 0, "parakeet": 0, "parakeet_key": None}

    def fake_whisper(*a, **k):
        calls["whisper"] += 1
        return {"segments": [], "text": "", "language": "en"}

    def fake_parakeet(audio_path, model_key=None):
        calls["parakeet"] += 1
        calls["parakeet_key"] = model_key
        return {"segments": [{"start": 0, "end": 1, "text": "hi"}], "text": "hi", "language": "multi"}

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "_parakeet_available", True)
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper", fake_whisper)
    monkeypatch.setattr(orchestrator, "transcribe_with_parakeet", fake_parakeet)
    monkeypatch.setattr(orchestrator, "run_diarization", lambda *a, **k: [])
    monkeypatch.delenv("HF_TOKEN", raising=False)

    settings = TranscriptionSettings(engine="auto-quick", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    orchestrator.orchestrate_transcription("orch-quick", str(audio_path), settings, mode="quick")

    assert calls["parakeet"] == 1
    assert calls["whisper"] == 0
    # Multilingual v3 covers EN+FR per the spec.
    assert calls["parakeet_key"] == "parakeet-multi-v3"


def test_orchestrate_emits_phase_transitions(tmp_path, monkeypatch):
    """Best mode writes phases in order: diarizing+transcribing → aligning → None (completed)."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-phases")
    job._retry_of = None
    phase_history = []

    real_update = transcription._update_job
    def tracking_update(j, **kw):
        if "phase" in kw or kw.get("_clear_phase"):
            phase_history.append(kw.get("phase"))
        real_update(j, **kw)

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    monkeypatch.setattr(transcription, "_update_job", tracking_update)
    monkeypatch.setattr(orchestrator, "_update_job", tracking_update)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper",
                        lambda *a, **k: {"segments": [{"start": 0, "end": 1, "text": "hi"}],
                                         "text": "hi", "language": "en"})
    # Return non-empty diarization so the `aligning` branch fires.
    monkeypatch.setattr(orchestrator, "run_diarization",
                        lambda *a, **k: [{"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00"}])
    monkeypatch.setattr(orchestrator, "assign_speakers_to_segments",
                        lambda segs, sp: [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])
    monkeypatch.setattr(orchestrator, "stitch_speaker_turns", lambda segs: segs)
    # B5 auto-match runs only if refinement_available — keep False to skip it here.
    monkeypatch.setenv("HF_TOKEN", "fake")

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=True, enable_noise_reduction=False)
    orchestrator.orchestrate_transcription("orch-phases", str(audio_path), settings, mode="best")

    # Expected order per spec Phase Lifecycle table:
    # diarizing (parallel start) → transcribing (dominant) → aligning → None (completed).
    assert "diarizing" in phase_history
    assert "transcribing" in phase_history
    assert "aligning" in phase_history
    assert phase_history[-1] is None, f"final phase write must clear, got {phase_history}"


def test_orchestrate_best_dispatches_refinement_when_auto_refine_fires(tmp_path, monkeypatch):
    """When _should_auto_refine() returns True and refinement is available,
    Best mode submits _run_refinement_for_job onto the transcription executor."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import orchestrator, transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("orch-refine")
    job._retry_of = None
    submitted = []
    fake_exec = MagicMock(submit=MagicMock(side_effect=lambda *a, **k: submitted.append((a, k))))

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)
    monkeypatch.setattr(orchestrator.state, "transcription_executor", fake_exec, raising=False)
    monkeypatch.setattr(orchestrator, "transcribe_with_whisper",
                        lambda *a, **k: {"segments": [{"start": 0, "end": 1, "text": "hi"}],
                                         "text": "hi", "language": "en"})
    monkeypatch.setattr(orchestrator, "run_diarization", lambda *a, **k: [])
    monkeypatch.delenv("HF_TOKEN", raising=False)

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=False, enable_noise_reduction=False,
                                     speaker_ids=["sp-1"])  # forces auto_refine via None mode
    orchestrator.orchestrate_transcription("orch-refine", str(audio_path), settings, mode="best")

    assert fake_exec.submit.called, "auto-refine must dispatch on the transcription executor"
    args, _kw = submitted[0]
    # args = (_run_refinement_for_job, job_id, speaker_ids, context_path, audio_path)
    assert args[1] == "orch-refine"
    assert args[2] == ["sp-1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -20
```
Expected: 4 new tests fail with `ModuleNotFoundError: No module named 'services.orchestrator'`.

- [ ] **Step 3: Create `backend/services/orchestrator.py`**

```python
"""Backend orchestrator: composes the right model stack per quality mode.

Best mode  → Whisper Large V3 Turbo + pyannote + Sonnet refinement (with
             diarization polish, per Sub-plan B).
Quick mode → Parakeet v3 multilingual + pyannote + Sonnet refinement.

This module is intentionally thin: it owns dispatch + phase transitions, and
delegates work to existing helpers in services.transcription, services.diarization,
and routes.refinement.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional

from services.transcription import (
    transcribe_with_whisper,
    transcribe_with_parakeet,
    _update_job,
    _should_auto_refine,
)
from services.diarization import (
    run_diarization,
    assign_speakers_to_segments,
    assign_speakers_time_proportional,
    stitch_speaker_turns,
)
from services.postprocess import normalize_segments, apply_readable_mode
from services.audio import apply_noise_reduction
import state

logger = logging.getLogger(__name__)

# Phase constants — single source of truth, matches the spec's Phase Lifecycle table.
PHASE_DIARIZING = "diarizing"
PHASE_TRANSCRIBING = "transcribing"
PHASE_ALIGNING = "aligning"
PHASE_REFINING = "refining"
PHASE_LEARNING = "learning"


def orchestrate_transcription(
    job_id: str,
    audio_path: str,
    settings,
    mode: Literal["best", "quick"] = "best",
) -> None:
    """Run the chosen pipeline. Synchronous; called from the thread pool."""
    job = state.jobs.get(job_id)
    if not job:
        logger.warning("orchestrator: job %s missing — bail", job_id)
        return

    try:
        _update_job(job, progress=5, message="Starting transcription...", status="processing")

        # Optional noise reduction (preserved from legacy path).
        if settings.enable_noise_reduction:
            _update_job(job, progress=8, message="Applying noise reduction...")
            from pathlib import Path
            src = Path(audio_path)
            cleaned_audio_path = str(src.with_stem(src.stem + "_cleaned"))
            audio_path = apply_noise_reduction(audio_path, cleaned_audio_path)

        # Spin up diarization concurrently with transcription (Audit #9 pattern preserved).
        speakers = []
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
        diarization_future = None
        diarization_executor = None
        if settings.enable_diarization and hf_token:
            _update_job(
                job,
                progress=10,
                message=(f"Identifying {settings.num_speakers} speakers..."
                         if settings.num_speakers else "Identifying speakers..."),
                phase=PHASE_DIARIZING,
            )
            diarization_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="diarize")
            diarization_future = diarization_executor.submit(
                run_diarization, audio_path, settings.num_speakers
            )

        # Transcribe (Best→Whisper Turbo, Quick→Parakeet multilingual v3).
        _update_job(
            job,
            progress=20,
            message=("Transcribing with MLX-Whisper (GPU-accelerated)..." if mode == "best"
                     else "Transcribing with Parakeet MLX (multilingual v3)..."),
            phase=PHASE_TRANSCRIBING,
        )
        if mode == "best":
            result = transcribe_with_whisper(audio_path, settings, job=job)
        else:
            # Quick: always multilingual v3 (covers EN+FR per spec).
            result = transcribe_with_parakeet(audio_path, model_key="parakeet-multi-v3")

        job.language = result.get("language", "unknown")
        job.language_probability = 0.99
        transcription_segments = result.get("segments", [])
        full_text = result.get("text", "")

        # Join diarization (never let a diarization failure kill transcription).
        if diarization_future is not None:
            try:
                speakers = diarization_future.result() or []
                job.speakers = speakers
            except Exception as e:
                logger.warning("Diarization failed, continuing without speakers: %s", e)
                speakers = []
            finally:
                if diarization_executor is not None:
                    diarization_executor.shutdown(wait=False)

        # Align speakers onto segments. Best uses A3 word-boundary; Quick uses A3-light.
        if speakers:
            _update_job(job, progress=65, message="Aligning speakers to segments...",
                        phase=PHASE_ALIGNING)
            if mode == "best":
                transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)
            else:
                transcription_segments = assign_speakers_time_proportional(
                    transcription_segments, speakers
                )
            transcription_segments = stitch_speaker_turns(transcription_segments)

        # B5 inline auto-match — overlay registered speaker names (~1-5s).
        # Same scope logic as the post-job /speakers/auto-match route.
        if speakers and state.refinement_available:
            _update_job(job, progress=68, message="Matching voices to registered speakers...")
            try:
                from routes.transcription import _resolve_match_scope
                restrict_ids, prefer_ids, scope_mode = _resolve_match_scope({
                    "speaker_ids": settings.speaker_ids,
                    "num_speakers": settings.num_speakers,
                })
                embedding_service = state.get_speaker_embedding_service()
                auto_matches = embedding_service.auto_identify_speakers(
                    audio_path=audio_path,
                    speaker_turns=speakers,
                    job_id=job_id,
                    restrict_to_ids=restrict_ids,
                    prefer_ids=prefer_ids,
                )
                job.auto_speaker_matches = auto_matches
                for seg in transcription_segments:
                    lbl = seg.get("speaker", "")
                    m = auto_matches.get(lbl)
                    if m and m.get("matched"):
                        seg["speaker"] = m["name"]
                for turn in (job.speakers or []):
                    lbl = turn.get("speaker", "")
                    m = auto_matches.get(lbl)
                    if m and m.get("matched"):
                        turn["speaker"] = m["name"]
                logger.info("B5 auto-match: scope=%s, matched %d/%d",
                            scope_mode, sum(1 for m in auto_matches.values() if m.get("matched")),
                            len(auto_matches))
            except Exception:
                logger.exception("B5 auto-match failed for %s; keeping SPEAKER_XX", job_id)

        # A1: strip internal `words` from emitted segments if user opted out.
        if not settings.word_timestamps:
            for seg in transcription_segments:
                seg.pop("words", None)

        _update_job(job, progress=70, message="Processing segments...")
        normalize_segments(transcription_segments)
        if settings.output_mode == "readable":
            apply_readable_mode(transcription_segments)
            full_text = " ".join(
                seg["text"].strip() for seg in transcription_segments if seg.get("text")
            )

        _update_job(job, progress=90, message="Finalizing...")
        job.segments = transcription_segments
        job.result = full_text

        # Clear phase as we transition to completed (verbatim ready).
        _update_job(job, progress=100, message="Complete!", status="completed",
                    phase=None, _clear_phase=True)

        # Auto-refine dispatch (Best mode benefits most; Quick mode also runs
        # so diarization polish + learning fire). Same dispatch as the legacy
        # path — _run_refinement_for_job already chains learning workers.
        if _should_auto_refine(settings) and state.refinement_available:
            try:
                from routes.refinement import _run_refinement_for_job
                job.refinement_status = "pending"
                state.jobs.update(job)
                state.refinement_store.create(job_id)
                job._defer_audio_cleanup = True
                state.transcription_executor.submit(
                    _run_refinement_for_job,
                    job_id,
                    settings.speaker_ids,
                    settings.context_path,
                    audio_path,
                )
                logger.info("Orchestrator: auto-refine dispatched for %s (mode=%s)", job_id, mode)
            except Exception:
                logger.exception("Orchestrator: auto-refine dispatch failed for %s", job_id)
                try:
                    job.refinement_status = "failed"
                    state.jobs.update(job)
                    state.refinement_store.update_status(job_id, "failed", "dispatch failed")
                except Exception:
                    logger.debug("Rollback after dispatch failure failed for %s",
                                 job_id, exc_info=True)
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        state.jobs.update(job)
        logger.exception("Orchestrator failed for job %s", job_id)
```

- [ ] **Step 4: Run the orchestrator tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -25
```
Expected: all orchestrator tests pass.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "Plan 4A Task 6: introduce backend/services/orchestrator.py with Best/Quick dispatch + phase transitions"
```

---

## Task 7: Collapse `_run_transcription_sync` to route via orchestrator

**Files:**
- Modify: `backend/services/transcription.py` (`_run_transcription_sync` ~lines 565-932 collapses to a thin router)

`_run_transcription_sync` becomes a wrapper. All legacy direct-engine branches (Voxtral Cloud, Voxtral Local, Parakeet-direct, Whisper-direct) are removed AT THEIR CALL SITES. The helper functions `transcribe_with_voxtral`, `transcribe_with_voxtral_local`, `transcribe_with_parakeet` STAY IN PLACE — Sub-plan D removes them along with the `voxtral_service` module. The finally-block (tmp-dir cleanup, retry guard) stays.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_orchestrator.py`:

```python
def test_run_transcription_sync_routes_auto_best_to_orchestrator(tmp_path, monkeypatch):
    """_run_transcription_sync with engine=auto-best calls orchestrate_transcription(mode='best')."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription, orchestrator

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    calls = []
    monkeypatch.setattr(orchestrator, "orchestrate_transcription",
                        lambda jid, ap, s, mode: calls.append((jid, mode)))
    # Also patch the symbol that transcription.py imports.
    monkeypatch.setattr(transcription, "orchestrate_transcription",
                        lambda jid, ap, s, mode: calls.append((jid, mode)), raising=False)

    job = TranscriptionJob("router-1")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))

    settings = TranscriptionSettings(engine="auto-best", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    transcription._run_transcription_sync("router-1", str(audio_path), settings)
    assert ("router-1", "best") in calls


def test_run_transcription_sync_routes_auto_quick_to_orchestrator(tmp_path, monkeypatch):
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription, orchestrator

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    calls = []
    monkeypatch.setattr(transcription, "orchestrate_transcription",
                        lambda jid, ap, s, mode: calls.append((jid, mode)), raising=False)

    job = TranscriptionJob("router-2")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))

    settings = TranscriptionSettings(engine="auto-quick", language="en",
                                     enable_diarization=False, enable_noise_reduction=False)
    transcription._run_transcription_sync("router-2", str(audio_path), settings)
    assert ("router-2", "quick") in calls
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v -k "_routes_" 2>&1 | tail -15
```
Expected: fail — `_run_transcription_sync` still has the legacy branching.

- [ ] **Step 3: Replace `_run_transcription_sync` body**

In `backend/services/transcription.py`, find `_run_transcription_sync` (~line 565). Replace the ENTIRE function body (lines ~565 through ~932) with the thin router below. The `finally:` block stays so the temp-dir cleanup contract holds.

Also add an import near the top of the file (alongside the other `services.*` imports):

```python
# Late import inside the function avoids the circular dependency (orchestrator
# imports from this module). Define a local symbol used by tests for monkeypatching.
```

Replace `_run_transcription_sync`:

```python
def _run_transcription_sync(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Synchronous transcription worker — runs in the thread pool.

    Routes to the orchestrator based on settings.engine. All quality-mode
    composition lives in services.orchestrator; this function is now a
    routing shim plus the tmp-audio cleanup guard.
    """
    # Local import — services.orchestrator imports from this module, so a
    # top-level import would be circular at module load time.
    from services.orchestrator import orchestrate_transcription

    job = state.jobs.get(job_id)
    if not job:
        return

    try:
        if settings.engine == "auto-best":
            orchestrate_transcription(job_id, audio_path, settings, mode="best")
        elif settings.engine == "auto-quick":
            orchestrate_transcription(job_id, audio_path, settings, mode="quick")
        else:
            # Pydantic Literal should have caught this upstream, but defend
            # in depth for any code path that bypasses validation.
            job.status = "failed"
            job.error = (
                f"Unknown engine: {settings.engine!r}. "
                f"Use 'auto-best' or 'auto-quick'."
            )
            state.jobs.update(job)
            return
    finally:
        # Audit #16: retries re-use the same file_path. Don't rmtree if this
        # job was created from a retry — the parent dir is still wanted by
        # any subsequent retry attempt.
        retry_of = getattr(job, "_retry_of", None) if job is not None else None
        if retry_of:
            return
        # B7: if auto-refine was dispatched, the learning workers need the
        # audio. _run_refinement_for_job's finally block will call
        # _cleanup_deferred_audio once refinement + learning (or any failure
        # path) completes.
        if getattr(job, "_defer_audio_cleanup", False):
            return
        try:
            parent_dir = os.path.dirname(audio_path)
            if parent_dir and os.path.isdir(parent_dir) and parent_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(parent_dir, ignore_errors=True)
            elif os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception:
            pass
```

For the test to be able to monkeypatch `transcription.orchestrate_transcription`, also expose the symbol at module scope after the import block (just after line 22 `logger = logging.getLogger(__name__)`):

```python
# Plan 4A: forward-declared for monkeypatching in tests. The real import
# happens lazily inside _run_transcription_sync to avoid the circular load
# (services.orchestrator imports from this module).
orchestrate_transcription = None  # type: ignore
```

And in the new `_run_transcription_sync`, do:

```python
        from services.orchestrator import orchestrate_transcription as _orchestrate
        # Allow tests to monkeypatch the module-level name.
        _dispatch = orchestrate_transcription or _orchestrate
```

Then call `_dispatch(...)` instead of `orchestrate_transcription(...)`. This gives tests a clean monkeypatch surface without changing the production path.

- [ ] **Step 4: Run the routing tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_orchestrator.py -v 2>&1 | tail -20
```
Expected: all orchestrator tests pass.

- [ ] **Step 5: Acknowledge the rest of the suite is still RED**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/ -q 2>&1 | tail -5
```
Expected: same wave of pydantic ValidationErrors from Task 5 — Task 10 fixes them.

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/transcription.py backend/tests/test_orchestrator.py
git commit -m "Plan 4A Task 7: collapse _run_transcription_sync to route via orchestrator (Best/Quick)"
```

---

## Task 8: Update `backend/routes/transcription.py` query defaults + engine validation

**Files:**
- Modify: `backend/routes/transcription.py:113, 117, 127-148, 248, 253, 270-291, 424, 428, 451-466` (three endpoints: `/transcribe/file`, `/transcribe/youtube`, `/transcribe/batch`)

The route layer currently defaults `engine="voxtral-local"` and `model_size="voxtral-realtime-4b"` and validates against `whisper / voxtral-local / voxtral-api`. We change defaults to `engine="auto-best"`, delete the `model_size` query param entirely, and replace engine validation with a clean two-value Literal check that hard-rejects everything else with 400.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_file_validation.py`:

```python
@pytest.mark.asyncio
async def test_upload_default_engine_is_auto_best(client, tmp_audio):
    """Without specifying engine, the route accepts the upload with auto-best."""
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    # 200 if engines wired, 503 if model not loaded — either proves no 400.
    assert resp.status_code in (200, 503), f"unexpected {resp.status_code}: {resp.text}"


@pytest.mark.asyncio
async def test_upload_rejects_legacy_engine_whisper(client, tmp_audio):
    """Legacy engine values must be rejected with 400."""
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=whisper",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert resp.status_code == 400
    assert "no longer supported" in resp.json()["detail"].lower() or \
           "auto-best" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_legacy_engine_voxtral_local(client, tmp_audio):
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=voxtral-local",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_accepts_engine_auto_quick(client, tmp_audio):
    with open(tmp_audio, "rb") as f:
        resp = await client.post(
            "/transcribe/file?language=auto&engine=auto-quick",
            files={"file": ("test.wav", f, "audio/wav")},
        )
    assert resp.status_code in (200, 503)
```

Also EDIT the existing `test_invalid_engine_rejected` (lines 57-65) so it doesn't conflict — the assertion message changes:

```python
@pytest.mark.asyncio
async def test_invalid_engine_rejected(client):
    """Request with invalid engine name should return 400."""
    fake = io.BytesIO(b"fake data")
    resp = await client.post(
        "/transcribe/file?language=auto&engine=invalid_engine",
        files={"file": ("test.wav", fake, "audio/wav")},
    )
    assert resp.status_code == 400
    body = resp.json()["detail"].lower()
    assert "auto-best" in body or "no longer supported" in body or "invalid engine" in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_file_validation.py -v 2>&1 | tail -20
```
Expected: new tests fail because the route still rejects `auto-best` / `auto-quick` and still defaults to `voxtral-local`.

- [ ] **Step 3: Add a shared validation helper at the top of `routes/transcription.py`**

Just after the `router = APIRouter()` line (~line 36), add:

```python
# Plan 4A: accepted engine values (mirror of TranscriptionSettings.engine Literal).
_VALID_ENGINES = frozenset({"auto-best", "auto-quick"})


def _validate_engine_or_400(engine: str) -> None:
    """Hard-reject legacy engine values. The frontend was updated in lockstep
    (Sub-plan C); any old client gets a clear 400 telling it what to send."""
    if engine in _VALID_ENGINES:
        return
    raise HTTPException(
        status_code=400,
        detail=(
            f"Engine {engine!r} is no longer supported. "
            f"Use 'auto-best' or 'auto-quick'."
        ),
    )
```

- [ ] **Step 4: Rewrite the three route signatures + validation blocks**

For each of the three POST routes (`/transcribe/file`, `/transcribe/youtube`, `/transcribe/batch`), apply the same set of edits:

1. **Delete the `model_size` query param** (lines ~113, ~248, ~424).
2. **Delete the `speed_priority` query param** (lines ~116, ~252, ~427).
3. **Change `engine` default to `"auto-best"`** and tighten the description (lines ~117, ~253, ~428):
   ```python
   engine: str = Query("auto-best", description="Quality mode: 'auto-best' or 'auto-quick'"),
   ```
4. **Replace the engine validation block** (lines ~127-148, ~270-297, ~439-466) with the single helper call:
   ```python
   _validate_engine_or_400(engine)
   ```
5. **Delete the `effective_model = ...` block and any `if engine == "voxtral-local": ... if model_size not in VOXTRAL_LOCAL_MODELS: ...` blocks.** These are no longer relevant — the orchestrator picks the model.
6. **Update the `TranscriptionSettings(...)` construction** to drop `model_size=...`, `two_pass=...`, `speed_priority=...` (`two_pass` field still exists in pydantic but is not user-controllable; let it default). Keep `engine=engine`.
7. **Update the return dict** at the end of `/transcribe/file`: change `return {"job_id": job_id, "status": "processing", "model": effective_model, "engine": engine}` to:
   ```python
   return {"job_id": job_id, "status": "processing", "engine": engine}
   ```
   Same shape change for `/transcribe/youtube`.

Concretely for `/transcribe/file` (lines ~105-242), the new signature head looks like:

```python
@router.post("/transcribe/file")
async def transcribe_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Query("auto", description="Language code: en, fr, or auto"),
    enable_diarization: bool = Query(True, description="Enable speaker identification"),
    num_speakers: Optional[int] = Query(None, description="Expected number of speakers (None = auto-detect)"),
    enable_noise_reduction: bool = Query(False, description="Apply noise reduction before transcription"),
    word_timestamps: bool = Query(False, description="Enable word-level timestamps"),
    translate_to_english: bool = Query(False, description="Translate output to English"),
    engine: str = Query("auto-best", description="Quality mode: 'auto-best' or 'auto-quick'"),
    context_terms: Optional[str] = Query(None, description="Comma-separated context terms (advisory)"),
    context_path: Optional[str] = Query(None, description="Path under CONTEXTS_DIR to a .md context document"),
    speaker_ids: Optional[str] = Query(None, description="Comma-separated speaker UUIDs"),
    output_mode: str = Query("verbatim", description="Output mode: verbatim or readable"),
):
    """Upload and transcribe an audio/video file with speaker diarization."""
    if output_mode not in ("verbatim", "readable"):
        raise HTTPException(status_code=400, detail="Invalid output_mode. Use: verbatim, readable")

    _validate_engine_or_400(engine)

    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language. Use: {list(SUPPORTED_LANGUAGES.keys())}")
    # ... rest of the function (file handling, settings construction, etc.) unchanged
    # except for the TranscriptionSettings() block which drops model_size/two_pass.
```

Inside the body, the `TranscriptionSettings(...)` block becomes:

```python
        settings = TranscriptionSettings(
            vad_filter=False,
            word_timestamps=word_timestamps,
            language=language,
            enable_diarization=enable_diarization,
            num_speakers=num_speakers,
            enable_noise_reduction=enable_noise_reduction,
            translate_to_english=translate_to_english,
            engine=engine,
            context_terms=parsed_context_terms,
            context_path=context_path,
            speaker_ids=[s for s in (speaker_ids or "").split(",") if s.strip()] or None,
            original_filename=_orig_filename,
            output_mode=output_mode,
        )
```

Apply equivalent edits to `/transcribe/youtube` (~lines 244-414) and `/transcribe/batch` (~lines 417-555). Drop the imports `VOXTRAL_LOCAL_MODELS, VOXTRAL_LOCAL_LANGUAGES` from line 22 and `PARAKEET_MODELS` from the `_WHISPER_ENGINE_MODEL_KEYS` frozenset above (delete that frozenset entirely — no longer referenced). Drop the unused `select_optimal_model, is_parakeet_key` imports from line 30 (also no longer referenced after this task).

- [ ] **Step 5: Run the file-validation tests**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_file_validation.py -v 2>&1 | tail -20
```
Expected: all 6 tests pass (the 2 pre-existing + the 4 new).

- [ ] **Step 6: Smoke the YouTube + batch routes don't 500 on import**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -c "from main import app; print('routes ok')" 2>&1 | tail -5
```
Expected: prints `routes ok`. If you get an ImportError about `VOXTRAL_LOCAL_*` or `select_optimal_model`, you missed an import — find the leftover reference and remove it.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/transcription.py backend/tests/test_file_validation.py
git commit -m "Plan 4A Task 8: narrow /transcribe/{file,youtube,batch} engine to auto-best/auto-quick with 400 on legacy values"
```

---

## Task 9: Update `watcher/config.py` (CRITICAL — JPR watcher migration)

**Files:**
- Modify: `watcher/config.py:23-32` (`TRANSCRIPTION_SETTINGS`)

The launchd-managed `com.whisper.jpr-watcher` daemon ships every JPR recording to the backend with the dict in `TRANSCRIPTION_SETTINGS`. The moment Task 8 lands, the watcher will 400 every submission because the backend rejects `engine="whisper"`. This task closes that gap.

- [ ] **Step 1: Write a smoke check (no failing test — config-only file)**

Run:
```bash
cat ~/Development/apps/whisper-transcription-app/watcher/config.py | grep -n "engine\|model_size"
```
Expected: shows `model_size: "large-v3-turbo"` (line ~27) and `engine: "whisper"` (line ~30). Both will be edited.

- [ ] **Step 2: Edit `watcher/config.py`**

Replace the `TRANSCRIPTION_SETTINGS` dict (~lines 23-32) with:

```python
# Transcription settings — sent with every JPR submission.
# Plan 4A: orchestrator-mode dispatch. Best mode uses Whisper Large V3 Turbo
# under the hood (per the orchestrator), which is what we want for long JPR
# recordings (better diarization, A1/A2/A3 wiring, refinement polish).
TRANSCRIPTION_SETTINGS = {
    "language": "auto",
    "enable_diarization": True,
    "enable_noise_reduction": False,
    "word_timestamps": False,
    "translate_to_english": False,
    "engine": "auto-best",
    "output_mode": "readable",
}
```

Specifically removed: `"model_size": "large-v3-turbo"` (line 27). Changed: `"engine": "whisper"` → `"engine": "auto-best"`.

- [ ] **Step 3: Verify the watcher's submission code doesn't reference model_size**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && grep -rn "model_size\|VOXTRAL_LOCAL_MODELS\|engine.*whisper" watcher/ 2>&1 | head -10
```
Expected: no hits for `model_size` after the config edit. If `watcher/submit.py` or similar still constructs a query string with `model_size=`, edit it out — the backend no longer accepts that param.

- [ ] **Step 4: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add watcher/config.py
git commit -m "Plan 4A Task 9: migrate JPR watcher to engine=auto-best, drop model_size (lockstep with backend cut-over)"
```

---

## Task 10: Migrate test fixtures across the suite

**Files:**
- Modify: `backend/tests/test_transcription_a1.py` (4 tests at lines ~20, ~69, ~115, ~157)
- Modify: `backend/tests/test_inline_auto_match.py` (2 tests at lines 48, 113)
- Modify: `backend/tests/test_auto_refine_orchestration.py` (3 tests at lines 189, 227, 263)
- Modify: `backend/tests/test_diarization_a3.py` (docstring note only — the file's helper signature doesn't depend on engine)
- Modify: `backend/tests/test_file_validation.py` (3 pre-existing tests at lines ~19, ~33, ~47 send `?engine=whisper` in URL — strip it; Task 8 already migrated `test_invalid_engine_rejected`)

These tests construct `TranscriptionSettings(engine="whisper", model_size="...", ...)`. Both the `engine="whisper"` and the `model_size=` kwargs are now rejected (the former by Literal, the latter is silently ignored as an extra field in pydantic v2 — but it's vestigial so we drop it for cleanliness). With these migrations, the test suite returns to GREEN.

- [ ] **Step 1: Read the failure list**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/ -q 2>&1 | grep "FAILED\|ValidationError" | head -20
```
Expected: a list of ValidationError failures grouped by file. Verify the failing files match the list above.

- [ ] **Step 2: Migrate `test_transcription_a1.py`**

For each of the 4 tests, change the `TranscriptionSettings(...)` constructor:
- `engine="whisper"` → `engine="auto-best"`
- Drop the `model_size="large-v3-turbo"` kwarg entirely.

E.g. `test_whisper_called_with_a1_kwargs` (lines 20-27):

```python
    settings = TranscriptionSettings(
        language="en",
        word_timestamps=False,
        enable_diarization=False,
        enable_noise_reduction=False,
        engine="auto-best",
    )
```

Apply identically to `test_emitted_segments_strip_words_when_user_opted_out` (~line 69), `test_emitted_segments_keep_words_when_user_opted_in` (~line 115), and `test_vad_trim_restores_segment_timestamps` (~line 157).

Also: these tests `patch("mlx_whisper.transcribe", ...)`. After Task 7, `_run_transcription_sync` routes through the orchestrator. The orchestrator imports `transcribe_with_whisper` from `services.transcription` — which still calls `mlx_whisper.transcribe`. The patches work as-is because the patch hits the underlying library, not the helper. Verify by running the tests.

Additionally, `test_transcribe_with_whisper_is_callable_and_returns_result_dict` from Task 2 also uses `engine="whisper"` and `model_size="large-v3-turbo"`. Update it the same way: `engine="auto-best"`, drop `model_size`.

- [ ] **Step 3: Migrate `test_inline_auto_match.py`**

Line 48 + line 113: same edit. `engine="whisper"` → `engine="auto-best"`. No `model_size` to drop (these tests don't set it).

- [ ] **Step 4: Migrate `test_auto_refine_orchestration.py`**

Lines 189, 227, 263: same edit. `engine="whisper"` → `engine="auto-best"`.

NOTE: these tests assert `submitted[0][0][1] == "job-A"` (the job_id arg to `_run_refinement_for_job`). After Task 7, the orchestrator is the dispatcher. The submit signature is `_run_refinement_for_job, job_id, speaker_ids, context_path, audio_path` — same arg order. The tests' assertions remain valid.

- [ ] **Step 5: Migrate `test_diarization_a3.py`**

This file does NOT construct `TranscriptionSettings`. The unit tests call `assign_speakers_to_segments` directly. Update only `test_no_words_falls_back_to_midpoint` (lines 109-119) to add a one-line docstring note referencing the new helper:

```python
def test_no_words_falls_back_to_midpoint():
    """Segment without word-level timestamps uses midpoint heuristic.

    Note: post-Plan-4A, Quick mode uses assign_speakers_time_proportional
    instead of this midpoint path. The midpoint fallback inside
    assign_speakers_to_segments stays for safety (segments with no words
    that arrive via Best mode, e.g. silence-only segments)."""
    ...
```

- [ ] **Step 5b: Migrate the 3 pre-existing `test_file_validation.py` URL fixtures**

After Task 8 lands, the route handler validates `engine` BEFORE running file-extension / magic-byte checks. Three pre-existing tests in `backend/tests/test_file_validation.py` send `?engine=whisper` in their URLs and will start 400'ing for the wrong reason (engine rejection instead of extension/magic-byte rejection). Two of them assert `status_code in (400, 503)` so they "pass" but the body assertion (`"Unsupported file type" in resp.json()["detail"]`) fails; the third asserts `status_code in (200, 503)` and fails outright.

Open `backend/tests/test_file_validation.py`. The three tests are around lines 19, 33, 47. In each, remove the `engine=whisper` from the URL query string (do not replace it — `engine` is no longer needed because `auto-best` is the route default after Task 8):

- `test_upload_unsupported_extension` (~line 19): `/transcribe/file?language=auto&engine=whisper` → `/transcribe/file?language=auto`
- `test_upload_wrong_magic_bytes` (~line 33): same edit
- `test_upload_valid_wav_accepted` (~line 47): same edit

Sanity-check after editing:

```bash
grep -n "engine=whisper" backend/tests/test_file_validation.py
```

Expected: empty (no hits). The `test_invalid_engine_rejected` test that Task 8 added uses `engine=voxtral-local` to assert the 400, so that one stays.

- [ ] **Step 6: Run the full suite — should be GREEN**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/ -q 2>&1 | tail -10
```
Expected: pass count matches baseline from Task 1 Step 2 PLUS the new orchestrator/time-proportional tests added in this sub-plan. No ValidationError, no AttributeError.

If anything still fails, investigate. Common culprits:
- A test that hits `/transcribe/youtube` or `/transcribe/batch` with `engine=whisper` in the query string — update the query.
- A test that constructs `TranscriptionSettings` via `**kwargs` from a dict literal with `"engine": "whisper"` — grep for `'"engine":` and `engine =` in `tests/`.

- [ ] **Step 7: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/tests/test_transcription_a1.py backend/tests/test_inline_auto_match.py backend/tests/test_auto_refine_orchestration.py backend/tests/test_diarization_a3.py backend/tests/test_file_validation.py
git commit -m "Plan 4A Task 10: migrate test fixtures to engine=auto-best, drop model_size kwargs"
```

---

## Task 11: End-to-end manual smoke (Pascal Weber audio or equivalent)

**Files:**
- None (manual validation; backend restart required)

This task validates the full Best-mode pipeline end-to-end. Only run AFTER Sub-plan C (frontend) has landed — the UI sends `engine=auto-best` from the Quality dial. The JPR watcher should also be restarted to pick up the new config.

- [ ] **Step 1: Restart backend + watcher daemons**

Run:
```bash
launchctl kickstart -k gui/$(id -u)/com.whisper.backend
launchctl kickstart -k gui/$(id -u)/com.whisper.jpr-watcher
sleep 5
tail -20 ~/.whisper-backend.log ~/.jpr_watcher.log
```
Expected: backend starts cleanly, watcher logs "starting" without import errors.

- [ ] **Step 2: Submit a small recording via the UI (Best mode)**

Open `http://localhost:3000`, drop a short test recording (30-90s with 2 speakers), Quality dial = Best, click Transcribe.

- [ ] **Step 3: Watch the phase pill in the UI**

Expected transitions in the progress bar pill (frontend behavior shipped by Sub-plan C):
- `Diarizing` (first ~5s)
- `Transcribing` (dominant phase while Whisper runs)
- `Aligning` (brief, post-transcribe speaker assignment)
- Pill disappears when status flips to Completed → verbatim transcript visible
- `Refining` (Sonnet runs, ~30-90s)
- `Learning` (B7 workers run)
- Pill clears; Refined badge appears

- [ ] **Step 4: Verify diarization clean boundaries**

Open the refined transcript. Speaker changes should land on sentence boundaries (Sub-plan B's polish). No mid-word speaker flips. Both speakers should be named correctly if registered, SPEAKER_00/01 otherwise.

- [ ] **Step 5: Submit a Quick-mode recording**

Same recording, Quality dial = Quick. Expected: verbatim transcript appears within ~30-60s. Refined transcript appears 60-120s later. Speakers are time-proportionally split (rougher boundaries than Best, but Sonnet polish should still clean them).

- [ ] **Step 6: Verify a JPR recording flows through the watcher**

Record a 10-15s clip on the iPhone Just Press Record app. Wait for iCloud sync (~30s on Wi-Fi). The watcher should pick it up and submit with `engine=auto-best`. Check `~/.jpr_watcher.log` — no 400 errors. The new recording should appear in `/jpr/recordings` as processing → completed.

- [ ] **Step 7: Verify the legacy 400 path is alive**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST 'http://localhost:8000/transcribe/file?language=auto&engine=whisper' -F file=@/tmp/silence.wav 2>&1 | head -2
```
Expected: `400`. Body should mention "no longer supported" / "auto-best".

- [ ] **Step 8: No commit needed (manual validation only)**

If everything passes, Sub-plan A is shippable. Coordinate with Sub-plan C deploy. Sub-plan D follows once both are stable.

---

## Self-Review (done by the planner, not the engineer)

Spec coverage:
- "Backend Orchestrator" (spec line 143) → Tasks 2, 3, 6, 7
- "Phased Progress Bar" (spec line 200) → Tasks 4, 4b, 6 (phase field + refinement/learning phase writes + orchestrator pre-completion writes)
- Phase Lifecycle table (spec line 215) → Tasks 4b, 6 (pre-completion writes in orchestrator; post-completion `refining`/`learning` writes in refinement.py; verified by `test_orchestrate_emits_phase_transitions` + `test_run_refinement_for_job_sets_phase_refining` + `test_run_post_refinement_learning_sets_then_clears_phase`)
- "Migration & Removal (no fallback)" backend half (spec line 232) → Tasks 5, 7, 8 (Sub-plan D handles the dead-function sweep)
- Sub-plan A enumeration (spec line 366):
  1. extract `transcribe_with_whisper` → Task 2 ✓
  2. orchestrator.py → Task 6 ✓
  3. `assign_speakers_time_proportional` → Task 3 ✓
  4. `phase` field + `_update_job` + GET surface → Task 4 ✓
  5. narrow `engine` Literal + drop `model_size` → Task 5 ✓
  6. `_run_transcription_sync` → orchestrator router → Task 7 ✓
  7. query-param defaults + validation → Task 8 ✓
  8. test fixture migration → Task 10 ✓
  9. `watcher/config.py` → Task 9 ✓

Counts: 12 tasks (Tasks 1 + 2 + 3 + 4 + 4b + 5 + 6 + 7 + 8 + 9 + 10 + 11; Tasks 1 and 11 are the bookend baseline/smoke tasks; Task 4b was added in response to reviewer feedback to wire phase=refining/learning into refinement.py — the spec's Phase Lifecycle table mandates these transitions but Sub-plan A's pre-fix tasks only wired the pre-completion phases inside the orchestrator).

Type consistency check:
- `assign_speakers_time_proportional(segments, speaker_turns)` — used identically in Task 6 (orchestrator) and Task 3 (test fixtures) ✓
- `transcribe_with_whisper(audio_path, settings, job=None)` — same signature in Task 2 (definition), Task 6 (orchestrator call), Task 7 (router) ✓
- `_update_job(..., phase=..., _clear_phase=...)` — same signature in Task 4 (definition) and Task 6 (orchestrator calls) ✓
- `_run_refinement_for_job(job_id, speaker_ids, context_path, audio_path)` — preserved; matches existing `routes/refinement.py:174` signature ✓
- Phase constant strings match the spec's Phase Lifecycle table verbatim ✓

Placeholder scan: clean — every step has concrete code or commands. No TBD, no "implement later".
