# Davrine Transcription — Continuous Improvement Foundation (B' v2)

**Status**: Draft for implementation
**Date**: 2026-05-15
**Scope**: Backend refinement pipeline + learning system + Voxtral default + frontend UX surface for the new capabilities
**Sequel to**: `2026-05-15-davrine-transcription-pipeline-fixes-design.md` (A1/A2/A3, now merged)

## Context

After A1/A2/A3 shipped, the Pascal Weber call validation showed Whisper now produces clean speaker turns, correct language detection, and zero hallucinations of the 4 baseline types. Three proper-noun errors survived ("Manukai" → "Manuk AI", "DMG Mori" → "BMG Mori", "Starrag" → "Stara") because the LLM refinement layer never receives the user-provided speaker context or domain glossary — so it can't fix what it doesn't know.

This spec closes that loop and turns the app from a passive transcriber into a **self-improving system**: every transcription updates the speaker registry's voice profile, extracts insights into the speaker dossier, learns new glossary terms from corrections, and surfaces what it learned to the user for review.

## Goals

1. **Proper-noun corrections** — "Manukai", "DMG Mori", "Starrag" appear correctly in the refined transcript on the existing test audio.
2. **Zero-click refinement** — when the user has selected speakers or a context document, the refinement pass runs automatically post-completion.
3. **Continuous learning** — each transcription improves the system's knowledge:
   - Speaker voice profile (rolling-average embedding update)
   - Speaker dossier (auto insights extraction)
   - Domain glossary (high-confidence corrections appended to `contexts/_global.md` for user review)
4. **Best local model by default** — `voxtral-realtime-4b` is the default `model_size` when `engine=voxtral-local`. A1/A2/A3 remain available for the Whisper engine.
5. **UX legibility** — the user can see what's happening (refinement in progress, auto-match confidence) and what was learned (post-job summary, pending-review glossary terms).

## Non-Goals

- No new model fine-tuning
- No new external services beyond the Anthropic API already used by `refinement.py` via the `claude` CLI
- No UI redesign of unrelated tabs (Recordings, Jobs, etc.) — only the surfaces directly impacted by B1-B8
- No Voxtral / Parakeet path modifications beyond the default model_size change (B8). A1/A2/A3 remain Whisper-only
- No changes to authentication, deployment, or the JPR watcher

## Design

### B1 — Refinement receives speaker context + context document + global glossary

**Files**: `backend/services/refinement.py`, `backend/routes/refinement.py`, `backend/job_models.py` (read-only)

**Change**:

- `RefinementService.analyze(segments, context_text=None, glossary_terms=None)` — two new optional parameters
- `RefinementService.refine(segments, context_text=None, glossary_terms=None)` — propagates the new params to `analyze`
- The Claude prompt is reshaped: when `context_text` or `glossary_terms` is provided, prepend a `## Known context` block listing the speaker bios + context doc + glossary terms, followed by an explicit instruction:

```
The following terms ARE present in the audio's domain. If you find any
misspelling of these in the transcript, correct it with confidence=high:

[Manukai, Pascal Weber, Daniel, Starrag, DMG Mori, Siemens, ETH, ...]

Speaker context:
[contents of speaker profiles + context.md merged]
```

- `routes/refinement.py:_run_refinement` is updated to load the same context bundle that `transcription.py` already loads (`load_speakers_context`, `load_context_document`, `derive_context_terms`, plus the new global glossary loader from B4). Reuse the existing helpers; do not duplicate.
- Subprocess timeout in `_run_claude` raised from 120 to **300 seconds** (Sonnet on full-length transcripts typically takes 60-180s; 300s leaves margin under load. No retry path today — accept the timeout as a hard failure, log it, mark `refinement_status=failed`).

**Why this works**: Claude already has the corrections schema; we're just feeding it the data it needs to decide *correctness*. The existing `confidence` field in the JSON schema does the rest — high-confidence corrections get applied, low-confidence ones don't.

### B2 — Auto-run refinement on completion

**Files**: `backend/services/transcription.py:_run_transcription_sync`, `backend/job_models.py`, `backend/routes/transcription.py`

**Change**:

- Add `auto_refine: Optional[bool] = None` to `TranscriptionSettings` (in `job_models.py`). `None` = default behavior (auto if `speaker_ids` or `context_path` provided, else no). `True` / `False` = explicit override.
- After `_update_job(job, progress=100, message="Complete!", status="completed")` in `_run_transcription_sync`, dispatch refinement as a background task:

```python
should_auto_refine = (
    settings.auto_refine is True
    or (settings.auto_refine is None and (settings.speaker_ids or settings.context_path))
)
if should_auto_refine and state.refinement_available:
    # Use the same executor pattern as A1/A2/A3 background work, NOT
    # FastAPI BackgroundTasks (the request that submitted the job has
    # long returned). The existing manual route /refine/job/{id} delegates
    # to `_run_refinement(job_id)` — extract the shared body into
    # routes/refinement.py:_run_refinement_for_job(job_id) so both callers
    # (manual route + auto-trigger here) share one implementation.
    state.transcription_executor.submit(
        _run_refinement_for_job, job_id, settings.speaker_ids, settings.context_path
    )
```

- New fields on `TranscriptionJob` (in `job_models.py`):
  - `refinement_status: Optional[str] = None` — tracks auto-refine state (`pending`, `processing`, `done`, `failed`)
  - `auto_speaker_matches: Optional[Dict[str, Dict]] = None` — populated by B5 inline auto-match
  - `learning_summary: Optional[Dict[str, int]] = None` — populated by B7 after refinement completes; keys: `embeddings_updated`, `insights_added`, `terms_learned`
  - `learning_status: Optional[str] = None` — `ok` (≥1 worker succeeded), `partial` (some workers failed), `failed` (all workers failed). Distinguishes "ran but learned nothing" from "all workers crashed".
- All four fields are serialized by the existing `/job/{job_id}` GET response. UI polls this for indicators (B6).

**Why not block the job completion on refinement**: the job is *transcribed* even before refinement; users can read the verbatim immediately. Refinement is an enhancement, not a gate.

### B3 — Sonnet 4.6 for refinement

**Files**: `backend/services/refinement.py:103`

**Change**: `--model haiku` → `--model sonnet`. That's it for B3 itself.

**Rationale**: Sonnet is significantly more reliable on careful proper-noun reasoning. Cost is marginal (~$0.01 per job on the user's Anthropic Max plan; an order of magnitude under Whisper compute time). Latency adds 20-40s per job, acceptable post-completion.

### B4 — Persistent global glossary

**Files**: new `backend/services/glossary.py` (small focused module), `backend/services/transcription.py`, `backend/routes/contexts.py`

**Change**:

- New helper module `backend/services/glossary.py`:

```python
def load_global_glossary() -> Optional[str]:
    """Read ICLOUD_BASE/contexts/_global.md if present. Returns None
    if missing or empty. Never raises."""

def load_global_glossary_terms() -> List[str]:
    """Same as above but returns the extracted proper-noun terms only,
    used to populate glossary_terms in the refinement call."""

def append_auto_learned_term(term: str, source_job_id: str, context_phrase: str) -> None:
    """Append a term to the '## Auto-learned terms (pending review)' section
    of _global.md. Creates the section if missing. Idempotent — won't
    duplicate an existing term (case-insensitive match)."""
```

- `merge_context_sources()` in `transcription.py` becomes the single composition point, always prepending the global glossary content before the context doc and speaker context. Order of priority: global → context_path → speakers.
- `contexts/_global.md` ships with a documented template (see "Initial deliverables" section below).
- `routes/contexts.py` gets two endpoints:
  - `GET /contexts/_global` — returns the file contents + metadata (modified date, term count)
  - `PUT /contexts/_global` — accepts a markdown payload, atomically rewrites the file
- UI surface: B6 covers the editor view.

**Why a section in one file vs many files**: keeps the glossary a single artifact that's easy to edit, version (via iCloud history), and inspect. The "pending review" subsection draws a clear boundary between user-curated and auto-learned content.

### B5 — Auto-match speakers via embedding (inline, post-diarization)

**Files**: `backend/services/transcription.py`, `backend/job_models.py`

**Important**: `auto_identify_speakers()` is **already implemented** at `backend/services/speaker_embedding.py:357-442` with full scoping logic (`restrict_to_ids`, `prefer_ids`, unknown staging, source tagging). It's already wired to the post-job endpoint `POST /job/{job_id}/speakers/auto-identify` (`routes/transcription.py:1274`). The scope resolver `_resolve_match_scope` (`routes/transcription.py:1217`) decides between strict-restrict and bias-prefer modes.

**B5's actual change** — call the existing service **inline during `_run_transcription_sync`** instead of waiting for a separate manual API call:

```python
# After diarization joins and A3 segment-to-speaker assignment:
if speakers and state.refinement_available:  # service depends on embedding extractor
    restrict_ids, prefer_ids, _scope_label = _resolve_match_scope({
        "speaker_ids": settings.speaker_ids,
    })
    try:
        auto_matches = state.embedding_service.auto_identify_speakers(
            audio_path=audio_path,           # original audio, not trimmed
            speaker_turns=speakers,
            job_id=job_id,
            restrict_to_ids=restrict_ids,
            prefer_ids=prefer_ids,
        )
        job.auto_speaker_matches = auto_matches  # for UI
        # Apply matches to segments — replace SPEAKER_XX with name when matched=True
        for seg in transcription_segments:
            lbl = seg.get("speaker", "")
            m = auto_matches.get(lbl)
            if m and m.get("matched"):
                seg["speaker"] = m["name"]
    except Exception:
        logger.exception("Auto-match failed for job %s; keeping SPEAKER_XX labels", job_id)
```

- `TranscriptionJob.auto_speaker_matches: Optional[Dict[str, Dict]] = None` field added — exact shape returned by `auto_identify_speakers`.
- **Precedence rule, explicit**: when `settings.speaker_ids` is provided, the existing `_resolve_match_scope` returns `restrict_to_ids=speaker_ids` (strict-scope mode). The auto-match then only picks names from that set. When `speaker_ids` is empty, the resolver returns `(None, None, "all")` and the matcher searches the full registry. This matches today's manual `/job/{id}/speakers/auto-identify` route behavior — same semantics, just inline.
- B5 implementation: ~30 lines in `_run_transcription_sync` + the field declaration. The bulk of the heavy lifting was already done.

### B6 — UX audit + improvements

**Files**: a frontend audit document (`docs/superpowers/audits/2026-05-15-ux-touchpoints.md`) drives concrete React/TypeScript changes across `src/components/*.tsx`.

**Audit scope** (executed as the first task of plan 3):

For each B1-B5 capability, document the impacted user touchpoints:

| Capability | Surface | Current state | Desired state |
|---|---|---|---|
| B1 (refinement gets context) | Refinement modal/view | Same as before | Indicate which context sources fed the refinement run |
| B2 (auto-refinement) | Transcript view, job list | No indicator | Spinner + "Refining…" badge while running; "Refined" badge when done |
| B3 (Sonnet) | None (model is internal) | N/A | N/A |
| B4 (global glossary) | Contexts tab | No editor | New `_global.md` editor (similar to existing context doc editor), with section split: "Active" vs "Pending review (auto-learned)" |
| B5 (auto-match) | Transcript view, SpeakersView | Speakers labeled SPEAKER_00/01 | Auto-matched names rendered with a "(auto · 87%)" subtle tag; click → Accept (locks it) / Reject (reverts to SPEAKER_XX) |
| B7 (learning) | Job completion toast | None | Post-job toast: "Learned: 3 new glossary terms (review), updated 2 speaker embeddings, +5 insights" |
| B7 (learning log) | New "Activity" entry under Contexts or Speakers tab | None | Read-only timeline of `learning_log.jsonl` events with filter by speaker / type / date |

**Concrete implementations** (each is a sub-task in plan 3):

- **B6a** — Refinement-status indicator in the existing `TranscriptView` and job list. Polls `/job/{id}` every 5s while `refinement_status in (pending, processing)`.
- **B6b** — Auto-match badges on speaker labels in `TranscriptView`. Two-action menu: Accept / Reject. Accept calls `/job/{id}/speakers/assign` with the auto-matched speaker_id.
- **B6c** — `_global.md` editor: new component `GlobalGlossaryEditor.tsx` mounted under the Contexts tab. Renders the file with two sections; allows manual edit of "Active", review-and-promote of "Pending review" items.
- **B6d** — Post-job "What was learned" toast. Shows a summary of the `learning_log` entries created for this job_id, with a "Review" link to the Activity timeline (B6e).
- **B6e** — Activity timeline. New tab or sub-view. Reads `learning_log.jsonl` (new backend endpoint `GET /learning/log?since=...&type=...`).
- **B6f** — SettingsPanel progressive disclosure: group advanced options (temperature ladder details, model_size, two_pass) under a collapsed "Advanced" accordion. Default closed.

### B7 — Continuous learning system

**Files**: new `backend/services/learning.py`, hooks into `backend/services/transcription.py` and `backend/services/refinement.py`, new route `backend/routes/learning.py`

**Change**: a thin orchestration layer that runs *after* refinement completes (so corrections have already landed in segments). Three workers, all fail-safe (any one failing must not block the others; log + continue).

```python
# backend/services/learning.py

def record_event(event_type: str, **fields) -> None:
    """Append a JSON line to ICLOUD_BASE/learning_log.jsonl. Never raises."""

def update_speaker_embeddings(job_id: str, audio_path: str, speaker_turns: List[dict],
                              assignments: Dict[str, str]) -> int:
    """For each pyannote label `lbl` mapped to a registered speaker name in
    `assignments` (manual `speaker_ids` or B5 auto-match with matched=True),
    if total speaking duration is >= 60s, extract a fresh embedding from
    the audio across that speaker's turns and merge it into the registry
    via the existing EMA pattern:

        embedding_service.update_embedding(name, new_embedding, alpha=0.3)

    This reuses speaker_embedding.py:279 (the same path used today by
    routes/transcription.py post-call). Don't reinvent the math; just
    move the trigger from manual to automatic.

    Returns count of speakers updated. Records 'embedding_update' events."""

def extract_insights_auto(job_id: str, segments: List[dict], registry) -> int:
    """For each speaker with >= 60s of speech, call the existing
    /speakers/{id}/extract-insights logic in-process (not via HTTP).
    Append new insights to explicit_insights.md and implicit_insights.md.
    Returns count of new insights added. Records 'insight_added' events."""

def learn_glossary_terms(job_id: str, corrections: List[dict]) -> int:
    """For each refinement correction with confidence='high', check if the
    corrected term appears in any existing context document (global,
    context_path, speaker bios). If not, append to the 'Auto-learned
    (pending review)' section of contexts/_global.md.
    Returns count of new terms learned. Records 'glossary_add' events."""
```

**Orchestrator**: at the end of `_run_refinement_for_job` (B2's background task), after corrections are applied:

```python
def _run_post_refinement_learning(job_id: str, audio_path: str, segments: List[dict], analysis: dict):
    successes = 0
    failures = 0
    emb_count = ins_count = glo_count = 0

    # Build assignments map {pyannote_label: speaker_name} from segments
    assignments = {seg.get("speaker"): seg.get("speaker") for seg in segments if seg.get("speaker") and not seg["speaker"].startswith("SPEAKER_")}

    try:
        emb_count = learning.update_speaker_embeddings(job_id, audio_path, segments, assignments)
        successes += 1
    except Exception:
        logger.exception("Embedding update failed for job %s", job_id)
        failures += 1
    try:
        ins_count = learning.extract_insights_auto(job_id, segments, state.speaker_store)
        successes += 1
    except Exception:
        logger.exception("Insights extraction failed for job %s", job_id)
        failures += 1
    try:
        glo_count = learning.learn_glossary_terms(job_id, analysis.get("corrections", []))
        successes += 1
    except Exception:
        logger.exception("Glossary learning failed for job %s", job_id)
        failures += 1

    # Stamp learning_summary + learning_status onto the job for UI polling
    job = state.jobs.get(job_id)
    job.learning_summary = {
        "embeddings_updated": emb_count,
        "insights_added": ins_count,
        "terms_learned": glo_count,
    }
    if successes == 3:
        job.learning_status = "ok"
    elif successes >= 1:
        job.learning_status = "partial"
    else:
        job.learning_status = "failed"
    state.jobs.update(job)
```

**`learning_log.jsonl` location**: `~/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/learning_log.jsonl` (iCloud — cross-device, version-historied). Append-only, never edited in place. **Concurrency**: `record_event` must hold an `fcntl.LOCK_EX` advisory lock during open+append+close; iCloud has no transactional guarantees. Followed by `fsync()` to ensure the line is on disk before unlocking.

**Glossary append normalization**: idempotent term matching uses case-insensitive comparison **plus** Unicode normalization (NFC), whitespace collapse, and trailing-punctuation strip. "DMG Mori" ≡ "DMG  Mori" ≡ "dmg mori." for de-dup purposes — but the canonical form (first-seen casing/spacing) is what gets stored.

**Schema** (one JSON object per line):
```json
{"ts": "2026-05-15T13:51:39Z", "job_id": "...", "type": "embedding_update", "speaker_id": "...", "speaker_name": "...", "duration_sec": 245.3}
{"ts": "...", "job_id": "...", "type": "glossary_add", "term": "Manukai", "source_phrase": "...", "confidence": "high"}
{"ts": "...", "job_id": "...", "type": "insight_added", "speaker_id": "...", "category": "explicit|implicit", "count": 3}
```

**Endpoint**: `GET /learning/log?since=...&type=...` (paginated, used by B6e Activity timeline)

### B8 — Voxtral default (confirmed already set) + engine compatibility doc

**Audit result (already verified)**: `backend/job_models.py:380` sets `model_size: str = "voxtral-realtime-4b"` and `engine: str = "voxtral-local"` as the `TranscriptionSettings` defaults. Commit `261ddf9 Add Voxtral Realtime 4B as default local engine` already landed this. **No code change needed for B8**.

**B8's actual change** — ship the engine-compatibility documentation table (below) so users understand which fixes apply to which engine. Add it to the README or a new `docs/engines.md`. ~5 lines of YAML/Markdown total.

**Engine compatibility documentation**: a new section in the project README (or `docs/engines.md`) clarifying:

| Capability | Whisper | Voxtral Local | Voxtral API | Parakeet |
|---|---|---|---|---|
| A1 decoding params | ✅ applied | ❌ N/A (different engine) | ❌ N/A | ❌ N/A |
| A2 VAD trim | ✅ applied | ❌ skipped (reads full audio) | ❌ skipped | ❌ skipped |
| A3 word-boundary speaker split | ✅ when words emitted | ⚠️ midpoint fallback | ⚠️ uses Voxtral's own diarization | ⚠️ midpoint fallback |
| B1-B7 (refinement, glossary, learning) | ✅ engine-agnostic | ✅ | ✅ | ✅ |

## Data flow (after B' v2, Whisper engine)

```
audio file + speaker_ids + context_path + auto_refine
     │
     ├── diarization (pyannote, original audio) ──► turns + embeddings
     │                                                        │
     │                                              [B5] auto-match
     │                                                        │
     ├── VAD trim (A2) ──► trimmed audio
     │                                                        │
     ├── load context bundle:                                  │
     │     [B4] global glossary                                │
     │     + context.md (if path)                              │
     │     + speakers profile.md/explicit/implicit             │
     │     ↓                                                   │
     │   initial_prompt (Whisper, A1 params)                   │
     │                                                        │
     ├── Whisper (A1) ──► segments + words ──► A3 split ──► stitch
     │                                                        │
     │                                              [B5 auto-match overlay]
     │                                                        │
     ├── normalize + (optional) readable ──► verbatim segments
     │                                                        │
     ├── job.status = completed
     │                                                        │
     └── [B2] if auto_refine: ──┐
                                ▼
            [B3 Sonnet 4.6] Refinement:
              transcript + context bundle + glossary terms + explicit instruction
              ──► corrections + speaker label mapping (already SPEAKER_XX → name from B5)
                                ▼
            apply_corrections + speaker_mapping
                                ▼
            [B7] _run_post_refinement_learning:
              ├── update_speaker_embeddings (rolling avg)
              ├── extract_insights_auto (Sonnet, append to dossier)
              └── learn_glossary_terms (auto-append to _global.md pending section)
                                ▼
            job.refinement_status = done, job.learning_summary set
                                ▼
            UI polls and renders "What was learned" toast
```

## Initial deliverables

- **`contexts/_global.md` template** (ship with empty repo, never overwrite if exists):

```markdown
# Global Glossary

Terms in this document are auto-injected into every transcription's
initial_prompt and into the refinement LLM's known-context block.

## Active

(Add domain-specific proper nouns, company names, jargon, etc.)

## Auto-learned (pending review)

(High-confidence corrections from refinement runs land here.
Review each item, then move it to a section above or delete it.)
```

## Testing strategy

Per-task tests are detailed in each plan. High-level coverage:

- **B1**: prompt-construction unit — verify the `## Known context` block appears in the prompt when context is provided, with the exact glossary terms and speaker bios; verify it's omitted when no context
- **B2**: orchestrator unit — verify auto_refine triggers when `auto_refine is None and speaker_ids` is set; doesn't trigger when `auto_refine=False`; doesn't trigger when refinement service unavailable
- **B3**: subprocess args unit — verify `--model sonnet` and `timeout=240` are passed
- **B4**: glossary helper unit — verify load, term extraction, idempotent append
- **B5**: auto-match unit — verify cosine similarity correctness against fixture embeddings, threshold honored
- **B6**: frontend Playwright e2e — verify the refinement indicator appears and clears; verify the auto-match badge renders with confidence; verify the toast appears on completion
- **B7**: learning unit — verify rolling-average embedding math; verify idempotent glossary append; verify learning_log line shape
- **B8**: config audit — verify default model_size, append audit note to this spec doc
- **End-to-end manual validation**: re-run the Pascal Weber call with all of B' enabled. Acceptance criteria: "Manukai", "DMG Mori", "Starrag" appear correctly in the refined transcript. `learning_log.jsonl` has new entries. `_global.md` has new pending-review terms.

## Open Questions (resolved)

| Question | Decision |
|---|---|
| Embedding update: rolling avg vs buffer of N? | **Duration-weighted rolling average** — simpler, more stable across recording conditions |
| Glossary auto-add: direct vs pending review section? | **Pending review section** in `_global.md` — clean separation from user-curated content |
| `learning_log.jsonl` location: local vs iCloud? | **iCloud** — cross-device, version-historied via iCloud |
| Refinement timeout for Sonnet on long transcripts | **300 seconds** (up from 120) — leaves margin under load; no retry path |
| `auto_refine` default behavior | `None` → auto-on when `speaker_ids` or `context_path` is provided, else off |

## Out of scope (post-B', future)

- Fine-tuning Whisper on user's voice for specific recurring speakers
- Real-time partial transcription (currently batch-only)
- Multi-user / shared glossary across teams
- Public glossary marketplace ("import VC pitch glossary", "import legal glossary", etc.)

## Three plans (sequenced)

This spec maps to three implementation plans, executed in order. Each plan ships independently, gets manual validation, before the next plan starts.

1. **Plan 1 — Backend foundation**: B4 (glossary helper + ship template `_global.md`) → B1 (refinement receives context — depends on B4's loader) → B3 (Sonnet + 300s timeout) → B2 (auto-run wiring with executor pattern) → B5 (inline auto-match call, ~30 lines reusing existing service) → B8 (ship engine-compatibility doc, 5 lines). ~5-6 tasks.
2. **Plan 2 — Learning system (B7)**: post-refinement learning orchestrator with three failure-isolated workers, `learning_log.jsonl` with fcntl locking, GET `/learning/log` route, glossary append normalization. ~4-5 tasks.
3. **Plan 3 — UX (B6 — audit first, then implementations)**: **Task 1 produces `docs/superpowers/audits/2026-05-15-ux-touchpoints.md` and gates all subsequent tasks** (Tasks 2-7 cannot start until Task 1 is reviewed and accepted by the user). Then in order: B6a refinement indicator, B6b auto-match badges + accept/reject, B6c `_global.md` editor, B6d post-job toast, B6e activity timeline, B6f settings progressive disclosure. ~7 tasks.

Manual validation gate at the end of each plan re-runs the Pascal Weber audio (or a representative sample) to measure progress against the proper-noun acceptance criterion.

**Cross-plan dependencies**:
- Plan 2 depends on Plan 1 (B7 reads `analysis["corrections"]` from B1's refinement output and uses `auto_speaker_matches` from B5)
- Plan 3 depends on Plan 1 + Plan 2 (UI reads `refinement_status`, `auto_speaker_matches`, `learning_summary`, `learning_status`, `learning_log.jsonl`)
