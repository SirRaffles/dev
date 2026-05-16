# Transcription engines & feature compatibility

The app supports four transcription engines. Not every fix or capability applies
to every engine — they have different decoders, different diarization paths, and
different word-emission contracts. This table documents what's wired where.

| Capability                          | Whisper        | Voxtral Local     | Voxtral API     | Parakeet      |
|------------------------------------|----------------|-------------------|-----------------|---------------|
| A1 — decoding params (logprob, temp ladder, no condition-on-previous) | ✅ applied | ❌ N/A (different engine) | ❌ N/A | ❌ N/A |
| A2 — VAD-based leading-silence trim | ✅ applied   | ❌ skipped (reads full audio) | ❌ skipped | ❌ skipped |
| A3 — word-boundary speaker split    | ✅ when words emitted | ⚠️ midpoint fallback | ⚠️ uses Voxtral's own diarization | ⚠️ midpoint fallback |
| B1–B7 (refinement, glossary, learning) | ✅ engine-agnostic | ✅ | ✅ | ✅ |

## Default engine

The application ships with `engine="voxtral-local"` and
`model_size="voxtral-realtime-4b"` as the `TranscriptionSettings` defaults
(see `backend/job_models.py`). The Whisper engine is opt-in via the Settings
panel — it remains available for users who need A1/A2/A3 specifically.

## Why the asymmetry

- **A1**: Whisper-only. The other engines don't expose decoder-level knobs.
- **A2**: Whisper-only — its language detector is uniquely sensitive to leading
  silence/jingles. Voxtral and Parakeet are robust to this.
- **A3**: Requires per-word timestamps. Whisper emits them when
  `word_timestamps=True` (we force this internally). The other engines either
  don't emit words or have their own diarization that handles the boundary
  decision differently.
- **B1–B7**: Operate on already-transcribed segments, so they're agnostic to
  which engine produced them.
