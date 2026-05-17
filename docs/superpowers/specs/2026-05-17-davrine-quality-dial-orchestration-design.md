# Davrine Transcription — Quality Dial & Orchestration Architecture

**Status**: Draft for implementation
**Date**: 2026-05-17
**Scope**: Replace engine selection UI with a 2-position Quality dial; introduce a backend orchestrator that composes the best local model stack per mode; ship a universal semantic diarization polish step; remove obsolete UI surfaces.
**Sequel to**: Plans 1, 2, 3 (B' v2 — refinement, learning system, UX surfaces). Re-architects the entry point those plans share.

## Context

After Plans 1-3 shipped, the app exposed 4 transcription engines (Whisper, Voxtral Local, Voxtral Cloud, Parakeet) + 9 model variants in a flat selector. The user's manual usage exposed the limits of this model:

- Engine choice is an implementation detail. The user wants "best transcript quality" — not "Voxtral vs Whisper".
- The 4 engines have asymmetric capabilities (voice auto-match disabled for Cloud, no per-word timestamps for Voxtral/Parakeet, etc.). Plan 3 papered over the asymmetry with capability disclosure notes — useful but a symptom, not a fix.
- After Plan 1's Sonnet refinement and continuous learning landed, the raw WER difference between engines (Voxtral 4% vs Whisper Turbo 5%) collapses post-refinement. The engine choice no longer meaningfully impacts final quality — but does impact latency dramatically (Voxtral 60min vs Whisper Turbo 8min on 30min audio).
- The user's audio is exclusively EN + FR. This eliminates several engine constraints (Parakeet v3 multilingual works for both) and simplifies the model space.
- Diarization is the dominant axis of remaining quality variance. Engines without per-word timestamps (Voxtral, Parakeet) fall back to midpoint speaker assignment — visible in transcripts as speaker changes at 30s chunk boundaries instead of natural sentence breaks.

This spec eliminates engine choice from the user's surface, introduces a backend orchestrator that always selects the best-quality local stack, and ships a universal Sonnet-driven semantic diarization polish so speaker boundaries land on sentence breaks regardless of which engine produced the underlying text.

## Goals

1. **One quality decision, not seven.** The user picks Best or Quick. The system decides which models, which order, which parallelism. Power-user "Advanced" escape hatch is explicitly excluded — full removal, no fallback.
2. **Engine-agnostic diarization quality.** Speaker boundaries land on sentence breaks regardless of whether the text engine emits word timestamps. Combo C (Sonnet semantic re-attribution) becomes a refinement-step universal.
3. **Visible phased progress.** The progress bar shows which phase is running (Diarizing → Transcribing → Refining → Learning) so the user understands the wait, especially for Best mode's longer pipeline.
4. **Clean break, no fallback.** Old engine values (`whisper`, `voxtral-local`, `voxtral-api`, `parakeet*`) are rejected by the new API. New API accepts only `auto-best` and `auto-quick`. Stale data in DB is fine (those jobs were completed under the old code); no migration of running clients required because there's only one client (the app's own UI), which we update in lockstep.
5. **No new runtime dependencies in the frontend.** Backend can add pyannote + Whisper Turbo (already there) + Parakeet v3 (already there) + Sonnet (already there). No new ML model added by this spec. Sonnet's per-job cost grows by ~30-50% due to the new diarization-polish prompt extension.

## Non-Goals

- **No new ML models.** All orchestration uses what's already installed. Wav2vec2 forced aligner was considered and rejected — Sonnet semantic polish provides higher-quality diarization correction at lower complexity, and Whisper Turbo's native word timestamps make external alignment unnecessary for Best mode.
- **No per-context glossaries** (Plan 4 territory). The orchestrator uses the existing global glossary + speaker bios for context.
- **No multi-language audio** in a single recording. Plans assume each recording is mono-lingual (EN or FR). Mixed-language detection is out of scope.
- **No multi-user / sharing.** Single-user app stays single-user.
- **No remote orchestration** of models. All execution stays local (or via the Anthropic API for Sonnet, as Plan 1 already does).
- **No backwards compat for old engine values.** The `engine` field in `TranscriptionSettings` becomes a `Literal["auto-best", "auto-quick"]`. Existing requests with old values are rejected with 400. The frontend is updated in the same shipping window.

## Design

### Quality Dial UX

**SettingsPanel layout** — replaces the current engine selector + model dropdown:

```
┌──────────────────────────────────────────────────────────┐
│  Quality                                                 │
│  ┌─────────────────┬─────────────────┐                   │
│  │  ● Best          │  ○ Quick         │                  │
│  │  Full pipeline   │  Fast preview    │                  │
│  │  ~10 min         │  ~30 sec         │                  │
│  └─────────────────┴─────────────────┘                   │
└──────────────────────────────────────────────────────────┘
```

- Two large mutually-exclusive buttons. Best is the default. Sub-label under each shows the order-of-magnitude wait time so the trade-off is visible up-front.
- **No Advanced section.** Power-user engine choice is explicitly removed from the UI. Internal-only orchestration.
- Other Settings knobs that remain: Language (auto/EN/FR), Speaker Diarization toggle, Number of Speakers, Context Document, Expected Speakers, Output Mode (Verbatim/Readable), Noise Reduction. All knobs that were Voxtral/Whisper/Parakeet-specific in Plan 3 disappear because the orchestrator owns those decisions.

### Best Mode Stack

```
[t=0]    pyannote diarization      (~30s, parallel)
[t=0]    Whisper Large V3 Turbo    (~8 min on 30 min audio, parallel)
                                    + native word_timestamps
                                    + A1 decoding params (Plan 1)
                                    + A2 VAD trim (Plan 1)
[t=8min] A3 word-boundary split    (Plan 1, runs on Whisper output)
[t=8min] Job marked completed       → user sees Verbatim transcript
[t=8min] Sonnet refinement async   (~2-3 min) — extended prompt:
                                    1. Corrections (Plan 1 B1)
                                    2. Speaker identification (Plan 1 B1)
                                    3. NEW: Diarization semantic polish
[t=11min] Refinement done           → user sees Refined badge + polished speakers
[t=11min] B7 learning workers       (Plan 2) — embeddings, insights, glossary
```

Total wall-clock: ~12 min on 30 min audio. User sees first transcript at ~8 min, polish at ~11-12 min.

### Quick Mode Stack

```
[t=0]    pyannote diarization      (~30s, parallel)
[t=0]    Parakeet v3 multilingual  (~30s on 30 min audio, parallel)
                                    EN+FR supported
[t=30s]  A3-light split             — Parakeet has no word timestamps, so
                                      split each segment at pyannote turn
                                      boundaries via time-proportional ratio
                                      (60% of segment time → 60% of words)
[t=30s]  Job marked completed       → user sees Verbatim transcript
[t=30s]  Sonnet refinement async   (~2-3 min, identical to Best mode)
[t=3min] Refinement done            → polished speakers + learning fires
```

Total wall-clock: ~3 min on 30 min audio. User sees first transcript at ~30s.

**Trade-off explicitly accepted:** Quick mode's first transcript has approximate speaker boundaries (time-proportional). Sonnet refinement polishes them later. Best mode's first transcript has accurate boundaries (Whisper word timestamps) from the start, then Sonnet polishes them further.

### Combo C — Semantic Diarization Polish (universal refinement step)

Plan 1's `RefinementService.analyze` produces a `corrections` list. We extend its prompt to also produce a `speaker_corrections` list. Schema additions:

```json
"speaker_corrections": [
  {
    "segment_index": 12,
    "speaker": "Pascal",
    "reason": "interruption by Pascal mid-David turn"
  },
  {
    "segment_index": 13,
    "speaker": "David",
    "reason": "continues David's sentence after Pascal's interjection"
  }
]
```

Prompt extension (added to the existing `## Known context` block when diarization was run):

```
## Diarization context

Pyannote detected the following speaker turns:
[2.4s-15.7s] SPEAKER_00
[15.7s-18.2s] SPEAKER_01
[18.2s-32.1s] SPEAKER_00
... (full list, capped at ~50 turns for prompt budget)

The current segment→speaker assignments may have mis-attributions where
a brief interjection (e.g. "yes", "right", "exactly") was assigned to
the dominant speaker of the segment instead of the interjector. Review
each segment and emit a `speaker_corrections` array for any segments
whose speaker should change based on:
- Conversational turn-taking cues (brief acknowledgments mid-sentence)
- Sentence-boundary semantics (a sentence should not change speaker mid-flow)
- Direct address patterns ("Pascal, what do you think?")

Only emit corrections you're confident in. Do NOT rewrite segment text.
```

`apply_corrections` is extended to apply speaker_corrections to the refined_segments. **Hard guardrail**: Sonnet can only modify `seg.speaker`, never `seg.text`. The existing text-correction path stays separate.

Backward-compat: when `speaker_corrections` is absent from Sonnet's response (older model, prompt drift), the existing diarization stays.

### Backend Orchestrator

New module `backend/services/orchestrator.py`:

```python
async def orchestrate_transcription(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Compose the right model stack for the job's quality mode.

    Best mode → Whisper Large V3 Turbo + pyannote + Sonnet (with diarization polish)
    Quick mode → Parakeet v3 + pyannote + Sonnet (background, same polish)
    """
```

This module is a thin coordinator. **One prerequisite refactor**: extract a `transcribe_with_whisper(audio_path, settings, job=None) -> dict` function out of the current inline Whisper branch in `_run_transcription_sync` (Whisper is currently inlined at lines ~686-end of `services/transcription.py`, not a callable). This refactor preserves the A1/A2/A3 wiring exactly and is the first task of Sub-plan A.

After the refactor, the orchestrator delegates to:
- `services.diarization.run_diarization` (unchanged)
- `services.transcription.transcribe_with_whisper` (Best) — NEW callable extracted in this sub-plan
- `services.transcription.transcribe_with_parakeet` (Quick) — already exists
- `services.diarization.assign_speakers_to_segments` (Best — uses A3 word-boundary; works as-is for Whisper)
- `services.diarization.assign_speakers_time_proportional` (Quick — NEW helper, A3-light)
- `routes.refinement._run_refinement_for_job` (unchanged signature; the diarization-polish prompt extension is internal to `RefinementService`)
- `routes.refinement._run_post_refinement_learning` (unchanged)

New helper in `services/diarization.py`:

```python
def assign_speakers_time_proportional(segments, speaker_turns):
    """A3-light: split each segment at speaker-turn boundaries by
    time-proportional text ratio.

    Used when the text engine doesn't emit per-word timestamps
    (Parakeet, Voxtral). Handles N-way splits: a segment that spans 3+
    pyannote turns produces 3+ sub-segments. Word allocation per
    sub-segment uses ceil(N_words * (sub_duration / total_duration))
    with a final-segment adjustment to absorb rounding so total word
    count matches the input.

    Example: segment "Hi yes that's right what do you think" (10s,
    pyannote turns: A=[0-3s], B=[3-4s], A=[4-10s]) → 3 sub-segments
    of A/B/A with word counts approximately 3/2/4."""
```

`_run_transcription_sync` becomes a wrapper that routes to the orchestrator based on `settings.engine`:

```python
def _run_transcription_sync(job_id, audio_path, settings):
    if settings.engine == "auto-best":
        asyncio.run(orchestrate_transcription(job_id, audio_path, settings, mode="best"))
    elif settings.engine == "auto-quick":
        asyncio.run(orchestrate_transcription(job_id, audio_path, settings, mode="quick"))
    else:
        raise ValueError(f"Unknown engine: {settings.engine}. Use 'auto-best' or 'auto-quick'.")
```

The legacy direct-engine paths (`use_voxtral`, `use_voxtral_local`, `use_parakeet`, Whisper-direct) are **removed**. Their bodies are folded into the orchestrator's mode-specific paths. Net code reduction expected: ~150-200 LOC in `transcription.py`.

### Phased Progress Bar

Current progress is a single 0-100% bar with a `progress_message` string. The orchestrator emits structured phase markers in addition:

`TranscriptionJob` gains an in-memory field:
```python
self.phase: Optional[Literal["diarizing", "transcribing", "aligning", "refining", "learning"]] = None
```

`None` = no active phase (either pre-start or post-everything-done).

`_update_job` extended to accept an optional `phase` parameter. The GET `/job/{id}` response surfaces it. The frontend `ProgressBar` component renders a small pill above the bar showing the current phase.

**Phase lifecycle (single source of truth):**

| Trigger | `phase` becomes | `status` becomes | `refinement_status` becomes | `learning_status` becomes |
|---|---|---|---|---|
| Job created | `None` | `pending` | `None` | `None` |
| pyannote diarization starts (parallel branch) | `"diarizing"` | `processing` | `None` | `None` |
| Text engine starts (parallel with diarization) | `"transcribing"` | `processing` | `None` | `None` |
| A3 / A3-light split runs | `"aligning"` | `processing` | `None` | `None` |
| Job marked completed (verbatim ready) | `None` | `completed` | `None` | `None` |
| Refinement worker picks up | `"refining"` | `completed` | `processing` | `None` |
| Refinement done, learning starts | `"learning"` | `completed` | `done` | `None` (then `processing` once learning starts internally — orchestrator sets `phase=learning` before kicking workers) |
| Learning workers complete | `None` | `completed` | `done` | `ok` \| `partial` \| `failed` |

**Note**: `phase` is the orchestrator's view of the active step. `status`/`refinement_status`/`learning_status` are the persisted lifecycle markers (Plan 1 B2 + Plan 2 B7). The frontend uses `phase` for the human-readable pill ("Refining…") and the other fields for downstream actions (showing the Refined badge once `refinement_status === "done"`).

When `phase=transcribing` AND diarization is also running in parallel, the UI picks `"transcribing"` as the displayed pill (transcription is the long pole). Showing "Transcribing… (also diarizing)" is an option but adds noise — prefer the dominant phase only.

The 0-100% percent continues to mean "raw audio bytes processed" by the text engine — phases are a complementary axis. The pill changes as phases transition; the bar continues to fill.

### Migration & Removal (no fallback)

**Removed completely — Backend** (most of this lands in Sub-plan D; Sub-plan A extracts what blocks orchestration):

Transcription engine surface:
- `backend/services/voxtral_service.py` — entire module (~200 LOC; uses raw `requests` for the Mistral Voxtral API)
- `backend/services/__init__.py` — `VoxtralService` export
- `backend/services/transcription.py:transcribe_with_voxtral` (Voxtral Cloud function)
- `backend/services/transcription.py:transcribe_with_voxtral_local` (Voxtral Local function + Voxtral A2 trim wiring added in commit `f585c11`)
- The direct-Whisper branch inside `_run_transcription_sync` (replaced by `transcribe_with_whisper` extracted helper + orchestrator call)
- The direct-Parakeet branch inside `_run_transcription_sync` (logic moves to orchestrator)

State / lifecycle:
- `backend/state.py` — `_voxtral_available`, `_voxtral_service`, `_voxtral_local_available`, `_voxtral_local_model`, `_voxtral_local_model_name` module-level vars + their initialization
- `backend/main.py` — `MISTRAL_API_KEY` env-var loading, VoxtralService instantiation block, `_voxtral_local_available` discovery branch (lines ~141, ~154-161)

Model manager:
- `backend/services/model_manager.py` — `ModelName.VOXTRAL_LOCAL` enum value, `CONFIGS[VOXTRAL_LOCAL]` entry, entire `load_voxtral_local()` method (~50 LOC starting line ~373), the unload branch (~lines 457-461)

Config:
- `backend/config.py` — `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`, `VOXTRAL_LOCAL_LANGUAGES` constants

Routes:
- `backend/routes/transcription.py` — query-param defaults `engine="voxtral-local"` and `model_size="voxtral-realtime-4b"` at lines ~113, ~117, ~248, ~253; engine validation branches at lines ~127-134, ~140-148, ~270-277, ~283-291. Replaced with the new `engine: Literal["auto-best", "auto-quick"]` default `"auto-best"`.
- `backend/routes/models_api.py` — `/models` and `/health` endpoints lines 11, 66, 69-70, 101-115, 123-124, 135-150 that report Voxtral availability. Either retire `/models` entirely or strip to `whisper` + `parakeet` engines only.

Models / settings:
- `backend/job_models.py` — `TranscriptionSettings.engine` becomes `Literal["auto-best", "auto-quick"]` default `"auto-best"`. `TranscriptionSettings.model_size` field removed entirely. `TranscriptionSettings.speed_priority` field becomes orchestrator-internal (frontend never sets it; orchestrator picks Whisper Turbo always for Best mode).

**Removed completely — Frontend**:
- `src/components/SettingsPanel.tsx` — engine selector (3 buttons), model_size dropdown, Speed Priority knob (Whisper-specific), Two-Pass Mode knob (Voxtral Cloud), Context Terms knob (Voxtral Cloud), engine capability disclosure block (added in commit `c5e4a53`), Word Timestamps engine-gating logic (added in commit `4f57b10`)
- `src/utils/api.ts` — `MODEL_SIZES`, `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`, `ENGINES` constants. `TranscriptionOptions.engine` narrows to the two new values. `TranscriptionOptions.modelSize`, `twoPass`, `speedPriority`, `contextTerms` fields removed.
- `src/hooks/useEngineAvailability.ts` — entire hook. It existed to detect Voxtral availability and fall back to Whisper. No longer needed.
- `src/App.tsx` — `useEngineAvailability` consumer code (~lines 100-104 and the `fallbackNotice` rendering downstream). The `setSettings(prev => ({...prev, ...fallback}))` branch on awaken (~line 110) also goes — no fallback to compute.

**Removed completely — Docs / config**:
- `docs/engines.md` — replaced by inline help in the Quality dial
- `README.md` — engine compatibility matrix link removed (added in Plan 1 Task 10)
- `docker-compose.yml` — `MISTRAL_API_KEY` env var passthrough (if present)
- `.claude/settings.local.json` — Voxtral references (if any user-facing — verify)

**Removed completely — JPR watcher (critical for production)**:
- `watcher/config.py` — `TRANSCRIPTION_SETTINGS["engine"] = "whisper"` becomes `"auto-best"`. `TRANSCRIPTION_SETTINGS["model_size"]` key deleted. Without this, the always-on JPR watcher (launchd-managed `com.whisper.jpr-watcher`) will 400 every transcription submission the moment the backend cut-over happens.

**Test fixture migration** (Sub-plan A includes this):
- `backend/tests/test_transcription_a1.py` — 4+ tests construct `TranscriptionSettings(engine="whisper", ...)` directly. Change to `engine="auto-best"`. The Whisper-specific assertions remain valid because Best mode = Whisper Turbo internally.
- `backend/tests/test_file_validation.py` — engine validation tests need updating to assert old engine values are rejected, new ones accepted.
- `backend/tests/test_auto_refine_orchestration.py` — 5+ fixtures use `engine="whisper"`. Migrate to `auto-best`.
- `backend/tests/test_inline_auto_match.py` — 2 fixtures use `engine="whisper"`. Migrate.
- `backend/tests/test_diarization_a3.py` — Voxtral coverage to remove or migrate.

Estimated test files touched: ~6 files, ~15-20 fixture changes total.

**Kept**:
- All Plan 1/2/3 wiring (refinement, B7 learning, glossary, B5 auto-match, B6a-f UX surfaces)
- Whisper Turbo engine code (the only kept text engine for Best mode)
- Parakeet v3 multilingual engine code (the only kept Quick text engine)
- Pyannote diarization
- `TranscriptionSettings` fields other than `engine` / `model_size`
- `original_filename` field (used by `_resolve_job_audio_path`)
- All existing API endpoints (jobs, refine, learning, contexts, speakers, jpr, recordings)

**New API contract**:
- `TranscriptionSettings.engine: Literal["auto-best", "auto-quick"]`, default `"auto-best"`
- `TranscriptionSettings.model_size` removed entirely
- Any request with the old engine values returns 400 with: `{"detail": "Engine 'voxtral-local' is no longer supported. Use 'auto-best' or 'auto-quick'."}`

**No data migration**. Existing jobs in `JobStore` with old engine values stay readable (the `settings` JSON column can hold anything). They're not re-runnable via the new API, but their results stay viewable.

## Data Flow (Best mode, full pipeline)

```
audio file + settings(engine=auto-best, language=auto, speakers)
     │
     ├──[parallel]──► pyannote diarization ──► turns
     │
     ├──[parallel]──► load_global_glossary + load_context + load_speakers_context
     │                      └──► initial_prompt (Plan 1 A1 + B4)
     │
     ├──► A2 VAD trim (Plan 1) ──► trimmed audio
     │
     └──► Whisper Large V3 Turbo (A1 decoding params)
              └──► segments + per-word timestamps
                    │
                    ├──► A3 word-boundary split with pyannote turns
                    │     └──► clean speaker boundaries
                    │
                    ├──► normalize + optional readable mode
                    │
                    ├──► job.segments = [...]
                    │     job.phase = None         (no active phase; matches the Phase Lifecycle table)
                    │     job.status = "completed"  ◄── UI gets verbatim
                    │
                    └──► [async background]
                          ├──► B5 inline auto-match (Plan 1)
                          │     └──► job.auto_speaker_matches
                          │
                          ├──► dispatch refinement on executor (Plan 1 B2)
                          │     └──► _run_refinement_for_job
                          │           job.phase = "refining"
                          │           ├──► load context bundle (global + context + speakers + B5 matches)
                          │           ├──► Sonnet analyze (Plan 1 B1 + NEW diarization polish prompt)
                          │           │     └──► corrections + speakers + speaker_corrections + uncertain_terms
                          │           ├──► apply_corrections (text + speaker_mapping + NEW speaker_corrections)
                          │           ├──► RefinementStore.save_result
                          │           ├──► job.refinement_status = "done"   ◄── UI gets Refined badge
                          │           │
                          │           └──► _run_post_refinement_learning
                          │                 job.phase = "learning"
                          │                 ├──► overlay refined speakers onto job.segments (Plan 3 Task 2)
                          │                 ├──► augment speaker_ids with B5 matches (Plan 3 followup)
                          │                 ├──► update_speaker_embeddings (Plan 2 B7)
                          │                 ├──► extract_insights_auto (Plan 2 B7)
                          │                 ├──► learn_glossary_terms (Plan 2 B7)
                          │                 └──► job.learning_status = "ok"  ◄── UI gets toast (B6d)
                          │                       job.phase = None
                          │
                          └──► _cleanup_deferred_audio (Plan 2 Task 6)
```

## Decomposition into 4 sub-plans

The work breaks into 4 independently-shippable plans. The user requested parallel sub-planning via dedicated agents.

### Sub-plan B — Combo C semantic diarization polish (refinement extension)

**Scope**: extend `RefinementService.analyze` prompt and schema to accept a `speaker_corrections` array. Extend `apply_corrections` to apply them. Adds Sonnet's semantic polish to every refinement run — improves diarization quality on existing engines IMMEDIATELY without waiting for the orchestrator.

**Independence**: pure backend, touches `services/refinement.py` only. Ships in isolation. Improves all current engines' diarization quality.

**Files**: `backend/services/refinement.py`, `backend/tests/test_refinement_context.py`

**Estimated**: 4-5 tasks.

### Sub-plan A — Orchestrator backend + API contract switch

**Scope**:
1. **Refactor prereq**: extract `transcribe_with_whisper(audio_path, settings, job=None) -> dict` from the inline Whisper branch in `_run_transcription_sync` (~lines 686-end of `services/transcription.py`), preserving A1/A2/A3 wiring exactly.
2. Introduce `backend/services/orchestrator.py` with the Best/Quick dispatch logic.
3. Add `assign_speakers_time_proportional` (A3-light, N-way safe) to `services/diarization.py`.
4. Phased progress bar backend: add `phase` field to `TranscriptionJob`, extend `_update_job`, surface in GET `/job/{id}` response.
5. Narrow `TranscriptionSettings.engine` to `Literal["auto-best", "auto-quick"]` default `"auto-best"`. Remove `model_size` field.
6. Update `_run_transcription_sync` to route via the orchestrator. Remove all direct-engine branches (Voxtral, Whisper-direct, Parakeet-direct, Voxtral Cloud).
7. Update query-param defaults + engine validation branches in `backend/routes/transcription.py` lines ~113/117/127-148/248/253/270-291.
8. Migrate test fixtures: all `engine="whisper"` / `"voxtral-*"` / `"parakeet"` references in `test_transcription_a1.py`, `test_file_validation.py`, `test_auto_refine_orchestration.py`, `test_inline_auto_match.py`, `test_diarization_a3.py` → `engine="auto-best"`.
9. Update `watcher/config.py` `TRANSCRIPTION_SETTINGS["engine"]` → `"auto-best"`, drop `model_size`. CRITICAL — without this the JPR watcher 400s on every submission.

**Independence**: depends on Sub-plan B (the orchestrator's Best path calls into refinement which now expects to do diarization polish). Must ship in lockstep with Sub-plan C — backend rejects old engine values, frontend must send the new ones. Sub-plan D (heavy cleanup of dead Voxtral surface) runs AFTER A+C land.

**Files**: `backend/services/orchestrator.py` (new), `backend/services/transcription.py` (refactor + remove branches), `backend/services/diarization.py` (new helper), `backend/job_models.py` (TranscriptionSettings.engine narrowing, phase field), `backend/routes/transcription.py` (query defaults + validation), `watcher/config.py` (engine value), `backend/tests/test_orchestrator.py` (new), `backend/tests/test_transcription_a1.py` + `test_file_validation.py` + `test_auto_refine_orchestration.py` + `test_inline_auto_match.py` + `test_diarization_a3.py` (fixture migration)

**Estimated**: 9-11 tasks.

### Sub-plan C — UI Quality dial + phased progress bar

**Scope**: replace SettingsPanel's engine selector + model dropdown with the 2-position Quality dial. Update App.tsx default settings. Update useTranscription.ts to send `engine: 'auto-best'`. Remove all engine-conditional logic from SettingsPanel (the dial decides). Add phased progress bar (frontend half of the phase indicator — reads `job.phase` from polling, renders a pill above the bar).

**What this sub-plan does NOT touch** (deferred to Sub-plan D): `useEngineAvailability.ts`, the `MODEL_SIZES`/`VOXTRAL_*`/`ENGINES` constants in `api.ts`. Sub-plan C only adds the dial and points settings at the new engine values; Sub-plan D sweeps away the dead surface.

**Independence**: depends on Sub-plan A (backend must accept the new engine values). Must ship in lockstep with Sub-plan A — backend cut-over + frontend cut-over = single shipping event.

**Files**: `src/components/SettingsPanel.tsx` (replace engine/model UI with Quality dial), `src/App.tsx` (default `engine: 'auto-best'`), `src/hooks/useTranscription.ts` (no engine remap needed), `src/utils/api.ts` (narrow `TranscriptionOptions.engine` to the 2 new values, keep MODEL_SIZES/VOXTRAL_* for now — D removes them), `src/components/ProgressBar.tsx` (phase pill rendering)

**Estimated**: 5-7 tasks.

### Sub-plan D — Voxtral surface removal sweep (dead-code cleanup)

**Scope** (post A+C, when no production code path uses Voxtral anymore):

Backend:
- Delete `backend/services/voxtral_service.py` entirely.
- Remove `VoxtralService` from `backend/services/__init__.py`.
- Remove from `backend/state.py`: `_voxtral_available`, `_voxtral_service`, `_voxtral_local_available`, `_voxtral_local_model`, `_voxtral_local_model_name` vars + initialization.
- Remove from `backend/main.py`: `MISTRAL_API_KEY` env-var loading, `VoxtralService` instantiation, `_voxtral_local_available` discovery branch.
- Remove from `backend/services/model_manager.py`: `ModelName.VOXTRAL_LOCAL` enum value, `CONFIGS[VOXTRAL_LOCAL]` entry, `load_voxtral_local()` method, unload branch.
- Remove from `backend/config.py`: `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`, `VOXTRAL_LOCAL_LANGUAGES` constants.
- Update `backend/routes/models_api.py`: strip Voxtral availability reporting from `/models` and `/health`. Either retire `/models` entirely or keep only `whisper` + `parakeet`.
- Remove from `TranscriptionSettings`: `speed_priority`, `two_pass`, `context_terms` fields (orchestrator owns these decisions; no longer user-set).

Frontend:
- Delete `src/hooks/useEngineAvailability.ts`.
- Remove `useEngineAvailability` consumer from `src/App.tsx` (~lines 100-104) and the `fallbackNotice` rendering.
- Remove the `setSettings(prev => ({...prev, ...fallback}))` branch on awaken.

Docs / config:
- Delete `docs/engines.md`.
- Remove engine compatibility matrix link from `README.md` (added in Plan 1 Task 10).
- Remove `MISTRAL_API_KEY` from `docker-compose.yml` if present.
- Verify and clean `.claude/settings.local.json` references.

**Independence**: depends on Sub-plans A + C being live in production. Last to ship — purely a sweep, no behavior changes.

**Files**: ~15-20 files touched (mostly deletions or surgical removes). See above enumeration.

**Estimated**: 4-5 tasks (one task per affected layer: services, state, model_manager, routes, frontend hook, docs).

### Execution order

- **B and A can be written in parallel** (independent backend specs).
- **C can be written in parallel** with A and B (the spec is self-contained even if it depends on A's implementation).
- **D can be written in parallel** too.
- **Implementation order**: B ships first (improves current system in isolation). Then A + C ship together (must be co-deployed). Then D cleans up.

The user requested writing-plans to be dispatched in parallel for all 4 sub-plans. Sub-plan implementation is sequenced as B → (A+C together) → D.

## Testing Strategy

**Sub-plan B (refinement extension)**:
- Unit: `analyze()` prompt contains the diarization polish block when speaker_turns are provided
- Unit: `analyze()` returns `speaker_corrections` array (mock Sonnet response)
- Unit: `apply_corrections` mutates segment.speaker per speaker_corrections, never touches segment.text
- Integration: refinement on a fixture transcript where Sonnet identifies a mid-sentence speaker error → assert the segment now has the corrected speaker

**Sub-plan A (orchestrator)**:
- Unit: orchestrator dispatches Whisper Turbo for Best mode
- Unit: orchestrator dispatches Parakeet v3 for Quick mode
- Unit: TranscriptionSettings rejects `engine='voxtral-local'` etc. with 400
- Unit: `assign_speakers_time_proportional` splits segments at turn boundaries by time ratio
- Integration: end-to-end Best path produces phase transitions (diarizing → transcribing → completed → refining → learning)

**Sub-plan C (UI dial)**:
- Manual: dial visibly toggles Best/Quick; default is Best
- Manual: phased progress bar shows the right label per phase
- Manual: no engine selector or model dropdown visible anywhere
- Snapshot/render test: SettingsPanel renders the dial component

**Sub-plan D (cleanup)**:
- Manual: app still works end-to-end after removals
- Grep: removed exports no longer referenced

**End-to-end manual validation gate** (Pascal Weber audio):
- Submit Best mode → see phased progress → verbatim at ~8 min → Refined at ~11 min → learning summary appears
- Submit Quick mode → see phased progress → verbatim at ~30s → Refined at ~3 min → learning summary appears
- Diarization in both modes shows clean speaker boundaries (no mid-sentence speaker changes)
- "Manukai", "DMG Mori", "Starrag" still appear correctly (Plan 1 acceptance criterion preserved)

## Open Questions (resolved during brainstorm)

| Question | Decision |
|---|---|
| Single dial or engine selector? | 2-position dial (Best / Quick). No Advanced section. |
| Best mode text engine? | Whisper Large V3 Turbo — refinement absorbs WER edge vs Voxtral, 8× faster, native word timestamps. |
| Quick mode text engine? | Parakeet v3 multilingual — EN+FR both supported, 60× speed. |
| Diarization fix scope? | Universal Sonnet semantic polish (Combo C, Sub-plan B). Helps all engines, not just Voxtral. |
| Phased progress visualization? | Yes — `TranscriptionJob.phase` field + ProgressBar phase pill. |
| Fallback for old engine values? | No fallback. Hard reject with 400. Frontend updated in lockstep. |
| Voxtral retained as power-user choice? | No. Removed entirely. |
| Parallel transcription engines for ensemble? | No. Single engine per mode, kept simple. |
| Per-context glossaries? | Out of scope. Deferred to a future plan. |

## Out of Scope (post this spec, future)

- **Per-context glossaries** (current backlog item)
- **Rename recording with LLM-suggested name** (current backlog item, half-shipped)
- **Voxtral kept available somehow** — explicitly excluded. If user later wants Voxtral back, it'd be a new plan.
- **Auto-detect mode from audio properties** (e.g. "audio < 5min + 1 speaker → auto-Quick"). Could be a future enhancement; for now Best is always default + Quick is explicit toggle.
- **Multi-language audio mid-recording** — assume mono-lingual per recording.
- **Per-correction confidence field on `speaker_corrections`** — the spec's schema relies on Sonnet's "only emit corrections you're confident in" prompt honor system. If false-positive speaker reassignments become a problem in practice, add a `confidence: "high"|"medium"|"low"` field and apply only `"high"` (analogous to B1's text-correction filter which currently applies high+medium via `RefinementService.apply_corrections`; speaker corrections would tighten to high-only given the risk). Deferred to post-launch observation.

## Dependencies on already-shipped Plans

- **Plan 1** (A1/A2/A3, B1/B2/B3/B4/B5/B8): all preserved. A1/A2/A3 stay wired to Whisper. B1/B2/B3/B4 refinement infrastructure used by the new orchestrator. B5 inline auto-match unchanged. B8 docs/engines.md gets deleted (Sub-plan D).
- **Plan 2** (B7 learning system): all preserved. Continues to fire after refinement done. The Plan 3 Task 2 overlay fix is essential.
- **Plan 3** (B6 UX surfaces): all preserved EXCEPT the engine-asymmetry patches (c5e4a53, 4f57b10) which are removed by Sub-plan D.
