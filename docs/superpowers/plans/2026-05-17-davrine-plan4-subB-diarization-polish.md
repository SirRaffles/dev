# Plan 4 Sub-plan B — Semantic Diarization Polish (Combo C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `RefinementService.analyze` to emit a `speaker_corrections` array (Sonnet's semantic re-attribution of speakers based on conversational turn-taking and sentence-boundary semantics), and extend `apply_corrections` to apply those corrections to refined segments — improving diarization quality on every engine without waiting for the Plan 4 Sub-plan A orchestrator.

**Architecture:** This sub-plan is a pure backend extension of the existing Plan 1 refinement pipeline. The Sonnet call already produces structured JSON with `corrections`, `speakers`, and `uncertain_terms`; we add a fourth optional field `speaker_corrections` (alongside, not replacing) and a new `## Diarization context` prompt block that is only emitted when pyannote turn data is passed in. `apply_corrections` gains a hard-guardrail loop that mutates `seg.speaker` per the new array — and never touches `seg.text`. The caller `_run_refinement_for_job` already builds `speaker_turns` for B7 learning; we route the same list into `refine` so Sonnet sees the diarization context.

**Tech Stack:** Python 3.11, FastAPI (existing), Claude CLI Sonnet (existing), pytest with `unittest.mock.patch` for prompt-construction and apply-correction tests (existing fixture pattern in `backend/tests/test_refinement_context.py`).

---

## Context for the implementer

Read these before starting:

1. **The spec** — `docs/superpowers/specs/2026-05-17-davrine-quality-dial-orchestration-design.md`, sections:
   - "Combo C — Semantic Diarization Polish (universal refinement step)" (lines 97-142)
   - "Sub-plan B — Combo C semantic diarization polish" (lines 356-364)
   - "Out of Scope" → bullet on confidence field (line 489)

2. **Current refinement surface** — `backend/services/refinement.py`. Key shapes you'll touch:
   - `ANALYSIS_SCHEMA` (lines 22-69) — the JSON schema string Sonnet's response is validated against. Today: `language`, `domain`, `summary`, `speakers`, `corrections`, `uncertain_terms`.
   - `RefinementService.analyze(self, segments, context_text=None, glossary_terms=None) -> dict` (lines 209-268) — builds the prompt, calls `_run_claude`, returns parsed JSON. Plan 1's B1 added `context_text` + `glossary_terms` kwargs and the conditional `## Known context` block (lines 226-240). We follow the same pattern.
   - `RefinementService.apply_corrections(self, segments, analysis) -> tuple` (lines 344-388) — deepcopies segments, builds `speaker_mapping` from `analysis["speakers"]`, applies text corrections, applies the SPEAKER_XX → name relabel. Returns `(refined_segments, speaker_mapping, corrections_count)`. We extend the per-segment loop with a speaker_corrections application step.
   - `RefinementService.refine(self, segments, context_text=None, glossary_terms=None) -> dict` (lines 390-450) — full pipeline. We add a `speaker_turns=None` kwarg that is forwarded to `analyze`.

3. **Caller** — `backend/routes/refinement.py` lines 102-124 already construct a `speaker_turns` list (the exact shape we want: `[{"start": float, "end": float, "speaker": str}, ...]`) for the B7 learning workers. The same list needs to be threaded into `refine`. The construction is currently inside `_run_post_refinement_learning`; we lift the build logic so `_run_refinement_for_job` builds it once and passes to both `refine` (NEW) and `_run_post_refinement_learning` (existing).

4. **Diarization helper** — `backend/services/diarization.py:assign_speakers_to_segments` (lines 146-222) is the existing function that produces the segment.speaker assignments we're polishing. No change to this module in Sub-plan B — Sonnet polishes the *output* of this function.

5. **Test fixture pattern** — `backend/tests/test_refinement_context.py`. The `_stub_run_claude_capture` helper (lines 12-25) is the canonical pattern: patch `services.refinement._run_claude`, capture the prompt, return a minimal valid JSON dict. We follow the same shape for the new prompt-construction tests.

## Design decisions already settled (do not re-litigate)

- **One Sonnet call, not two.** `speaker_corrections` rides alongside `corrections` and `speakers` in the existing JSON response. No new endpoint, no second prompt round-trip.
- **Hard guardrail in `apply_corrections`.** Speaker_corrections can mutate `seg["speaker"]` ONLY. The text-correction path is the only thing that may touch `seg["text"]`. Enforced by structure: the new loop reads from `analysis["speaker_corrections"]` and writes `seg["speaker"]`, period.
- **Conditional prompt block.** The `## Diarization context` section is emitted only when `speaker_turns` is non-empty. Callers (including the legacy `/refine/job/{id}` manual route which doesn't have access to speaker_turns conveniently) that pass `None` get the existing behavior — full backward compat.
- **Sonnet response may omit `speaker_corrections`.** Older model output, prompt drift, or a transcript where no corrections apply → field absent → no speaker changes, existing diarization stays untouched. `apply_corrections` defaults to `analysis.get("speaker_corrections", [])`.
- **Turn list capped at 50 entries.** Per spec, "full list, capped at ~50 turns for prompt budget". Cap is `[:50]` — first 50 turns by audio order. Long recordings with many turns get the head of the list; this is acceptable since most mis-attribution errors cluster around interruptions in the early dense sections.
- **No `confidence` field on speaker_corrections in v1.** Honor-system prompt ("Only emit corrections you're confident in"). Out-of-scope per spec line 489. If false-positives become an issue, add a `confidence: "high"|"medium"|"low"` filter post-launch.
- **`segment_index` is an integer index into the segments list passed to `analyze`.** Out-of-range indexes are silently skipped in `apply_corrections` (defensive — Sonnet might hallucinate an index).

## File structure

**Modify:**
- `backend/services/refinement.py` — add `speaker_corrections` to `ANALYSIS_SCHEMA`; add `speaker_turns` kwarg to `analyze` + emit the conditional `## Diarization context` prompt block; extend `apply_corrections` with a speaker-only mutation loop; add `speaker_turns` kwarg to `refine` and forward it.
- `backend/routes/refinement.py` — `_run_refinement_for_job` builds `speaker_turns` from `job.speakers` (or falls back to segment-derived turns) and passes it to `refine`. Lift the existing turn-build logic out of `_run_post_refinement_learning` into a small helper used by both callers, OR duplicate the 7-line build in `_run_refinement_for_job` (the second is simpler and reviewed by the implementer). See Task 4.

**Create:**
- (no new files — all changes land in the two existing modules)

**Modify (tests):**
- `backend/tests/test_refinement_context.py` — add tests for: schema includes `speaker_corrections`; prompt omits the diarization block when `speaker_turns` is `None` or `[]`; prompt includes the diarization block when `speaker_turns` is provided; `analyze` returns `speaker_corrections` from Sonnet's response untouched; `apply_corrections` mutates speaker per speaker_corrections; `apply_corrections` NEVER touches text via the speaker_corrections path; `apply_corrections` silently skips out-of-range indexes; `apply_corrections` is a no-op when `speaker_corrections` is absent from analysis; `refine` propagates `speaker_turns` to `analyze`.

**Reference (read for context, do not modify):**
- `docs/superpowers/specs/2026-05-17-davrine-quality-dial-orchestration-design.md` — full spec.
- `backend/services/diarization.py` — `assign_speakers_to_segments` produces the segments whose `speaker` field we're polishing.
- `backend/job_models.py` — `TranscriptionJob.speakers` is the pyannote turn list `_run_refinement_for_job` reads.

## Conventions

- **TDD discipline.** Each task: write failing test → run red → implement → run green → commit. No shortcuts.
- **Tests use the existing `_make_service()` + `_stub_run_claude_capture(captured)` pattern** from `backend/tests/test_refinement_context.py`. Do not invent new fixture mechanics.
- **Patch target** is `services.refinement._run_claude` (the module-level function), not `RefinementService._run_claude` (it's not a method).
- **Backend runs from `backend/` cwd.** All `pytest` commands run from there: `cd backend && python -m pytest ...`. The launchd-managed dev server uses `~/Development/apps/whisper-transcription-app/backend/venv`.
- **Commit per task.** Each task ends with a single `git commit` (no `git add -A`). Stage only the files listed in the task's `Files:` block.
- **No formatting churn.** Edits use `Edit` tool with exact-match strings — do not reflow surrounding code.
- **Backward-compat default.** Every new kwarg defaults to `None` (or `[]` for collections where idiomatic). The `_run_refinement` legacy wrapper (line 269 of `routes/refinement.py`) does NOT need to be touched — it'll just call `_run_refinement_for_job` which builds its own `speaker_turns` from `state.jobs.get(job_id)`.

---

## Tasks

### Task 1: Extend `ANALYSIS_SCHEMA` with `speaker_corrections`

**Files:**
- Modify: `backend/services/refinement.py:22-69` (the `ANALYSIS_SCHEMA` constant)
- Test: `backend/tests/test_refinement_context.py`

The JSON schema string defines the structure Sonnet's response is validated against. Today it has `language`, `domain`, `summary`, `speakers`, `corrections`, `uncertain_terms`. We add an optional `speaker_corrections` array of `{segment_index, speaker, reason}` objects. The field stays out of the `required` list (Sonnet may omit it when no corrections apply or when the prompt block was suppressed).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_refinement_context.py`:

```python
def test_analysis_schema_includes_speaker_corrections():
    """The exported schema must declare speaker_corrections so Sonnet's
    output is recognized as valid when the field is present."""
    import json
    from services.refinement import ANALYSIS_SCHEMA

    schema = json.loads(ANALYSIS_SCHEMA)
    props = schema["properties"]
    assert "speaker_corrections" in props, (
        "ANALYSIS_SCHEMA must declare speaker_corrections for Combo C diarization polish"
    )
    sc = props["speaker_corrections"]
    assert sc["type"] == "array"
    item = sc["items"]
    assert item["type"] == "object"
    assert set(item["required"]) == {"segment_index", "speaker", "reason"}
    assert item["properties"]["segment_index"]["type"] == "integer"
    assert item["properties"]["speaker"]["type"] == "string"
    assert item["properties"]["reason"]["type"] == "string"
    # speaker_corrections must NOT be in top-level required — it's optional
    assert "speaker_corrections" not in schema["required"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py::test_analysis_schema_includes_speaker_corrections -v`

Expected: FAIL with `KeyError: 'speaker_corrections'` or `AssertionError`.

- [ ] **Step 3: Extend `ANALYSIS_SCHEMA`**

Edit `backend/services/refinement.py`. Find the existing `uncertain_terms` block at the end of `properties` (lines 62-66):

```python
        "uncertain_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Terms that may be misspelled but need web verification"
        }
    },
    "required": ["language", "domain", "summary", "speakers", "corrections", "uncertain_terms"]
})
```

Replace with:

```python
        "uncertain_terms": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Terms that may be misspelled but need web verification"
        },
        "speaker_corrections": {
            "type": "array",
            "description": "Semantic re-attribution of mis-assigned speakers (Combo C). Optional; absent when no corrections apply.",
            "items": {
                "type": "object",
                "properties": {
                    "segment_index": {"type": "integer", "description": "0-based index into the segments array passed to analyze()"},
                    "speaker": {"type": "string", "description": "Corrected speaker label (e.g. SPEAKER_01 or an identified name)"},
                    "reason": {"type": "string", "description": "Brief justification, e.g. 'mid-sentence interjection by Pascal'"}
                },
                "required": ["segment_index", "speaker", "reason"]
            }
        }
    },
    "required": ["language", "domain", "summary", "speakers", "corrections", "uncertain_terms"]
})
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py::test_analysis_schema_includes_speaker_corrections -v`

Expected: PASS.

- [ ] **Step 5: Run the full refinement-context suite to confirm no regression**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -v`

Expected: ALL PASS (including the 6 pre-existing tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app
git add backend/services/refinement.py backend/tests/test_refinement_context.py
git commit -m "$(cat <<'EOF'
Plan 4B Task 1: extend ANALYSIS_SCHEMA with speaker_corrections

Adds the optional speaker_corrections array to the Sonnet response schema
for Combo C semantic diarization polish. Each entry is
{segment_index: int, speaker: str, reason: str}. The field stays out of
the top-level required list so older model outputs and no-correction
cases stay valid.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add `speaker_turns` kwarg + conditional `## Diarization context` prompt block to `analyze`

**Files:**
- Modify: `backend/services/refinement.py:209-268` (the `RefinementService.analyze` method)
- Test: `backend/tests/test_refinement_context.py`

The `analyze` method gains a `speaker_turns: Optional[List[dict]] = None` kwarg. When non-empty, it emits a `## Diarization context` block (preceding or after `## Known context`, doesn't matter functionally — pick after `## Known context` so the diarization block is closer to the transcript text in the prompt). The block lists turns capped at 50 entries.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_refinement_context.py`:

```python
def test_analyze_omits_diarization_block_when_no_speaker_turns():
    """Backward compat: callers that don't pass speaker_turns get the
    original prompt with no Diarization context section."""
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze([{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])
    assert "## Diarization context" not in captured["prompt"]
    assert "Pyannote detected" not in captured["prompt"]
    assert "speaker_corrections" not in captured["prompt"]


def test_analyze_omits_diarization_block_when_speaker_turns_empty():
    """Empty list is treated identically to None — no block emitted."""
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=[],
        )
    assert "## Diarization context" not in captured["prompt"]


def test_analyze_injects_diarization_block_when_speaker_turns_provided():
    """When pyannote turns are passed, the prompt must include the
    Diarization context block, the turn list, and the speaker_corrections
    instruction."""
    svc = _make_service()
    captured = {}
    turns = [
        {"start": 2.4, "end": 15.7, "speaker": "SPEAKER_00"},
        {"start": 15.7, "end": 18.2, "speaker": "SPEAKER_01"},
        {"start": 18.2, "end": 32.1, "speaker": "SPEAKER_00"},
    ]
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=turns,
        )
    prompt = captured["prompt"]
    assert "## Diarization context" in prompt
    assert "Pyannote detected" in prompt
    # Turn timestamps formatted as [start s - end s] with speaker label
    assert "SPEAKER_00" in prompt
    assert "SPEAKER_01" in prompt
    assert "2.40" in prompt or "2.4" in prompt
    assert "15.70" in prompt or "15.7" in prompt
    # The instruction telling Sonnet what to emit
    assert "speaker_corrections" in prompt
    assert "Do NOT rewrite segment text" in prompt


def test_analyze_caps_diarization_turns_at_50():
    """Prompt budget protection: only the first 50 turns appear in the
    Diarization context block, even if more are passed."""
    svc = _make_service()
    captured = {}
    turns = [
        {"start": float(i), "end": float(i + 1), "speaker": f"SPEAKER_{i % 3:02d}"}
        for i in range(75)
    ]
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=turns,
        )
    prompt = captured["prompt"]
    # Turn 49 (the 50th, 0-indexed) should appear
    assert "49.00" in prompt or "49.0" in prompt
    # Turn 50 (the 51st) and beyond should NOT appear in the diarization block.
    # Use a structural check: count lines in the diarization block.
    block_start = prompt.index("## Diarization context")
    # Block ends at the next "## " header OR at "Transcript:" — find whichever comes first.
    rest = prompt[block_start + len("## Diarization context"):]
    # Find end of block: either next ##, "Review each segment", or "Transcript:"
    end_candidates = [rest.find("Transcript:"), rest.find("Review each")]
    end_candidates = [c for c in end_candidates if c >= 0]
    block_end_rel = min(end_candidates) if end_candidates else len(rest)
    block = rest[:block_end_rel]
    turn_lines = [ln for ln in block.splitlines() if "SPEAKER_" in ln]
    assert len(turn_lines) == 50, (
        f"Expected 50 turn lines, got {len(turn_lines)}. Block:\n{block[:500]}"
    )


def test_analyze_returns_speaker_corrections_from_sonnet_response():
    """When Sonnet's response includes speaker_corrections, analyze() must
    pass it through unchanged."""
    svc = _make_service()
    def fake_run(prompt, schema, claude_path, timeout=120):
        return {
            "language": "en", "domain": "test", "summary": "",
            "speakers": [], "corrections": [], "uncertain_terms": [],
            "speaker_corrections": [
                {"segment_index": 12, "speaker": "Pascal",
                 "reason": "interruption mid-David turn"},
            ],
        }
    with patch("services.refinement._run_claude", side_effect=fake_run):
        result = svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=[{"start": 0, "end": 1, "speaker": "SPEAKER_00"}],
        )
    assert result["speaker_corrections"] == [
        {"segment_index": 12, "speaker": "Pascal",
         "reason": "interruption mid-David turn"},
    ]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -k "diarization or speaker_corrections_from" -v`

Expected: 5 FAILs (the diarization block doesn't exist yet; `analyze` doesn't accept `speaker_turns` so the calls raise TypeError).

- [ ] **Step 3: Extend the `analyze` signature and prompt construction**

Edit `backend/services/refinement.py`. The current signature (line 209):

```python
    def analyze(self, segments: list, context_text: Optional[str] = None,
                glossary_terms: Optional[List[str]] = None) -> dict:
```

Replace with:

```python
    def analyze(self, segments: list, context_text: Optional[str] = None,
                glossary_terms: Optional[List[str]] = None,
                speaker_turns: Optional[List[dict]] = None) -> dict:
```

Update the docstring (lines 211-219). Current:

```python
        """
        Send transcript to Claude for analysis.

        Optional `context_text` (speaker bios + context doc + global glossary, merged)
        and `glossary_terms` (proper-noun list) are prepended as a `## Known context`
        block that tells Claude these terms are present in the audio's domain.

        Returns structured dict with speakers, corrections, uncertain_terms.
        """
```

Replace with:

```python
        """
        Send transcript to Claude for analysis.

        Optional `context_text` (speaker bios + context doc + global glossary, merged)
        and `glossary_terms` (proper-noun list) are prepended as a `## Known context`
        block that tells Claude these terms are present in the audio's domain.

        Optional `speaker_turns` (pyannote turn list:
        [{"start": float, "end": float, "speaker": str}, ...]) enables Combo C
        semantic diarization polish: the prompt gains a `## Diarization context`
        block listing the turns and instructing Sonnet to emit a
        `speaker_corrections` array for any segments whose speaker should change
        based on conversational turn-taking cues. Turn list is capped at 50
        entries for prompt budget.

        Returns structured dict with speakers, corrections, uncertain_terms,
        and (when speaker_turns was provided and Sonnet found mis-attributions)
        speaker_corrections.
        """
```

Now extend the prompt construction. Find the `known_context_block` build (lines 226-240) and the prompt assembly that follows (line 242). Insert a new diarization block construction BETWEEN the `known_context_block` assignment and the `prompt = f"""..."""` line.

Find this code (lines 240-242 of the current file):

```python
            known_context_block = "\n".join(parts) + "\n---\n\n"

        prompt = f"""{known_context_block}Analyze this transcript and return a JSON object with the following structure:
```

Replace with:

```python
            known_context_block = "\n".join(parts) + "\n---\n\n"

        # Combo C — semantic diarization polish prompt block.
        # Emitted only when pyannote turn data is available. Turn list is
        # capped at 50 entries to bound prompt size on long recordings.
        diarization_block = ""
        if speaker_turns:
            turn_lines = []
            for turn in speaker_turns[:50]:
                t_start = float(turn.get("start", 0))
                t_end = float(turn.get("end", 0))
                t_spk = str(turn.get("speaker", "")).strip() or "UNKNOWN"
                turn_lines.append(f"[{t_start:.2f}s-{t_end:.2f}s] {t_spk}")
            turns_csv = "\n".join(turn_lines)
            diarization_block = (
                "## Diarization context\n\n"
                "Pyannote detected the following speaker turns:\n"
                f"{turns_csv}\n\n"
                "The current segment->speaker assignments may have mis-attributions "
                "where a brief interjection (e.g. \"yes\", \"right\", \"exactly\") "
                "was assigned to the dominant speaker of the segment instead of the "
                "interjector. Review each segment and emit a `speaker_corrections` "
                "array for any segments whose speaker should change based on:\n"
                "- Conversational turn-taking cues (brief acknowledgments mid-sentence)\n"
                "- Sentence-boundary semantics (a sentence should not change speaker mid-flow)\n"
                "- Direct address patterns (\"Pascal, what do you think?\")\n\n"
                "Only emit corrections you're confident in. Do NOT rewrite segment text.\n"
                "---\n\n"
            )

        prompt = f"""{known_context_block}{diarization_block}Analyze this transcript and return a JSON object with the following structure:
```

Also extend the JSON example inside the prompt so Sonnet sees `speaker_corrections` as a legal field. Find the JSON example (lines 243-254 of the current file):

```python
{{
  "language": "ISO 639-1 code",
  "domain": "brief topic description",
  "summary": "1-2 sentence summary",
  "speakers": [
    {{"label": "SPEAKER_00", "name": "identified name", "confidence": "high|medium|low", "reasoning": "why"}}
  ],
  "corrections": [
    {{"original": "misspelled term", "corrected": "correct spelling", "confidence": "high|medium|low"}}
  ],
  "uncertain_terms": ["terms needing web verification"]
}}
```

Replace with:

```python
{{
  "language": "ISO 639-1 code",
  "domain": "brief topic description",
  "summary": "1-2 sentence summary",
  "speakers": [
    {{"label": "SPEAKER_00", "name": "identified name", "confidence": "high|medium|low", "reasoning": "why"}}
  ],
  "corrections": [
    {{"original": "misspelled term", "corrected": "correct spelling", "confidence": "high|medium|low"}}
  ],
  "uncertain_terms": ["terms needing web verification"],
  "speaker_corrections": [
    {{"segment_index": 12, "speaker": "corrected speaker label or name", "reason": "brief justification"}}
  ]
}}
```

Note: the `speaker_corrections` field stays in the JSON example shown to Sonnet whether or not the diarization block was emitted. That's fine — Sonnet will only populate it when the diarization block tells it to (and the schema marks it optional). When the diarization block is absent, leave the example as-is; Sonnet returning `[]` or omitting the field is acceptable.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -k "diarization or speaker_corrections_from" -v`

Expected: 5 PASS.

- [ ] **Step 5: Run the full refinement-context suite to confirm no regression**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -v`

Expected: ALL PASS (the 6 pre-existing tests from Plan 1 B1/B3 + the Task 1 schema test + the 5 new diarization-prompt tests = 12 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app
git add backend/services/refinement.py backend/tests/test_refinement_context.py
git commit -m "$(cat <<'EOF'
Plan 4B Task 2: analyze() emits ## Diarization context prompt block

Adds speaker_turns kwarg to RefinementService.analyze. When provided
(non-empty), the prompt gains a ## Diarization context block listing
pyannote turns (capped at 50) and instructs Sonnet to emit a
speaker_corrections array for any mis-attributions detected via
conversational turn-taking or sentence-boundary semantics. Backward
compat preserved: speaker_turns=None or [] → no block emitted, prompt
unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Extend `apply_corrections` to apply `speaker_corrections` (text-immutable guardrail)

**Files:**
- Modify: `backend/services/refinement.py:344-388` (the `RefinementService.apply_corrections` method)
- Test: `backend/tests/test_refinement_context.py`

`apply_corrections` deepcopies segments and applies text corrections + `SPEAKER_XX → name` mapping. We add a third application step: per-segment speaker mutation driven by `analysis["speaker_corrections"]`. Hard rule: this loop reads `analysis["speaker_corrections"]` (default `[]`) and writes `refined[i]["speaker"]` ONLY. It must never touch `refined[i]["text"]`.

Apply the speaker_corrections AFTER the existing speaker_mapping loop. Sonnet's `speaker_corrections` may target either a SPEAKER_XX label or a name — apply after the SPEAKER_XX → name rename so a `speaker_corrections` entry can override the name assigned by the speaker_mapping step. Out-of-range `segment_index` values are silently skipped (defensive).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_refinement_context.py`:

```python
def test_apply_corrections_mutates_speaker_per_speaker_corrections():
    """speaker_corrections in the analysis dict must update segment[i].speaker
    for the specified segment_index."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello",  "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "Yes",    "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 3.0, "text": "Right",  "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [],
        "corrections": [],
        "speaker_corrections": [
            {"segment_index": 1, "speaker": "SPEAKER_01", "reason": "interjection"},
        ],
    }
    refined, _mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "SPEAKER_00"
    assert refined[1]["speaker"] == "SPEAKER_01"  # corrected
    assert refined[2]["speaker"] == "SPEAKER_00"


def test_apply_corrections_speaker_corrections_never_touches_text():
    """Hard guardrail: the speaker_corrections loop must NEVER mutate
    segment.text — even if Sonnet's response includes an unrelated text
    correction that overlaps the segment, the speaker_corrections path
    itself does not touch text. (Text corrections still flow through the
    existing corrections path.)"""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello world", "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [],
        "corrections": [],  # no text corrections
        "speaker_corrections": [
            {"segment_index": 0, "speaker": "SPEAKER_01",
             "reason": "actually the other speaker"},
        ],
    }
    refined, _mapping, count = svc.apply_corrections(segments, analysis)
    assert refined[0]["text"] == "Hello world", (
        "speaker_corrections must NEVER mutate segment.text"
    )
    assert refined[0]["speaker"] == "SPEAKER_01"
    # count is the number of TEXT corrections applied, which is 0 here.
    assert count == 0


def test_apply_corrections_skips_out_of_range_segment_index():
    """Defensive: Sonnet may hallucinate an index. Out-of-range entries
    are silently skipped (no exception, no mutation of any segment)."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [],
        "corrections": [],
        "speaker_corrections": [
            {"segment_index": 99, "speaker": "Ghost", "reason": "out of range"},
            {"segment_index": -1, "speaker": "Negative", "reason": "negative index"},
        ],
    }
    refined, _mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "SPEAKER_00"  # unchanged


def test_apply_corrections_no_op_when_speaker_corrections_absent():
    """Backward compat: analysis dicts without speaker_corrections must
    behave exactly as before — speaker_mapping still applies, but no
    additional speaker mutation happens."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [
            {"label": "SPEAKER_00", "name": "David",
             "confidence": "high", "reasoning": "self-introduction"},
        ],
        "corrections": [],
        # speaker_corrections absent
    }
    refined, mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "David"  # speaker_mapping applied
    assert mapping == {"SPEAKER_00": "David"}


def test_apply_corrections_speaker_corrections_overrides_speaker_mapping():
    """When both apply, speaker_corrections wins because it's applied
    AFTER the speaker_mapping rename. This lets Sonnet correct a
    mis-mapped speaker on a per-segment basis."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hi",   "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "Yes",  "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [
            {"label": "SPEAKER_00", "name": "David",
             "confidence": "high", "reasoning": "..."},
        ],
        "corrections": [],
        "speaker_corrections": [
            {"segment_index": 1, "speaker": "Pascal", "reason": "interjection"},
        ],
    }
    refined, _mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "David"   # speaker_mapping applied
    assert refined[1]["speaker"] == "Pascal"  # speaker_corrections overrides
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -k "apply_corrections" -v`

Expected: 5 FAILs. The `no_op_when_speaker_corrections_absent` test may already PASS today since `apply_corrections` doesn't read `speaker_corrections` yet — that's fine, it's a guard against regression. The other 4 FAIL because speaker_corrections aren't applied.

- [ ] **Step 3: Extend `apply_corrections`**

Edit `backend/services/refinement.py`. Find the existing `apply_corrections` body — specifically the end of the per-segment loop (lines 383-386 of the current file):

```python
            # Apply speaker mapping
            speaker = seg.get("speaker", "")
            if speaker in speaker_mapping:
                seg["speaker"] = speaker_mapping[speaker]

        return refined, speaker_mapping, corrections_applied
```

Replace with:

```python
            # Apply speaker mapping
            speaker = seg.get("speaker", "")
            if speaker in speaker_mapping:
                seg["speaker"] = speaker_mapping[speaker]

        # Combo C — apply speaker_corrections AFTER speaker_mapping so Sonnet's
        # per-segment overrides win over the bulk SPEAKER_XX -> name rename.
        # Hard guardrail: this loop mutates seg["speaker"] ONLY. It must never
        # touch seg["text"]. Out-of-range indexes are silently skipped
        # (defensive against Sonnet hallucinating a segment index).
        for sc in analysis.get("speaker_corrections", []) or []:
            if not isinstance(sc, dict):
                continue
            idx = sc.get("segment_index")
            new_speaker = sc.get("speaker")
            if not isinstance(idx, int) or idx < 0 or idx >= len(refined):
                continue
            if not new_speaker or not isinstance(new_speaker, str):
                continue
            refined[idx]["speaker"] = new_speaker

        return refined, speaker_mapping, corrections_applied
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -k "apply_corrections" -v`

Expected: 5 PASS.

- [ ] **Step 5: Run the full refinement-context suite to confirm no regression**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -v`

Expected: ALL PASS (12 from earlier + 5 new = 17 tests).

- [ ] **Step 6: Commit**

```bash
cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app
git add backend/services/refinement.py backend/tests/test_refinement_context.py
git commit -m "$(cat <<'EOF'
Plan 4B Task 3: apply_corrections applies speaker_corrections (text-immutable)

Extends RefinementService.apply_corrections with a final per-segment
speaker mutation step driven by analysis["speaker_corrections"]. Applied
AFTER the SPEAKER_XX -> name speaker_mapping so Sonnet's per-segment
overrides win. Hard guardrail: this path mutates seg["speaker"] only,
never seg["text"]. Defensive: out-of-range or malformed entries are
silently skipped.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Thread `speaker_turns` through `refine` and the route caller

**Files:**
- Modify: `backend/services/refinement.py:390-450` (the `RefinementService.refine` method)
- Modify: `backend/routes/refinement.py:174-267` (the `_run_refinement_for_job` function)
- Test: `backend/tests/test_refinement_context.py`

`refine` gains a `speaker_turns: Optional[List[dict]] = None` kwarg and forwards it to `analyze`. The route-level caller `_run_refinement_for_job` builds `speaker_turns` from `job.speakers` (the pyannote turn list — already used by `_run_post_refinement_learning` lines 107-124) and passes it to `refine`. The shape required by `analyze` is identical to what `_run_post_refinement_learning` already builds, so we lift the build out of that function and use it in both places.

- [ ] **Step 1: Write the failing test for `refine` propagation**

Append to `backend/tests/test_refinement_context.py`:

```python
def test_refine_propagates_speaker_turns_to_analyze():
    """refine() must forward speaker_turns to analyze() so the
    Diarization context block gets emitted by the underlying analyze call."""
    svc = _make_service()
    turns = [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 6.0, "speaker": "SPEAKER_01"},
    ]
    with patch.object(svc, "analyze", return_value={
        "language": "en", "domain": "test", "summary": "",
        "speakers": [], "corrections": [], "uncertain_terms": [],
    }) as mock_analyze:
        svc.refine(
            [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
            context_text="ctx",
            glossary_terms=["t1"],
            speaker_turns=turns,
        )
    mock_analyze.assert_called_once()
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("context_text") == "ctx"
    assert kwargs.get("glossary_terms") == ["t1"]
    assert kwargs.get("speaker_turns") == turns


def test_refine_defaults_speaker_turns_to_none():
    """Backward compat: callers that don't pass speaker_turns get the
    pre-Combo-C behavior — analyze receives speaker_turns=None."""
    svc = _make_service()
    with patch.object(svc, "analyze", return_value={
        "language": "en", "domain": "test", "summary": "",
        "speakers": [], "corrections": [], "uncertain_terms": [],
    }) as mock_analyze:
        svc.refine([{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}])
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("speaker_turns") is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -k "refine_propagates_speaker_turns or refine_defaults_speaker_turns" -v`

Expected: 2 FAILs (`refine` doesn't accept `speaker_turns`).

- [ ] **Step 3: Extend `refine` to accept and forward `speaker_turns`**

Edit `backend/services/refinement.py`. The current `refine` signature (line 390):

```python
    def refine(self, segments: list, context_text: Optional[str] = None,
               glossary_terms: Optional[List[str]] = None) -> dict:
```

Replace with:

```python
    def refine(self, segments: list, context_text: Optional[str] = None,
               glossary_terms: Optional[List[str]] = None,
               speaker_turns: Optional[List[dict]] = None) -> dict:
```

Find the `analyze` call inside `refine` (line 401):

```python
        analysis = self.analyze(segments, context_text=context_text, glossary_terms=glossary_terms)
```

Replace with:

```python
        analysis = self.analyze(
            segments,
            context_text=context_text,
            glossary_terms=glossary_terms,
            speaker_turns=speaker_turns,
        )
```

Update the `refine` docstring (lines 392-396). Current:

```python
        """
        Full refinement pipeline: analyze → web verify → finalize → apply.

        Returns dict with all refinement results.
        """
```

Replace with:

```python
        """
        Full refinement pipeline: analyze -> web verify -> finalize -> apply.

        Optional `speaker_turns` (pyannote turn list) enables Combo C semantic
        diarization polish in the analyze phase — Sonnet's response may include
        a `speaker_corrections` array that apply_corrections will use to
        re-attribute mis-assigned speakers on a per-segment basis. See
        analyze() docstring for the speaker_turns shape.

        Returns dict with all refinement results.
        """
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -k "refine_propagates_speaker_turns or refine_defaults_speaker_turns" -v`

Expected: 2 PASS.

- [ ] **Step 5: Confirm the existing `refine` propagation test still passes**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py::test_refine_propagates_context_and_glossary -v`

Expected: PASS (the existing test didn't assert `speaker_turns` so it shouldn't break — we only added a kwarg with a default).

- [ ] **Step 6: Update the route-level caller `_run_refinement_for_job` to build and pass `speaker_turns`**

Edit `backend/routes/refinement.py`. Find the `refine` call inside `_run_refinement_for_job` (lines 236-240):

```python
        result = state.refinement_service.refine(
            job.segments,
            context_text=context_text,
            glossary_terms=glossary_terms,
        )
```

Insert a `speaker_turns` build BEFORE that block and pass it into `refine`. Replace lines 236-240 with:

```python
        # Build pyannote turn list for Combo C semantic diarization polish.
        # Same shape and source as _run_post_refinement_learning uses (job.speakers
        # is the pyannote diarization output set by transcription.py). Falls back
        # to deriving turns from job.segments when job.speakers is empty (e.g.
        # diarization was disabled or failed).
        raw_turns = (job.speakers or [])
        if raw_turns:
            speaker_turns = [
                {"start": float(t.get("start", 0)),
                 "end": float(t.get("end", 0)),
                 "speaker": (t.get("speaker") or "").strip()}
                for t in raw_turns
                if (t.get("speaker") or "").strip()
            ]
        else:
            speaker_turns = [
                {"start": float(seg.get("start", 0)),
                 "end": float(seg.get("end", 0)),
                 "speaker": (seg.get("speaker") or "").strip()}
                for seg in (job.segments or [])
                if (seg.get("speaker") or "").strip()
            ]

        result = state.refinement_service.refine(
            job.segments,
            context_text=context_text,
            glossary_terms=glossary_terms,
            speaker_turns=speaker_turns or None,
        )
```

Note: `speaker_turns or None` — when the list is empty (no diarization data at all), pass `None` so `analyze` cleanly skips the diarization block.

- [ ] **Step 7: Write a route-level integration test asserting `speaker_turns` reaches `refine`**

Append to `backend/tests/test_refinement_context.py` (this test lives alongside the unit tests for proximity; if a more appropriate test file exists by the time you implement, move it there — but ONLY if you find one with the same monkeypatch-state pattern):

```python
def test_run_refinement_for_job_builds_speaker_turns_from_job_speakers(monkeypatch):
    """_run_refinement_for_job must build speaker_turns from job.speakers
    (pyannote output) and pass it into refine()."""
    import state
    from routes.refinement import _run_refinement_for_job

    # Fixture job with pyannote turns in job.speakers
    class _Job:
        job_id = "j1"
        status = "completed"
        segments = [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}]
        speakers = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 6.0, "speaker": "SPEAKER_01"},
        ]
        auto_speaker_matches = None
        refinement_status = None

    job = _Job()

    # Stub job store
    class _JobStore:
        def get(self, jid): return job
        def update(self, j): pass
    monkeypatch.setattr(state, "job_store", _JobStore())
    monkeypatch.setattr(state, "jobs", _JobStore())

    # Stub refinement store
    class _RefStore:
        def update_status(self, jid, s, err=None): pass
        def save_result(self, jid, r): pass
    monkeypatch.setattr(state, "refinement_store", _RefStore())

    captured = {}
    class _RefSvc:
        def refine(self, segments, context_text=None, glossary_terms=None,
                   speaker_turns=None):
            captured["speaker_turns"] = speaker_turns
            return {
                "analysis": {"corrections": []},
                "refined_segments": segments,
                "speaker_mapping": {},
                "corrections_applied": 0,
                "speakers_identified": 0,
                "web_searches_performed": 0,
            }
    monkeypatch.setattr(state, "refinement_service", _RefSvc())

    # Stub context loaders to avoid touching disk
    import services.transcription as txn
    import services.glossary as glo
    monkeypatch.setattr(txn, "load_context_document", lambda p: "")
    monkeypatch.setattr(txn, "load_speakers_context", lambda ids: "")
    monkeypatch.setattr(txn, "merge_context_sources", lambda *a: "")
    monkeypatch.setattr(glo, "load_global_glossary", lambda: "")
    monkeypatch.setattr(glo, "load_global_glossary_terms", lambda: [])

    # Stub the B7 orchestrator — out of scope for this test
    import routes.refinement as rr
    monkeypatch.setattr(rr, "_run_post_refinement_learning", lambda **kw: None)

    _run_refinement_for_job("j1", speaker_ids=None, context_path=None, audio_path=None)

    assert captured.get("speaker_turns") is not None, (
        "_run_refinement_for_job must pass speaker_turns into refine()"
    )
    assert captured["speaker_turns"] == [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 6.0, "speaker": "SPEAKER_01"},
    ]
```

- [ ] **Step 8: Run the new route-level test**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py::test_run_refinement_for_job_builds_speaker_turns_from_job_speakers -v`

Expected: PASS.

- [ ] **Step 9: Run the full refinement-context suite to confirm no regression**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -v`

Expected: ALL PASS (17 from earlier + 2 new `refine` tests + 1 new route-level test = 20 tests).

- [ ] **Step 10: Commit**

```bash
cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app
git add backend/services/refinement.py backend/routes/refinement.py backend/tests/test_refinement_context.py
git commit -m "$(cat <<'EOF'
Plan 4B Task 4: thread speaker_turns through refine and route caller

RefinementService.refine gains a speaker_turns kwarg that forwards to
analyze. _run_refinement_for_job builds the turn list from job.speakers
(pyannote output) and passes it in, with a derived-from-segments fallback
when diarization data is absent. Empty list collapses to None so the
diarization prompt block is cleanly suppressed.

This wires Combo C end-to-end for the existing refinement path: every
refinement run on the current engines now benefits from Sonnet's
semantic speaker re-attribution.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: End-to-end refinement integration test (mocked Sonnet)

**Files:**
- Test: `backend/tests/test_refinement_context.py`

A focused integration test that exercises the full `refine` pipeline against a fixture transcript and a mocked Sonnet response, asserting the final `refined_segments` reflect Sonnet's speaker_corrections. This is the acceptance gate for the sub-plan — it catches plumbing errors that the unit tests miss.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_refinement_context.py`:

```python
def test_refine_end_to_end_applies_speaker_corrections_to_refined_segments():
    """Acceptance gate for Sub-plan B: a refine() call with speaker_turns
    + a mocked Sonnet response that includes speaker_corrections must
    produce refined_segments where the targeted segment has the corrected
    speaker AND the segment text is unchanged."""
    svc = _make_service()

    segments = [
        {"start": 0.0, "end": 5.0, "text": "So what do you think of the proposal",
         "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 5.5, "text": "Yes",
         "speaker": "SPEAKER_00"},  # mis-attributed interjection
        {"start": 5.5, "end": 12.0, "text": "I think it's a good idea",
         "speaker": "SPEAKER_00"},
    ]
    speaker_turns = [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 5.5, "speaker": "SPEAKER_01"},
        {"start": 5.5, "end": 12.0, "speaker": "SPEAKER_00"},
    ]

    # Mock Sonnet's response: it identifies the segment 1 interjection as
    # being by SPEAKER_01, and renames both labels via the speakers list.
    sonnet_response = {
        "language": "en",
        "domain": "business meeting",
        "summary": "Two speakers discuss a proposal.",
        "speakers": [
            {"label": "SPEAKER_00", "name": "David",
             "confidence": "high", "reasoning": "self-introduced"},
            {"label": "SPEAKER_01", "name": "Pascal",
             "confidence": "high", "reasoning": "self-introduced"},
        ],
        "corrections": [],
        "uncertain_terms": [],
        "speaker_corrections": [
            {"segment_index": 1, "speaker": "Pascal",
             "reason": "brief affirmation mid-David turn, matches pyannote SPEAKER_01"},
        ],
    }

    with patch("services.refinement._run_claude", return_value=sonnet_response):
        result = svc.refine(segments, speaker_turns=speaker_turns)

    refined = result["refined_segments"]
    # Segment 0: SPEAKER_00 -> David via speaker_mapping
    assert refined[0]["speaker"] == "David"
    assert refined[0]["text"] == "So what do you think of the proposal"
    # Segment 1: speaker_mapping renames SPEAKER_00 -> David, then
    # speaker_corrections overrides to Pascal
    assert refined[1]["speaker"] == "Pascal"
    assert refined[1]["text"] == "Yes", (
        "Combo C must NEVER mutate segment.text"
    )
    # Segment 2: SPEAKER_00 -> David
    assert refined[2]["speaker"] == "David"
    assert refined[2]["text"] == "I think it's a good idea"

    # Speaker mapping reflects the rename (not the per-segment correction).
    assert result["speaker_mapping"] == {
        "SPEAKER_00": "David",
        "SPEAKER_01": "Pascal",
    }
```

- [ ] **Step 2: Run the new test to verify it passes**

If Tasks 1-4 are correctly implemented, this test should pass on first run. Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py::test_refine_end_to_end_applies_speaker_corrections_to_refined_segments -v`

Expected: PASS. If FAIL, the failure pinpoints which plumbing step has a bug:
- "expected 'Pascal', got 'David' (or 'SPEAKER_00')" → speaker_corrections not being applied in `apply_corrections` (Task 3 bug)
- "expected 'Pascal', got 'Pascal' but text changed" → Task 3 guardrail violated
- `analyze` not seeing `speaker_turns` → Task 4 propagation bug

If the test fails, fix the underlying task's implementation and re-run — do not patch around it here.

- [ ] **Step 3: Run the full refinement-context suite once more**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest tests/test_refinement_context.py -v`

Expected: ALL PASS (21 tests total).

- [ ] **Step 4: Run the full backend suite to confirm no broader regression**

Run: `cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app/backend && python -m pytest -v --tb=short 2>&1 | tail -50`

Expected: same count of passes/skips as before this sub-plan (the new tests are additive; nothing else should have regressed). Skim the tail for any unexpected fail/error.

- [ ] **Step 5: Commit**

```bash
cd /Users/davidmarchesseau/Development/apps/whisper-transcription-app
git add backend/tests/test_refinement_context.py
git commit -m "$(cat <<'EOF'
Plan 4B Task 5: end-to-end integration test for Combo C polish

Exercises the full refine() pipeline with a mocked Sonnet response that
includes speaker_corrections. Asserts the final refined_segments show
the per-segment speaker override AND that segment text is preserved
(text-immutable guardrail). This is the acceptance gate for Sub-plan B —
catches any plumbing regression between analyze/apply_corrections/refine
and the route caller.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-review checklist (run after writing the plan, before dispatching reviewer)

**Spec coverage** (mapping each Combo C / Sub-plan B requirement → task):

| Spec requirement | Covered by |
|---|---|
| `speaker_corrections` array in JSON schema | Task 1 |
| `[{segment_index, speaker, reason}]` shape | Task 1 |
| `## Diarization context` prompt block | Task 2 |
| Block only emitted when speaker_turns provided (backward compat) | Task 2 |
| Turn list capped at ~50 entries for prompt budget | Task 2 |
| "Only emit corrections you're confident in" prompt language | Task 2 (in the inserted block text) |
| "Do NOT rewrite segment text" prompt language | Task 2 (in the inserted block text) |
| `apply_corrections` applies speaker_corrections | Task 3 |
| Hard guardrail: speaker only, never text | Task 3 (structural + asserted by test) |
| Backward compat when speaker_corrections absent | Task 3 |
| `refine` accepts and forwards speaker_turns | Task 4 |
| Route caller builds speaker_turns from job.speakers | Task 4 |
| End-to-end refinement run produces polished speakers | Task 5 |
| No `confidence` field on speaker_corrections | Honored — schema in Task 1 omits it |

**Placeholder scan**: No "TBD" / "implement later" / "add validation" / "similar to Task N" patterns. Every test has full code. Every Edit shows the exact `old_string` and `new_string`.

**Type consistency**: `speaker_turns` is consistently `List[dict]` with `{start: float, end: float, speaker: str}` across `analyze`, `refine`, the route caller, and the diarization-block prompt formatter. `speaker_corrections` is consistently `List[dict]` with `{segment_index: int, speaker: str, reason: str}` across the schema, the prompt example, the apply path, and all tests.

**Cross-task dependencies**: Task 1 (schema) → Task 2 (prompt) → Task 3 (apply) → Task 4 (route plumbing) → Task 5 (integration). Each task ends green and committed before the next starts. Task 5 is the only one that fails if any earlier task is buggy, by design.

## Notes on out-of-scope items (for the implementer's awareness)

- **No `confidence` field on `speaker_corrections`.** Spec line 489 explicitly defers this. If post-launch observation shows false-positive speaker reassignments, add a `confidence: "high"|"medium"|"low"` field to the schema, the prompt example, and an apply-time filter — but NOT in this sub-plan.
- **No frontend changes.** Sub-plan B is pure backend. The Refined badge / refinement UI from Plan 1 + Plan 3 already surfaces the polished speakers transparently via `refined_segments`.
- **No orchestrator integration.** This sub-plan ships in isolation against the current engine selector. Sub-plan A's orchestrator will later route through the same `refine` call, inheriting Combo C automatically with no further changes here.
- **No changes to `_run_refinement` (the legacy wrapper)** — it just calls `_run_refinement_for_job` which now builds its own `speaker_turns`. The manual `/refine/job/{id}` endpoint inherits Combo C for free.
- **No changes to `assign_speakers_to_segments` in `services/diarization.py`** — Sonnet polishes its output downstream.
