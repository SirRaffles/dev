# Davrine Transcription — Pipeline Quality Fixes (Approach A)

**Status**: Draft for implementation
**Date**: 2026-05-15
**Scope**: Backend transcription pipeline only — no UI, no model swap, no refinement changes

## Context

Comparative evaluation on a real call (Pascal Weber / Manukai, 35 min, FR/EN code-switching, two speakers) showed Davrine producing materially worse output than Turboscribe (cloud Whisper-based) on:
- Speaker attribution (multi-speaker text glued under a single label)
- Language detection (first segment transcribed as Arabic)
- Hallucinations on proper nouns ("Le Price Asset Management" for "Enterprise Asset Management")
- Long, badly-segmented blocks

Root-cause analysis of `backend/services/transcription.py` and `backend/services/diarization.py` identified four mechanical issues, all fixable without changing models or adding services:

1. `condition_on_previous_text=True` propagates Whisper's own errors as context for subsequent chunks
2. No `temperature` fallback + no `logprob_threshold` → low-confidence segments never get retried at higher entropy, locking in hallucinations
3. `assign_speakers_to_segments` uses Whisper-segment midpoint to pick one speaker — when a Whisper segment spans multiple speaker turns, only the dominant speaker is credited
4. `language="auto"` runs Whisper's language detector on the first 30 s of audio, which on phone calls contains jingles/silence/background — yields wrong-language openings

This spec addresses (1)-(4) as three sub-changes (A1, A2, A3). Out of scope: refinement LLM improvements, persistent glossary, auto speaker-embedding matching, model swap — these are tracked separately as Approach B' (improve existing refinement/context features) and Approach C (Voxtral 4B evaluation).

## Goals

- On the Pascal Weber sample, re-run produces:
  - No non-target-language opening segment
  - ≥ 95 % of words attributed to the correct speaker
  - Visibly fewer fabricated phrases (manual diff vs. current output)
- No regression on existing test fixtures (English-only single-speaker samples)
- No new external services, no new heavy dependencies (silero-vad is one .py file, MIT, ~2 MB)

## Non-Goals

- Improving accuracy on proper nouns / domain terms (addressed by B', requires refinement changes)
- UI changes to surface new settings (everything ships with sensible defaults; advanced settings remain hidden)
- Touching Voxtral local or Parakeet code paths (A1's params are Whisper-specific)
- Tuning pyannote itself or swapping the diarization model — A3 only changes how diarization output is *applied* to Whisper segments
- Reducing run-time (acceptable to slow down 5-15 % on clean audio in exchange for quality)

## Design

### A1 — Whisper decoding parameter fixes

**File**: `backend/services/transcription.py:667-676`

**Change**: replace the current `mlx_whisper.transcribe()` kwargs with:

```python
result = mlx_whisper.transcribe(
    audio_path,
    path_or_hf_repo=model_path,
    language=language,
    task="translate" if settings.translate_to_english else "transcribe",
    word_timestamps=True,                          # forced on; needed by A3
    condition_on_previous_text=False,              # stop error propagation
    no_speech_threshold=0.6,                       # unchanged; lowering risks more hallucinations on silence
    compression_ratio_threshold=2.4,
    logprob_threshold=-1.0,                        # new: triggers temp fallback
    temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0),    # new: decoding fallback ladder
    initial_prompt=initial_prompt,
    verbose=False,
    fp16=True,
)
```

**Behavior**:
- `word_timestamps=True` is forced — it was previously a user setting. The runtime cost is small (~5 %) and we need word-level times for A3.
- `condition_on_previous_text=False` matches OpenAI's recommendation for long-form audio with silences.
- `temperature` as a tuple triggers mlx-whisper's built-in fallback: if a chunk's average logprob is below `logprob_threshold` or its compression ratio exceeds `compression_ratio_threshold`, it retries at the next higher temperature.

**Required change to emission gating (transcription.py:692-703)**:
The current code only populates `seg_data["words"]` when `settings.word_timestamps` is True. Since A3 needs `words` internally regardless of the user setting, this gating must be **decoupled**:

```python
# Always carry words through internally so A3 can split by speaker turn.
seg_data["words"] = [
    {"word": w.get("word", w.get("text", "")),
     "start": w["start"], "end": w["end"],
     "probability": w.get("probability", 1.0)}
    for w in segment.get("words", [])
]
transcription_segments.append(seg_data)
```

Then, **after** A3 and `stitch_speaker_turns`, strip `words` from emitted segments if the user opted out:

```python
if not settings.word_timestamps:
    for seg in transcription_segments:
        seg.pop("words", None)
```

This preserves the existing public contract (output unchanged when `word_timestamps=False`) while enabling internal use.

**Edge cases**:
- mlx-whisper's `temperature` accepts both a scalar and an iterable — passing a tuple is supported.
- `no_speech_threshold` deliberately kept at 0.6 — lowering it would increase emissions on silent regions, which A2 is independently trying to suppress upstream. Two changes pulling opposite directions = bad.

### A2 — VAD-based leading silence trim (silero-vad)

**Goal**: when Whisper's language detector runs on the first 30 s of audio, ensure that 30 s contains *speech*, not jingle / hold music / silence.

**Approach**: integrate `silero-vad` (torch.hub model, ~2 MB, MIT) to detect the first speech timestamp. If speech starts > 0.5 s into the file, pass a trimmed audio buffer to Whisper. Original segment timestamps are restored after transcription by adding back the trim offset.

**File**: new helper in `backend/services/audio.py`:

```python
def find_first_speech_offset(audio_path: str, min_silence_s: float = 0.5) -> float:
    """Return seconds of leading silence to trim. 0.0 if no significant lead-in.

    Uses silero-vad. Returns 0.0 if silero-vad is unavailable or audio
    can't be loaded — caller falls back to raw audio.
    """
```

Implementation:
- Load silero-vad via `torch.hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True)` — cached after first call
- Read audio via `soundfile` (already a dep), resample to 16 kHz mono if needed
- Run `get_speech_timestamps(audio, model, threshold=0.5, min_silence_duration_ms=400)`
- Return `timestamps[0]["start"] / 16000` if found and >= `min_silence_s`, else 0.0
- Wrap entire body in try/except — on any failure, return 0.0 and log a warning

**File**: `backend/services/transcription.py` — in `_run_transcription_sync`, before the Whisper branch:

```python
trim_offset = 0.0
if not use_voxtral and not use_voxtral_local and not use_parakeet:
    from services.audio import find_first_speech_offset
    trim_offset = find_first_speech_offset(audio_path)
    if trim_offset > 0:
        logger.info("Trimming %.2fs of leading silence before transcription", trim_offset)
        trimmed_path = _make_trimmed_audio(audio_path, trim_offset)
        audio_path_for_whisper = trimmed_path
    else:
        audio_path_for_whisper = audio_path
else:
    audio_path_for_whisper = audio_path
```

And after Whisper returns, before `assign_speakers_to_segments`:

```python
if trim_offset > 0:
    for seg in transcription_segments:
        seg["start"] += trim_offset
        seg["end"] += trim_offset
        for word in seg.get("words", []):
            word["start"] += trim_offset
            word["end"] += trim_offset
```

**Helper `_make_trimmed_audio`**: writes a trimmed WAV to a temp file (cleaned up in the existing `finally` block by extending the temp-dir cleanup logic to include the trimmed file).

**Why Whisper-only**: Voxtral and Parakeet don't have the same auto-language-detection flaw (they handle the whole file as one). Adding VAD trim there is unnecessary complexity for no benefit.

**Diarization stays on the original audio**: pyannote runs concurrently against `audio_path` (not `audio_path_for_whisper`). Whisper segment timestamps are restored to the original time base before A3 runs, so the two streams stay in sync. Do not pass the trimmed file to diarization — it would silently shift speaker turns relative to the original audio.

**Why not just default `language="en"`**: David's calls are bilingual FR/EN and will include all-French recordings. Forcing English breaks those. VAD trim fixes the root cause without restricting use cases.

### A3 — Word-boundary speaker assignment

**File**: `backend/services/diarization.py:146-162` — rewrite `assign_speakers_to_segments`.

**Current behavior** (broken): one speaker per Whisper segment via midpoint heuristic.

**New behavior**: when a Whisper segment crosses speaker-turn boundaries, split it into multiple sub-segments aligned to those boundaries.

**Algorithm**:

```python
def assign_speakers_to_segments(segments: list, speakers: list) -> list:
    if not speakers:
        return segments

    def speaker_at(t: float) -> str:
        for turn in speakers:
            if turn["start"] <= t < turn["end"]:
                return turn["speaker"]
        return "Unknown"

    out = []
    for seg in segments:
        words = seg.get("words") or []

        # Fallback path: no word timestamps available (Voxtral/Parakeet).
        # Keep midpoint behavior — these engines have their own diarization
        # or don't need word-level assignment.
        if not words:
            mid = (seg["start"] + seg["end"]) / 2
            out.append({**seg, "speaker": speaker_at(mid)})
            continue

        # Word-by-word: split segment when speaker changes between words.
        current_speaker = speaker_at(words[0].get("start", seg["start"]))
        buf_words = []
        buf_start = words[0].get("start", seg["start"])

        for w in words:
            w_speaker = speaker_at(w.get("start", w.get("end", buf_start)))
            if w_speaker != current_speaker and buf_words:
                out.append({
                    "start": buf_start,
                    "end": buf_words[-1].get("end", buf_start),
                    "text": " ".join(b.get("word", "").strip() for b in buf_words).strip(),
                    "speaker": current_speaker,
                    "words": buf_words,
                })
                current_speaker = w_speaker
                buf_words = []
                buf_start = w.get("start", buf_start)
            buf_words.append(w)

        if buf_words:
            out.append({
                "start": buf_start,
                "end": buf_words[-1].get("end", seg["end"]),
                "text": " ".join(b.get("word", "").strip() for b in buf_words).strip(),
                "speaker": current_speaker,
                "words": buf_words,
            })

    return out
```

**Interaction with existing `stitch_speaker_turns`** (diarization.py:109): unchanged. After splitting, adjacent same-speaker sub-segments with small gaps will be re-merged by `stitch_speaker_turns`, producing clean speaker turns.

**Edge cases**:
- A segment with no words list (Voxtral, Parakeet) falls through to existing midpoint behavior
- A segment fully inside one speaker turn produces one output sub-segment (no degradation)
- Punctuation attached to words: mlx-whisper emits per-word strings like `" Hello"`, `" ,"`, `" world"`, `" ."` (with leading spaces). After `.strip()` + `" ".join(...)`, the intermediate text is `"Hello , world ."`. The downstream `normalize_transcript_text` (postprocess.py:31) applies `re.sub(r"\s+([.!?,;:])", r"\1", text)` which correctly collapses these to `"Hello, world."`. **A3 unit test must include a punctuation case** to guard this contract.
- Empty speakers list: early return, unchanged from current behavior

**Known limitations** (acceptable in v1, tracked for follow-up):
- `speaker_at(t)` uses linear scan with `start <= t < end`. If a word's start time falls in a gap between two pyannote turns (small gaps are common at ~10 ms granularity), it returns `"Unknown"` and forces a spurious split. Mitigation: `stitch_speaker_turns` re-merges adjacent same-speaker turns, so an `"Unknown"` sub-segment between two identical neighbors collapses cleanly only if it's same-speaker on both sides — which it usually is. Worst case: one extra "Unknown" sub-segment per gap, still vastly better than current behavior.
- Overlapping speaker turns (pyannote can emit them for cross-talk) are resolved by first-match in list order, not by dominance. Acceptable since cross-talk is rare in 1-on-1 business calls and previously not handled at all.

## Data Flow After Changes

```
audio file
    │
    ├──[ A2: VAD trim if Whisper engine selected ]──► trimmed audio + offset
    │
    ├──[ pyannote diarization, concurrent ]──► [{start, end, speaker}, ...]
    │
    └──[ A1: mlx_whisper.transcribe with new params ]──► segments + words
                                                              │
                                                              ▼
                                              [ restore timestamps with offset ]
                                                              │
                                                              ▼
                                              [ A3: word-boundary speaker assign ]
                                                              │
                                                              ▼
                                              [ stitch_speaker_turns (existing) ]
                                                              │
                                                              ▼
                                              [ normalize_segments (existing) ]
                                                              │
                                                              ▼
                                              [ optional readable mode (existing) ]
```

## Testing Strategy

### Regression tests (must pass before merge)
1. Existing pytest suite in `backend/tests/` — no failures
2. Single-speaker English-only fixture: word count within ±2 %, no spurious speaker splits

### New tests
1. **A1 unit**: mock `mlx_whisper.transcribe`, verify kwargs include `condition_on_previous_text=False`, `temperature=(0.0, ...)`, `logprob_threshold=-1.0`, `word_timestamps=True`
2. **A1 emission-gating unit**: with `settings.word_timestamps=False`, A3 still receives populated `words` internally; emitted segments have `words` stripped after stitching
3. **A2 unit**: given a synthetic 5 s silence + 10 s speech audio, `find_first_speech_offset` returns ≈ 5.0. Given pure speech, returns 0.0. Given silero unavailable (mock `torch.hub.load` to raise), returns 0.0 and logs warning.
4. **A3 unit — basic split**: synthetic segment with words spanning two speaker turns → produces two sub-segments with correct boundary
5. **A3 unit — punctuation**: words `[" Hello", " ,", " world", " ."]` produce text `"Hello, world."` after `normalize_transcript_text` runs
6. **A3 unit — gap between turns**: a word with start time in the gap between two pyannote turns is labeled "Unknown" but `stitch_speaker_turns` re-merges same-speaker neighbors
7. **A3 unit — no words fallback**: segment with no `words` key → midpoint fallback works (parity with current)
8. **A3 unit — empty speakers**: no-op

### Manual validation (gate for "done")
- Re-run on `Tests/15-29-21.m4a` (Pascal Weber call) with diarization + speaker tags for "David Marchesseau" and "Pascal Weber" pre-registered
- Compare segment-by-segment against current Davrine output and Turboscribe baseline
- Acceptance criteria:
  - No leading non-target-language segment
  - Speaker turn changes visible at sentence-level granularity (not 3-minute blocks)
  - At least 3 of the 5 hallucinations identified in the comparative review are gone or reduced

## Dependencies

- New: `silero-vad` (loaded via torch.hub, no `requirements.txt` entry needed if torch is already there — which it is, via pyannote)
- No other new packages

## Rollout

Single PR on the `dev` branch. Manual validation gate before merge to main. No feature flag — these are pure quality fixes with documented fallbacks on failure.

## Open Questions

- mlx-whisper API quirks around the `temperature` tuple — if implementation hits an issue, fallback is to set `temperature=0.0` and accept reduced robustness on the first iteration, file a follow-up.
- silero-vad first call requires a network round-trip (torch.hub.load downloads the ~2 MB model and caches it under `~/.cache/torch/hub/`). First-run on a fresh install with no internet logs a warning and returns 0.0 (graceful degradation to current behavior). Acceptable for now; pre-bundling the silero weights into the repo is a follow-up if needed.

## Follow-ups (Out of Scope for This Spec)

- **Approach B'**: improve existing context/refinement features
  - Pipe speaker + context blob into `RefinementService.analyze()` prompt
  - Make refinement auto-run when speaker/context selected
  - Upgrade Haiku → Sonnet for corrections pass (or two-tier)
  - Auto-match diarization speaker embeddings against `speakers/<id>/embedding.npy`
  - Persistent global glossary (`contexts/_global.md`)
- **Approach C**: evaluate Voxtral Local 4B Realtime on same Pascal sample + 2-3 others; decide on engine pivot
