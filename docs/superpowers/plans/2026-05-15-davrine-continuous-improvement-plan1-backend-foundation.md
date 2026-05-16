# Davrine Continuous Improvement — Plan 1 (Backend Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the backend foundation of spec `docs/superpowers/specs/2026-05-15-davrine-continuous-improvement-design.md` — B4 (persistent global glossary), B1 (refinement receives context + glossary), B3 (Sonnet 4.6 + 300s timeout), B2 (auto-run refinement on completion), B5 (inline auto-match), B8 (engine-compatibility doc). Plans 2 (learning system) and 3 (UX) build on this.

**Architecture:** A small new helper module `backend/services/glossary.py` owns the `_global.md` lifecycle. The existing `merge_context_sources()` in `transcription.py` becomes the single composition point and always prepends the global glossary. The `RefinementService.analyze/refine` signatures grow two optional kwargs (`context_text`, `glossary_terms`) and a `## Known context` prompt block. The `_run_refinement` body in `routes/refinement.py` is extracted to a shared `_run_refinement_for_job(job_id, speaker_ids, context_path)` that both the manual route and the new auto-trigger in `transcription.py` call. The auto-trigger is dispatched on `state.transcription_executor` after `_update_job(..., status="completed")`. B5 calls the already-implemented `embedding_service.auto_identify_speakers()` inline after diarization joins (Whisper path only — Voxtral/Parakeet do their own diarization). B8 ships `docs/engines.md`.

**Tech Stack:** Python 3.11+, FastAPI, pytest, pydantic, Claude CLI subprocess, mlx-whisper, pyannote-audio.

---

## File Structure

**Create:**
- `backend/services/glossary.py` — `load_global_glossary`, `load_global_glossary_terms`, `append_auto_learned_term` (the third is unused in Plan 1; Plan 2 calls it. Stub it now to keep the helper a single artifact.)
- `backend/tests/test_glossary.py` — unit tests for the helper (load, term extraction, idempotent append, missing file, empty file)
- `backend/tests/test_refinement_context.py` — unit tests for B1 + B3 (prompt construction, model/timeout args)
- `backend/tests/test_auto_refine_orchestration.py` — unit tests for B2 (auto-trigger decision logic and dispatch)
- `backend/tests/test_inline_auto_match.py` — unit test for B5 (inline call wiring in `_run_transcription_sync`)
- `docs/engines.md` — B8 engine-compatibility table
- `~/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/contexts/_global.md` — initial template (one-time bootstrap; not VCS-tracked)

**Modify:**
- `backend/services/refinement.py` — B1 + B3: `analyze(segments, context_text=None, glossary_terms=None)`, `refine(segments, context_text=None, glossary_terms=None)`, prompt prefix, `--model sonnet`, `timeout=300`
- `backend/routes/refinement.py` — B1 + B2: extract `_run_refinement_for_job(job_id, speaker_ids, context_path)`; manual `/refine/job/{job_id}` route uses it
- `backend/job_models.py` — B2: add `auto_refine: Optional[bool] = None` to `TranscriptionSettings`; add `refinement_status`, `auto_speaker_matches`, `learning_summary`, `learning_status` to `TranscriptionJob.__init__` (in-memory only, no DB migration)
- `backend/services/transcription.py` — B4: prepend `load_global_glossary()` at every `merge_context_sources(...)` call site (3 sites: lines 289, 403, 668); B2: dispatch refinement on `state.transcription_executor` after `_update_job(..., status="completed")`; B5: inline auto-match call after diarization joins in the Whisper branch and overlay matched names onto segments
- `backend/routes/transcription.py:638-662` — include `refinement_status`, `auto_speaker_matches`, `learning_summary`, `learning_status` in the GET `/job/{job_id}` response
- `README.md` — link to `docs/engines.md` from the "Architecture" section

**Reference (read-only):**
- `backend/services/transcription.py:34-161` — `load_context_document`, `derive_context_terms`, `load_speakers_context`, `merge_context_sources` (already exist; reuse, do not duplicate)
- `backend/services/speaker_embedding.py:357-442` — `auto_identify_speakers()` (already implemented; B5 just calls it inline)
- `backend/routes/transcription.py:1217-1237` — `_resolve_match_scope()` (already implemented; B5 reuses it)
- `backend/state.py:72` — `state.transcription_executor` (B2 dispatch target)
- `backend/state.py:112-123` — `state.refinement_available`, `state.refinement_service`
- `backend/tests/conftest.py:27-46` — `icloud_base` fixture (B4 tests use it)
- `backend/tests/test_transcription_a1.py` — reference for the monkeypatch/MagicMock pattern used to test `_run_transcription_sync`

---

## Conventions for all tasks

- **Run from the venv:** `cd ~/Development/apps/whisper-transcription-app/backend && source venv/bin/activate` (or invoke `./venv/bin/python -m pytest …` directly without `cd`).
- **Commit granularity:** one commit per task (after all its tests pass). Use `git add <specific files>` — never `git add -A` (avoids ramassing the user's WIP — feedback from the A1/A2/A3 plan).
- **Branch:** all work lands on `dev`. The branch is already pushed.
- **TDD discipline:** Use superpowers:test-driven-development. Write the failing test first, watch it fail, then implement.
- **Backend restart not required** between most tasks — pytest hits the code directly. The only end-to-end manual validation (Task 10) needs a fresh `launchctl kickstart -k gui/$(id -u)/com.whisper.backend` to pick up code changes the daemon has cached.

---

## Task 1: Baseline & branch check

**Files:**
- None (verification only)

- [ ] **Step 1: Confirm we're on `dev`**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app && git status -sb | head -3
```
Expected: `## dev...origin/dev` (working tree may have WIP changes — leave them).

- [ ] **Step 2: Run existing backend tests as baseline**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: `247 passed, 3 skipped` (per handoff notes; record actual numbers for regression check at Task 10).

- [ ] **Step 3: Read the spec end-to-end one more time**

Skim `docs/superpowers/specs/2026-05-15-davrine-continuous-improvement-design.md` sections B1–B5 and B8 (skip B6/B7 — those are Plans 2 & 3). Confirm acceptance criterion: "Manukai", "DMG Mori", "Starrag" appear correctly in the refined transcript at Task 10.

---

## Task 2: B4 — `glossary.py` helper module

**Files:**
- Create: `backend/services/glossary.py`
- Create: `backend/tests/test_glossary.py`

The helper owns the lifecycle of `<ICLOUD_BASE_PATH>/contexts/_global.md`. Two readers (`load_global_glossary`, `load_global_glossary_terms`) are called by transcription/refinement. The writer (`append_auto_learned_term`) is unused in Plan 1 but stubbed so Plan 2 can wire it without revisiting this module.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_glossary.py`:

```python
"""B4 unit tests: global glossary helper."""

import importlib
from pathlib import Path


def _reload_glossary():
    """Re-import the glossary module so it picks up the patched ICLOUD_BASE_PATH."""
    import services.glossary
    return importlib.reload(services.glossary)


def test_load_missing_file_returns_none(icloud_base):
    glossary = _reload_glossary()
    assert glossary.load_global_glossary() is None
    assert glossary.load_global_glossary_terms() == []


def test_load_empty_file_returns_none(icloud_base):
    (icloud_base / "contexts" / "_global.md").write_text("   \n  \n", encoding="utf-8")
    glossary = _reload_glossary()
    assert glossary.load_global_glossary() is None
    assert glossary.load_global_glossary_terms() == []


def test_load_returns_text_and_terms(icloud_base):
    body = (
        "# Global Glossary\n\n"
        "## Active\n\n"
        "Manukai, DMG Mori, Starrag, Pascal Weber, Daniel.\n"
    )
    (icloud_base / "contexts" / "_global.md").write_text(body, encoding="utf-8")
    glossary = _reload_glossary()

    text = glossary.load_global_glossary()
    assert text is not None
    assert "Manukai" in text
    assert "DMG Mori" in text

    terms = glossary.load_global_glossary_terms()
    # derive_context_terms picks proper nouns and ALL-CAPS acronyms.
    assert "Manukai" in terms
    assert "Starrag" in terms
    # 'DMG' is an acronym; 'Mori' is a proper noun — both should appear.
    assert "DMG" in terms or "Mori" in terms


def test_append_auto_learned_term_creates_section(icloud_base):
    body = "# Global Glossary\n\n## Active\n\n(empty)\n"
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(body, encoding="utf-8")
    glossary = _reload_glossary()

    glossary.append_auto_learned_term(
        "Manukai",
        source_job_id="job-1",
        context_phrase="founder of Manukai",
    )
    out = target.read_text(encoding="utf-8")
    assert "## Auto-learned (pending review)" in out
    assert "Manukai" in out.split("## Auto-learned (pending review)")[1]


def test_append_auto_learned_term_is_idempotent(icloud_base):
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(
        "# Global Glossary\n\n## Active\n\n## Auto-learned (pending review)\n\n- Manukai (job-1)\n",
        encoding="utf-8",
    )
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("manukai", source_job_id="job-2", context_phrase="x")
    glossary.append_auto_learned_term("MANUKAI", source_job_id="job-3", context_phrase="y")
    out = target.read_text(encoding="utf-8")

    # Case-insensitive de-dup: still exactly one mention in the pending section
    pending = out.split("## Auto-learned (pending review)")[1]
    assert pending.lower().count("manukai") == 1


def test_append_creates_file_if_missing(icloud_base):
    target = icloud_base / "contexts" / "_global.md"
    assert not target.exists()
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("Starrag", source_job_id="job-1", context_phrase="...")
    assert target.exists()
    out = target.read_text(encoding="utf-8")
    assert "Starrag" in out
    assert "## Auto-learned (pending review)" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_glossary.py -v 2>&1 | tail -20
```
Expected: collection errors / ImportError on `services.glossary`.

- [ ] **Step 3: Implement `backend/services/glossary.py`**

Create:

```python
"""Persistent global glossary helper (B4).

Owns the lifecycle of <ICLOUD_BASE_PATH>/contexts/_global.md — a single
markdown file whose terms are auto-injected into every transcription's
initial_prompt and every refinement run's known-context block.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from config import ICLOUD_BASE_PATH
from services.transcription import derive_context_terms

logger = logging.getLogger(__name__)

GLOBAL_GLOSSARY_PATH = ICLOUD_BASE_PATH / "contexts" / "_global.md"
PENDING_SECTION_HEADER = "## Auto-learned (pending review)"


def load_global_glossary() -> Optional[str]:
    """Return the full contents of _global.md, or None if missing/empty."""
    if not GLOBAL_GLOSSARY_PATH.is_file():
        return None
    try:
        text = GLOBAL_GLOSSARY_PATH.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("Failed to read %s: %s", GLOBAL_GLOSSARY_PATH, exc)
        return None
    return text if text.strip() else None


def load_global_glossary_terms() -> List[str]:
    """Return proper-noun terms extracted from _global.md, or [] if missing."""
    text = load_global_glossary()
    if not text:
        return []
    return derive_context_terms(text, limit=200)


def _normalize_term(term: str) -> str:
    """Case-fold + collapse whitespace + strip trailing punctuation for de-dup."""
    import unicodedata
    normalized = unicodedata.normalize("NFC", term).strip()
    normalized = " ".join(normalized.split())
    normalized = normalized.rstrip(".,;:!?")
    return normalized.lower()


def append_auto_learned_term(term: str, source_job_id: str, context_phrase: str) -> None:
    """Append `term` to the pending-review section of _global.md.

    - Creates the file with the standard template if it doesn't exist.
    - Creates the pending-review section if missing.
    - Idempotent: no-op if a case-insensitive normalized match already appears
      anywhere in the file (active or pending).
    - Never raises — logs and returns on any IO failure.
    """
    canonical = term.strip()
    if not canonical:
        return
    norm = _normalize_term(canonical)
    if not norm:
        return

    try:
        GLOBAL_GLOSSARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if GLOBAL_GLOSSARY_PATH.is_file():
            body = GLOBAL_GLOSSARY_PATH.read_text(encoding="utf-8", errors="ignore")
        else:
            body = (
                "# Global Glossary\n\n"
                "Terms in this document are auto-injected into every transcription's\n"
                "initial_prompt and into the refinement LLM's known-context block.\n\n"
                "## Active\n\n"
                "(Add domain-specific proper nouns, company names, jargon, etc.)\n\n"
            )

        # Idempotency: skip if any existing line contains the normalized term.
        for line in body.splitlines():
            if norm and norm in _normalize_term(line):
                return

        if PENDING_SECTION_HEADER not in body:
            if not body.endswith("\n"):
                body += "\n"
            body += f"\n{PENDING_SECTION_HEADER}\n\n"

        # Append the new term as a bullet under the pending section.
        entry = f"- {canonical} (from {source_job_id}: {context_phrase[:120]})\n"
        # Insert right after the header line, before any later content.
        head, _, tail = body.partition(PENDING_SECTION_HEADER)
        rebuilt = head + PENDING_SECTION_HEADER + "\n" + entry + tail.lstrip("\n")

        GLOBAL_GLOSSARY_PATH.write_text(rebuilt, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to append auto-learned term %r: %s", canonical, exc)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_glossary.py -v 2>&1 | tail -20
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/glossary.py backend/tests/test_glossary.py
git commit -m "B4: add global glossary helper (load/extract/append)"
```

---

## Task 3: B4 wiring — prepend global glossary in `transcription.py`

**Files:**
- Modify: `backend/services/transcription.py:289`, `:403`, `:668` (the three `merge_context_sources(...)` call sites)
- Modify: `backend/tests/test_glossary.py` — add an integration test that verifies the merge order

`merge_context_sources()` already accepts variadic args. The change is to add `load_global_glossary()` as the first arg at each call site so the spec's priority order is enforced: **global → context_path → speakers**.

- [ ] **Step 1: Write the failing integration test**

Append to `backend/tests/test_glossary.py`:

```python
def test_transcription_merges_global_first(icloud_base, monkeypatch):
    """merge_context_sources call sites must put global glossary first."""
    (icloud_base / "contexts" / "_global.md").write_text(
        "# Global Glossary\n\n## Active\n\nManukai\n",
        encoding="utf-8",
    )
    (icloud_base / "contexts" / "deal.md").write_text(
        "# Deal context\n\nPascal Weber call.\n",
        encoding="utf-8",
    )

    # Re-import after icloud_base patched config
    import importlib
    import services.transcription as t
    importlib.reload(t)

    from job_models import TranscriptionSettings
    settings = TranscriptionSettings(context_path="deal.md", speaker_ids=None)

    # Mimic the call-site composition used inside _run_transcription_sync.
    from services.glossary import load_global_glossary
    merged = t.merge_context_sources(
        load_global_glossary(),
        t.load_context_document(settings.context_path),
        t.load_speakers_context(settings.speaker_ids),
    )

    assert merged is not None
    # Global must come before the deal context (priority order).
    assert merged.index("Manukai") < merged.index("Pascal Weber call")
```

- [ ] **Step 2: Run test to verify it fails or already passes**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_glossary.py::test_transcription_merges_global_first -v 2>&1 | tail -10
```
Expected: PASS (the test exercises `merge_context_sources` directly with the new helper — this baseline test will pin the order before we change the production call sites).

- [ ] **Step 3: Modify the three production call sites in `transcription.py`**

Add the import near the existing imports at the top:

```python
from services.glossary import load_global_glossary
```

At each of the three sites (search for `context_text = merge_context_sources(` — there are exactly 3), change:

```python
context_text = merge_context_sources(
    load_context_document(settings.context_path),
    load_speakers_context(settings.speaker_ids),
)
```

to:

```python
context_text = merge_context_sources(
    load_global_glossary(),
    load_context_document(settings.context_path),
    load_speakers_context(settings.speaker_ids),
)
```

The three sites are:
- `transcribe_with_voxtral` (~line 289)
- `transcribe_with_voxtral_local` (~line 403)
- `_run_transcription_sync` Whisper branch (~line 668)

- [ ] **Step 4: Run the full backend test suite to verify nothing broke**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: same passing count as baseline + the new glossary tests (~6-7 new passes).

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/transcription.py backend/tests/test_glossary.py
git commit -m "B4: wire global glossary into transcription context merge"
```

---

## Task 4: B1 — refinement service receives context + glossary

**Files:**
- Modify: `backend/services/refinement.py` — `analyze()` and `refine()` grow `context_text` + `glossary_terms` kwargs; prompt prefix added
- Create: `backend/tests/test_refinement_context.py`

The Claude prompt is reshaped: when either kwarg is provided, prepend a `## Known context` block to the existing analysis prompt with an explicit instruction to apply high-confidence corrections for misspellings of the listed terms.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_refinement_context.py`:

```python
"""B1 + B3 unit tests: refinement context injection and model/timeout args."""

import json
from unittest.mock import patch


def _make_service():
    from services.refinement import RefinementService
    return RefinementService(claude_path="/fake/claude")


def _stub_run_claude_capture(captured):
    """Replace _run_claude so analyze() returns a minimal valid response and
    we capture the prompt that was sent."""
    def fake_run(prompt, schema, claude_path, timeout=120):
        captured["prompt"] = prompt
        captured["timeout"] = timeout
        return {
            "language": "en",
            "domain": "test",
            "summary": "...",
            "speakers": [],
            "corrections": [],
            "uncertain_terms": [],
        }
    return fake_run


def test_analyze_omits_known_context_when_no_context():
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze([{"start": 0, "end": 1, "text": "hello", "speaker": "SPEAKER_00"}])
    assert "## Known context" not in captured["prompt"]
    assert "ARE present in the audio" not in captured["prompt"]


def test_analyze_injects_glossary_terms_block():
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hello", "speaker": "SPEAKER_00"}],
            glossary_terms=["Manukai", "DMG Mori", "Starrag"],
        )
    prompt = captured["prompt"]
    assert "## Known context" in prompt
    assert "Manukai" in prompt
    assert "DMG Mori" in prompt
    assert "Starrag" in prompt
    assert "ARE present in the audio" in prompt
    assert "confidence=high" in prompt


def test_analyze_injects_context_text_block():
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            context_text="# Speaker: Pascal Weber\n\nHead of partnerships at Manukai.",
        )
    prompt = captured["prompt"]
    assert "## Known context" in prompt
    assert "Pascal Weber" in prompt
    assert "Manukai" in prompt


def test_refine_propagates_context_and_glossary():
    """refine() must forward both kwargs to analyze()."""
    svc = _make_service()
    captured = {}
    with patch.object(svc, "analyze", return_value={
        "language": "en", "domain": "test", "summary": "",
        "speakers": [], "corrections": [], "uncertain_terms": [],
    }) as mock_analyze:
        svc.refine(
            [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
            context_text="ctx",
            glossary_terms=["t1", "t2"],
        )
    mock_analyze.assert_called_once()
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("context_text") == "ctx"
    assert kwargs.get("glossary_terms") == ["t1", "t2"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_refinement_context.py -v 2>&1 | tail -20
```
Expected: TypeError on unexpected kwargs / assertion failures on missing prompt block.

- [ ] **Step 3: Modify `backend/services/refinement.py`**

Update the `analyze` signature and prompt:

```python
def analyze(self, segments: list, context_text: Optional[str] = None,
            glossary_terms: Optional[List[str]] = None) -> dict:
    """
    Send transcript to Claude for analysis.

    Optional `context_text` (speaker bios + context doc + global glossary, merged)
    and `glossary_terms` (proper-noun list) are prepended as a `## Known context`
    block that tells Claude these terms are present in the audio's domain.
    """
    transcript_text = _build_transcript_text(segments)
    if len(transcript_text) > 50000:
        transcript_text = transcript_text[:50000] + "\n\n[... transcript truncated for analysis ...]"

    known_context_block = ""
    if glossary_terms or context_text:
        parts = ["## Known context\n"]
        if glossary_terms:
            terms_csv = ", ".join(t.strip() for t in glossary_terms if t and t.strip())
            if terms_csv:
                parts.append(
                    "The following terms ARE present in the audio's domain. "
                    "If you find any misspelling of these in the transcript, "
                    "correct it with confidence=high:\n\n"
                    f"[{terms_csv}]\n"
                )
        if context_text:
            parts.append(f"\nSpeaker context:\n{context_text.strip()}\n")
        known_context_block = "\n".join(parts) + "\n---\n\n"

    prompt = f"""{known_context_block}Analyze this transcript and return a JSON object with the following structure:
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

Rules:
- For speakers: Look for self-introductions, how others address them, context clues. Only assign names with medium+ confidence.
- For corrections: Fix proper nouns, company names, technical terms, medication names, place names. Only include high/medium confidence fixes.
- For uncertain_terms: List terms that look wrong but you're not sure of the correct spelling. These will be verified via web search.
- Keep original speaker labels (SPEAKER_00 etc.) in the "label" field.
- If you cannot identify a speaker's name, use a descriptive label like "Interviewer" or "Caller".

Transcript:
{transcript_text}

Return ONLY the JSON object, no other text."""

    return _run_claude(prompt, ANALYSIS_SCHEMA, self.claude_path, timeout=300)
```

Update the `refine` signature:

```python
def refine(self, segments: list, context_text: Optional[str] = None,
           glossary_terms: Optional[List[str]] = None) -> dict:
    """
    Full refinement pipeline: analyze → web verify → finalize → apply.
    """
    logger.info("Starting transcript refinement (%d segments)", len(segments))

    logger.info("Phase 1: Analyzing transcript with Claude...")
    analysis = self.analyze(segments, context_text=context_text, glossary_terms=glossary_terms)
    # ... rest unchanged
```

(Leave the rest of `refine()` untouched; only the call to `self.analyze` gains the two kwargs.)

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_refinement_context.py -v 2>&1 | tail -20
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/refinement.py backend/tests/test_refinement_context.py
git commit -m "B1: refinement accepts context_text + glossary_terms kwargs"
```

---

## Task 5: B3 — Sonnet model + 300s timeout

**Files:**
- Modify: `backend/services/refinement.py:103-110` (`_run_claude` default timeout + `--model` arg)
- Modify: `backend/tests/test_refinement_context.py` — add a test for the model/timeout args

Task 4 already set `timeout=300` at the analyze call site. This task hardens the default and switches the model.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_refinement_context.py`:

```python
def test_run_claude_uses_sonnet_and_300s_timeout(monkeypatch):
    """B3: _run_claude must invoke claude CLI with --model sonnet and accept timeout=300."""
    import subprocess
    from services import refinement

    captured = {}

    class _Result:
        returncode = 0
        stdout = '{"language": "en", "domain": "", "summary": "", "speakers": [], "corrections": [], "uncertain_terms": []}'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        return _Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    refinement._run_claude("hi", "{}", "/fake/claude", timeout=300)

    cmd = captured["cmd"]
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "sonnet", f"expected sonnet, got {cmd[model_idx + 1]!r}"
    assert captured["timeout"] == 300


def test_analyze_passes_300s_timeout_to_run_claude():
    """B3: analyze() must request the 300s budget for Sonnet on full transcripts."""
    from unittest.mock import patch
    svc = _make_service()
    captured = {}
    def fake_run(prompt, schema, claude_path, timeout=120):
        captured["timeout"] = timeout
        return {"language": "en", "domain": "", "summary": "",
                "speakers": [], "corrections": [], "uncertain_terms": []}
    with patch("services.refinement._run_claude", side_effect=fake_run):
        svc.analyze([{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])
    assert captured["timeout"] == 300
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_refinement_context.py -v -k "sonnet or 300s" 2>&1 | tail -10
```
Expected: FAIL — current code uses `--model haiku`.

- [ ] **Step 3: Update `_run_claude` in `refinement.py`**

Change the `cmd` list:

```python
cmd = [
    claude_path, "-p",
    "--model", "sonnet",
    "--output-format", "json",
    "--max-turns", "1",
    "--no-session-persistence",
    prompt,
]
```

The `analyze()` call from Task 4 already passes `timeout=300`. Leave `finalize()` at its existing 60s budget — it processes a small web-context payload and shouldn't need more.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_refinement_context.py -v 2>&1 | tail -10
```
Expected: 6 passed (4 from Task 4 + 2 new).

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/refinement.py backend/tests/test_refinement_context.py
git commit -m "B3: refinement uses Sonnet with 300s timeout"
```

---

## Task 6: B2 (part 1) — add new fields to TranscriptionSettings + TranscriptionJob

**Files:**
- Modify: `backend/job_models.py:370-392` — add `auto_refine` to `TranscriptionSettings`
- Modify: `backend/job_models.py:18-31` — add 4 fields to `TranscriptionJob.__init__`
- Modify: `backend/routes/transcription.py:638-662` — emit the 4 new fields in GET `/job/{job_id}`

The 4 new `TranscriptionJob` fields are **in-memory only**. Persisting them across backend restarts would require a SQL migration; the spec accepts the restart-loss tradeoff because refinement is short-lived (~30s-3min). After restart, the UI sees `None` for these fields, which it must treat as "no auto-refine info available" (UI work is Plan 3).

- [ ] **Step 1: Add fields with default `None`**

Modify `TranscriptionSettings` in `backend/job_models.py`:

```python
class TranscriptionSettings(BaseModel):
    # ... existing fields ...
    output_mode: str = "verbatim"
    # B2: tri-state — None = auto-on if speaker_ids or context_path set; True/False = explicit
    auto_refine: Optional[bool] = None
```

Modify `TranscriptionJob.__init__` in `backend/job_models.py`:

```python
class TranscriptionJob:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.status = "pending"
        self.progress = 0
        self.progress_message = ""
        self.result = None
        self.error = None
        self.language = None
        self.language_probability = None
        self.segments = []
        self.speakers = []
        self.is_generated = False
        self._from_captions = False
        # B2 (in-memory only — not persisted to SQL):
        self.refinement_status = None       # None | "pending" | "processing" | "done" | "failed"
        self.auto_speaker_matches = None    # Dict[str, Dict] from B5
        self.learning_summary = None        # Dict[str, int] populated by Plan 2
        self.learning_status = None         # "ok" | "partial" | "failed" — populated by Plan 2
```

Modify GET `/job/{job_id}` response in `backend/routes/transcription.py` (around line 638):

```python
response = {
    "job_id": job.job_id,
    "status": job.status,
    "progress": job.progress,
    "progress_message": job.progress_message,
    # B2: surface auto-refine indicators for UI polling (None when not applicable)
    "refinement_status": getattr(job, "refinement_status", None),
    "auto_speaker_matches": getattr(job, "auto_speaker_matches", None),
    "learning_summary": getattr(job, "learning_summary", None),
    "learning_status": getattr(job, "learning_status", None),
}
```

Use `getattr(..., default)` to stay safe with jobs reloaded from the DB cache that pre-dates this change.

- [ ] **Step 2: Write a regression test for the response shape**

Add `backend/tests/test_auto_refine_orchestration.py`:

```python
"""B2 unit tests: TranscriptionSettings.auto_refine and orchestration wiring."""

import pytest


def test_auto_refine_defaults_to_none():
    from job_models import TranscriptionSettings
    s = TranscriptionSettings()
    assert s.auto_refine is None


def test_auto_refine_accepts_explicit_bool():
    from job_models import TranscriptionSettings
    assert TranscriptionSettings(auto_refine=True).auto_refine is True
    assert TranscriptionSettings(auto_refine=False).auto_refine is False


def test_transcription_job_has_b2_fields():
    from job_models import TranscriptionJob
    j = TranscriptionJob("test-job")
    assert j.refinement_status is None
    assert j.auto_speaker_matches is None
    assert j.learning_summary is None
    assert j.learning_status is None


@pytest.mark.asyncio
async def test_get_job_status_emits_b2_fields(client, sample_job):
    """GET /job/{id} response includes the 4 new B2 fields, even when None."""
    resp = await client.get(f"/job/{sample_job}")
    assert resp.status_code == 200
    body = resp.json()
    assert "refinement_status" in body
    assert "auto_speaker_matches" in body
    assert "learning_summary" in body
    assert "learning_status" in body
```

- [ ] **Step 3: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_auto_refine_orchestration.py -v 2>&1 | tail -15
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/job_models.py backend/routes/transcription.py backend/tests/test_auto_refine_orchestration.py
git commit -m "B2: add auto_refine setting + refinement/learning status fields on job"
```

---

## Task 7: B2 (part 2) — extract `_run_refinement_for_job` shared helper

**Files:**
- Modify: `backend/routes/refinement.py:19-47` — extract the body into `_run_refinement_for_job(job_id, speaker_ids=None, context_path=None)`; keep the existing `_run_refinement(job_id)` as a thin wrapper that calls the new helper with `(None, None)` (preserving today's manual-route behavior)

The auto-trigger in Task 8 will call `_run_refinement_for_job` directly with the settings from the completed job.

- [ ] **Step 1: Refactor `routes/refinement.py`**

Replace the existing `_run_refinement` body with:

```python
def _run_refinement_for_job(job_id: str, speaker_ids: Optional[List[str]] = None,
                            context_path: Optional[str] = None):
    """Run refinement for a completed job with the given context bundle.

    Loads the same context sources transcription used (global glossary +
    context_path + speaker bios) and feeds them to RefinementService.refine.
    Updates the job's refinement_status and the RefinementStore row.
    """
    from services.transcription import (
        load_context_document,
        load_speakers_context,
        merge_context_sources,
    )
    from services.glossary import load_global_glossary, load_global_glossary_terms

    job = state.job_store.get(job_id)
    try:
        state.refinement_store.update_status(job_id, "processing")
        if job is not None:
            job.refinement_status = "processing"
            try:
                state.jobs.update(job)
            except Exception:
                pass  # best-effort; the in-memory attr is what UI polls

        if not job:
            state.refinement_store.update_status(job_id, "failed", "Job not found")
            return

        if job.status != "completed":
            state.refinement_store.update_status(
                job_id, "failed", f"Job status is '{job.status}', not 'completed'"
            )
            if job is not None:
                job.refinement_status = "failed"
            return

        if not job.segments:
            state.refinement_store.update_status(job_id, "failed", "Job has no segments")
            if job is not None:
                job.refinement_status = "failed"
            return

        context_text = merge_context_sources(
            load_global_glossary(),
            load_context_document(context_path),
            load_speakers_context(speaker_ids),
        )
        glossary_terms = load_global_glossary_terms() or None

        result = state.refinement_service.refine(
            job.segments,
            context_text=context_text,
            glossary_terms=glossary_terms,
        )
        state.refinement_store.save_result(job_id, result)
        if job is not None:
            job.refinement_status = "done"
            try:
                state.jobs.update(job)
            except Exception:
                pass
        logger.info("Refinement complete for job %s", job_id)

    except Exception as e:
        logger.exception("Refinement failed for job %s", job_id)
        state.refinement_store.update_status(job_id, "failed", str(e))
        if job is not None:
            job.refinement_status = "failed"
            try:
                state.jobs.update(job)
            except Exception:
                pass


def _run_refinement(job_id: str):
    """Backwards-compatible wrapper: manual route uses no extra context."""
    _run_refinement_for_job(job_id, speaker_ids=None, context_path=None)
```

Add the necessary import near the top:

```python
from typing import List, Optional
```

(`List` may already be imported — check before duplicating.)

- [ ] **Step 2: Add an integration test**

Append to `backend/tests/test_auto_refine_orchestration.py`:

```python
def test_run_refinement_for_job_loads_context_and_calls_refine(icloud_base, monkeypatch):
    """The shared helper must load global glossary + context_path + speakers
    and forward them to RefinementService.refine."""
    import importlib
    from unittest.mock import MagicMock

    # Seed a global glossary so load_global_glossary returns content.
    (icloud_base / "contexts" / "_global.md").write_text(
        "# Global Glossary\n\n## Active\n\nManukai, Starrag\n",
        encoding="utf-8",
    )

    # Reload glossary so it picks up the patched ICLOUD_BASE_PATH
    import services.glossary
    importlib.reload(services.glossary)

    # Build a fake completed job
    from job_models import TranscriptionJob
    job = TranscriptionJob("job-1")
    job.status = "completed"
    job.segments = [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}]

    import state
    monkeypatch.setattr(state, "job_store", MagicMock(get=MagicMock(return_value=job)))
    monkeypatch.setattr(state, "jobs", MagicMock(update=MagicMock()))
    monkeypatch.setattr(state, "refinement_store", MagicMock(
        update_status=MagicMock(), save_result=MagicMock(),
    ))

    captured = {}
    def fake_refine(segments, context_text=None, glossary_terms=None):
        captured["context_text"] = context_text
        captured["glossary_terms"] = glossary_terms
        return {"analysis": {}, "refined_segments": segments,
                "speaker_mapping": {}, "corrections_applied": 0,
                "speakers_identified": 0, "web_searches_performed": 0}
    fake_service = MagicMock(refine=MagicMock(side_effect=fake_refine))
    monkeypatch.setattr(state, "refinement_service", fake_service)

    from routes.refinement import _run_refinement_for_job
    _run_refinement_for_job("job-1", speaker_ids=None, context_path=None)

    assert captured["context_text"] is not None
    assert "Manukai" in captured["context_text"]
    assert "Manukai" in (captured["glossary_terms"] or [])
    assert job.refinement_status == "done"
```

- [ ] **Step 3: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_auto_refine_orchestration.py -v 2>&1 | tail -15
```
Expected: 5 passed.

- [ ] **Step 4: Run the full backend suite for regressions**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: same baseline pass count + new Plan 1 tests.

- [ ] **Step 5: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/routes/refinement.py backend/tests/test_auto_refine_orchestration.py
git commit -m "B2: extract _run_refinement_for_job helper with context bundle"
```

---

## Task 8: B2 (part 3) — auto-trigger refinement after `_run_transcription_sync` completes

**Files:**
- Modify: `backend/services/transcription.py:776-781` — after `_update_job(..., status="completed")`, dispatch refinement on `state.transcription_executor` when the trigger condition holds
- Extend: `backend/tests/test_auto_refine_orchestration.py` — add the orchestrator decision tests

Trigger logic from spec section B2:

```
should_auto_refine = (
    settings.auto_refine is True
    or (settings.auto_refine is None and (settings.speaker_ids or settings.context_path))
)
should_auto_refine and state.refinement_available
```

- [ ] **Step 1: Write the failing decision-logic tests**

Append to `backend/tests/test_auto_refine_orchestration.py`:

```python
def test_auto_refine_decision_explicit_true():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    assert _should_auto_refine(TranscriptionSettings(auto_refine=True)) is True


def test_auto_refine_decision_explicit_false():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    s = TranscriptionSettings(auto_refine=False, speaker_ids=["sp-1"])
    assert _should_auto_refine(s) is False


def test_auto_refine_decision_default_with_speakers():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    s = TranscriptionSettings(speaker_ids=["sp-1"])
    assert _should_auto_refine(s) is True


def test_auto_refine_decision_default_with_context_path():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    s = TranscriptionSettings(context_path="deal/notes.md")
    assert _should_auto_refine(s) is True


def test_auto_refine_decision_default_with_neither():
    from job_models import TranscriptionSettings
    from services.transcription import _should_auto_refine
    assert _should_auto_refine(TranscriptionSettings()) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: ImportError on `_should_auto_refine`.

- [ ] **Step 3: Implement `_should_auto_refine` + dispatch in `transcription.py`**

Add the helper near `_update_job` (~line 509):

```python
def _should_auto_refine(settings: TranscriptionSettings) -> bool:
    """B2 trigger rule. Tri-state auto_refine: explicit True/False overrides;
    None means auto-on iff speaker_ids or context_path is set."""
    if settings.auto_refine is True:
        return True
    if settings.auto_refine is False:
        return False
    return bool(settings.speaker_ids or settings.context_path)
```

Then, in `_run_transcription_sync`, immediately after the line:

```python
_update_job(job, progress=100, message="Complete!", status="completed")
```

(~line 778) insert:

```python
if _should_auto_refine(settings) and state.refinement_available:
    # The submitting HTTP request returned long ago — dispatch via the
    # transcription executor (the same pool used for jobs). The helper
    # loads context + glossary itself.
    try:
        job.refinement_status = "pending"
        state.jobs.update(job)
    except Exception:
        pass
    try:
        from routes.refinement import _run_refinement_for_job
        state.refinement_store.create(job_id)
        state.transcription_executor.submit(
            _run_refinement_for_job,
            job_id,
            settings.speaker_ids,
            settings.context_path,
        )
        logger.info("B2: auto-refine dispatched for job %s", job_id)
    except Exception:
        logger.exception("B2: auto-refine dispatch failed for job %s", job_id)
```

The lazy `from routes.refinement import _run_refinement_for_job` avoids a circular import at module load time (services importing routes).

- [ ] **Step 4: Add the dispatch integration test**

Append to `backend/tests/test_auto_refine_orchestration.py`:

```python
def test_dispatch_submits_to_executor_when_conditions_met(tmp_path, monkeypatch):
    """When auto_refine triggers, _run_transcription_sync must submit
    _run_refinement_for_job to state.transcription_executor."""
    from unittest.mock import MagicMock, patch
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-A")
    job._retry_of = None

    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))

    submitted = []
    fake_exec = MagicMock(submit=MagicMock(side_effect=lambda *a, **k: submitted.append((a, k))))
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)

    settings = TranscriptionSettings(
        engine="whisper",
        language="en",
        enable_diarization=False,
        enable_noise_reduction=False,
        speaker_ids=["sp-1"],  # forces auto_refine in None mode
    )

    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 1, "text": "hi", "words": []}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-A", str(audio_path), settings)

    assert fake_exec.submit.called, "auto-refine must dispatch on the transcription executor"
    args, _ = submitted[0]
    # First arg is the function, then positional args (job_id, speaker_ids, context_path)
    assert args[1] == "job-A"
    assert args[2] == ["sp-1"]


def test_dispatch_skipped_when_refinement_unavailable(tmp_path, monkeypatch):
    from unittest.mock import MagicMock, patch
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-B")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", False)
    fake_exec = MagicMock(submit=MagicMock())
    monkeypatch.setattr(transcription.state, "transcription_executor", fake_exec)

    settings = TranscriptionSettings(
        engine="whisper", language="en", enable_diarization=False,
        enable_noise_reduction=False, speaker_ids=["sp-1"],
    )
    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 1, "text": "hi", "words": []}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-B", str(audio_path), settings)

    assert not fake_exec.submit.called
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_auto_refine_orchestration.py -v 2>&1 | tail -20
```
Expected: 12 passed (5 from Tasks 6-7 + 5 decision + 2 dispatch).

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/transcription.py backend/tests/test_auto_refine_orchestration.py
git commit -m "B2: auto-dispatch refinement on transcription completion"
```

---

## Task 9: B5 — inline auto-match speakers in the Whisper engine path

**Files:**
- Modify: `backend/services/transcription.py` — after diarization joins in the Whisper branch (~line 749, right after `transcription_segments = stitch_speaker_turns(transcription_segments)`), call `embedding_service.auto_identify_speakers` and overlay matched names
- Create: `backend/tests/test_inline_auto_match.py`

B5 reuses `_resolve_match_scope` (`routes/transcription.py:1217`) and the existing `auto_identify_speakers` service. The change is ~30 lines of glue. Apply only in the Whisper branch — Voxtral/Parakeet have their own diarization and don't currently emit pyannote-shaped `speakers` arrays compatible with `auto_identify_speakers`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_inline_auto_match.py`:

```python
"""B5 unit test: inline auto-match wiring in _run_transcription_sync (Whisper path)."""

from unittest.mock import MagicMock, patch


def test_inline_auto_match_overlays_names_when_diarization_present(tmp_path, monkeypatch):
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-M")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))
    monkeypatch.setattr(transcription.state, "transcription_executor",
                        MagicMock(submit=MagicMock()))

    # Stub diarization to return two speakers.
    monkeypatch.setattr(transcription, "run_diarization", lambda *a, **k: [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 10.0, "speaker": "SPEAKER_01"},
    ])
    monkeypatch.setattr(transcription, "assign_speakers_to_segments",
                        lambda segs, speakers: [
                            {"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"},
                            {"start": 5, "end": 10, "text": "bonjour", "speaker": "SPEAKER_01"},
                        ])
    monkeypatch.setattr(transcription, "stitch_speaker_turns", lambda segs: segs)

    # Stub the embedding service to "match" SPEAKER_00 → Pascal, leave SPEAKER_01 unmatched.
    fake_embedding = MagicMock()
    fake_embedding.auto_identify_speakers = MagicMock(return_value={
        "SPEAKER_00": {"name": "Pascal", "confidence": 0.91, "speaker_id": "sp-1",
                       "matched": True, "source": "pick"},
        "SPEAKER_01": {"name": None, "confidence": 0.3, "speaker_id": None,
                       "matched": False, "source": None},
    })
    monkeypatch.setattr(transcription.state, "get_speaker_embedding_service",
                        lambda: fake_embedding, raising=False)

    # Provide HF_TOKEN so diarization branch is taken.
    monkeypatch.setenv("HF_TOKEN", "fake-token")

    settings = TranscriptionSettings(
        engine="whisper", language="en",
        enable_diarization=True, enable_noise_reduction=False,
        speaker_ids=["sp-1"],
    )

    with patch("mlx_whisper.transcribe", return_value={
        "segments": [
            {"start": 0, "end": 5, "text": "hi", "words": [{"word": "hi", "start": 0, "end": 1, "probability": 1.0}]},
            {"start": 5, "end": 10, "text": "bonjour", "words": [{"word": "bonjour", "start": 5, "end": 6, "probability": 1.0}]},
        ],
        "text": "hi bonjour", "language": "en",
    }):
        transcription._run_transcription_sync("job-M", str(audio_path), settings)

    # auto_speaker_matches stored on the job
    assert job.auto_speaker_matches is not None
    assert job.auto_speaker_matches["SPEAKER_00"]["name"] == "Pascal"
    assert job.auto_speaker_matches["SPEAKER_00"]["matched"] is True

    # Segments overlay: SPEAKER_00 → Pascal, SPEAKER_01 left as is
    speakers_in_segments = [s.get("speaker") for s in job.segments]
    assert "Pascal" in speakers_in_segments
    assert "SPEAKER_01" in speakers_in_segments


def test_inline_auto_match_failure_does_not_break_job(tmp_path, monkeypatch):
    """Auto-match exceptions must be swallowed; segments keep SPEAKER_XX."""
    from job_models import TranscriptionSettings, TranscriptionJob
    from services import transcription

    audio_path = tmp_path / "fake.wav"
    audio_path.write_bytes(b"\x00" * 1024)

    job = TranscriptionJob("job-F")
    job._retry_of = None
    monkeypatch.setattr(transcription.state, "jobs",
                        MagicMock(get=MagicMock(return_value=job), update=MagicMock()))
    monkeypatch.setattr(transcription.state, "whisper_model_ready", True)
    # Must be True so the B5 branch executes; the test then asserts that
    # the exception inside auto_identify_speakers is swallowed and the job
    # still completes with original SPEAKER_XX labels intact.
    monkeypatch.setattr(transcription.state, "refinement_available", True)
    monkeypatch.setattr(transcription.state, "refinement_store", MagicMock(create=MagicMock()))
    monkeypatch.setattr(transcription.state, "transcription_executor",
                        MagicMock(submit=MagicMock()))
    monkeypatch.setattr(transcription, "run_diarization", lambda *a, **k: [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
    ])
    monkeypatch.setattr(transcription, "assign_speakers_to_segments",
                        lambda segs, speakers: [{"start": 0, "end": 5, "text": "hi", "speaker": "SPEAKER_00"}])
    monkeypatch.setattr(transcription, "stitch_speaker_turns", lambda segs: segs)

    fake_embedding = MagicMock()
    fake_embedding.auto_identify_speakers = MagicMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(transcription.state, "get_speaker_embedding_service",
                        lambda: fake_embedding, raising=False)
    monkeypatch.setenv("HF_TOKEN", "fake-token")

    settings = TranscriptionSettings(engine="whisper", language="en",
                                     enable_diarization=True, enable_noise_reduction=False)
    with patch("mlx_whisper.transcribe", return_value={
        "segments": [{"start": 0, "end": 5, "text": "hi",
                      "words": [{"word": "hi", "start": 0, "end": 1, "probability": 1.0}]}],
        "text": "hi", "language": "en",
    }):
        transcription._run_transcription_sync("job-F", str(audio_path), settings)

    # Job completed; auto_speaker_matches stays None; speakers untouched
    assert job.status == "completed"
    assert job.auto_speaker_matches is None
    assert job.segments[0]["speaker"] == "SPEAKER_00"
```

- [ ] **Step 2: Run tests to verify they fail**

Expected: assertions fail because the inline call doesn't exist yet.

- [ ] **Step 3: Implement the inline call in `_run_transcription_sync`**

In `backend/services/transcription.py`, the Whisper branch joins the diarization future around line 738 and runs `assign_speakers_to_segments` + `stitch_speaker_turns` at line 750-751. **Right after** the `if speakers:` block (immediately after line 751, before the `_update_job(job, progress=70, ...)` call), insert:

```python
            # B5: inline auto-match — overlay registered speaker names on
            # diarization labels using the voice-embedding registry. Reuses
            # the same scope logic as the post-job /speakers/auto-match route.
            if speakers and state.refinement_available:
                try:
                    from routes.transcription import _resolve_match_scope
                    restrict_ids, prefer_ids, _scope = _resolve_match_scope({
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
                except Exception:
                    logger.exception(
                        "B5 auto-match failed for job %s; keeping SPEAKER_XX labels", job_id
                    )
```

The gate `state.refinement_available` is the same gate used in B2 — both depend on Claude CLI availability for the downstream registry interaction, and both should fail-soft if missing.

(Note: both tests run with `state.refinement_available = True` so the B5 branch executes. The success test provides a working `auto_identify_speakers` stub; the failure-isolation test injects `RuntimeError("boom")` and asserts the `except Exception` swallows it — segments keep `SPEAKER_XX` labels and the job still finishes `completed`.)

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest tests/test_inline_auto_match.py -v 2>&1 | tail -15
```
Expected: 2 passed.

- [ ] **Step 5: Run the full suite for regressions**

Run:
```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: same baseline + all new Plan 1 tests pass.

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/transcription.py backend/tests/test_inline_auto_match.py
git commit -m "B5: inline speaker auto-match in Whisper transcription pipeline"
```

---

## Task 10: B8 — engine compatibility doc + README link

**Files:**
- Create: `docs/engines.md`
- Modify: `README.md` — add a one-line link under the "Architecture" section

No code change. The spec already confirmed `model_size = "voxtral-realtime-4b"` and `engine = "voxtral-local"` are the current defaults (`backend/job_models.py:380-382`).

- [ ] **Step 1: Create `docs/engines.md`**

Content:

```markdown
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
```

- [ ] **Step 2: Link from README**

Open `README.md` and add a line under the "Architecture" header (right after the existing bullet list around line 29), e.g.:

```markdown
- **Engine compatibility**: see [`docs/engines.md`](docs/engines.md) for which fixes/features apply to which transcription backend.
```

- [ ] **Step 3: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add docs/engines.md README.md
git commit -m "B8: document engine/feature compatibility matrix"
```

---

## Task 11: Bootstrap the `_global.md` template on iCloud (one-time)

**Files:**
- Create: `~/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/contexts/_global.md` (only if missing)

The file lives on iCloud, not in VCS. The template ships from the spec.

- [ ] **Step 1: Check whether the file already exists**

Run:
```bash
ls -la "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/contexts/_global.md" 2>&1 | head -3
```
If it exists, **skip steps 2-3** and continue to Task 12. Never overwrite a user-edited file.

- [ ] **Step 2: Write the template**

If missing, create with the spec-defined content:

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

Use the Write tool with absolute path:
`/Users/davidmarchesseau/Library/Mobile Documents/com~apple~CloudDocs/Davrine Transcription/contexts/_global.md`

- [ ] **Step 3: Seed the known proper nouns for the Pascal Weber validation**

Append a few seed terms to the **Active** section so Task 12 can demonstrate B1's effect end-to-end. Use the Edit tool to add under `## Active`:

```
- Manukai
- Pascal Weber
- Daniel
- Starrag
- DMG Mori
- Siemens
- ETH
```

(Optional but recommended — without seeds, B1's effect depends entirely on speaker bios + context_path being present.)

---

## Task 12: Manual validation gate — re-run the Pascal Weber audio

**Files:**
- None (manual run + record results in this task's commit message)

This gates Plan 2. Per the spec acceptance criterion: "Manukai", "DMG Mori", "Starrag" must appear correctly in the refined transcript. **Do not start Plan 2 until this passes.**

- [ ] **Step 1: Reload the backend daemon to pick up code changes**

Run:
```bash
launchctl kickstart -k "gui/$(id -u)/com.whisper.backend"
sleep 5
curl -sf http://127.0.0.1:8000/health > /dev/null && echo "backend OK" || echo "backend NOT READY"
```
Expected: `backend OK`.

- [ ] **Step 2: Locate the test audio**

The handoff résumé references `Tests/15-29-21.m4a` (already shipped by the A-plan). Confirm:

```bash
ls -la ~/Development/apps/whisper-transcription-app/Tests/15-29-21.m4a
```

- [ ] **Step 3: Submit a transcription job via the API with auto_refine triggers**

You'll need a speaker_id for Pascal Weber (the auto-refine trigger). List speakers:

```bash
curl -s http://127.0.0.1:8000/speakers/ | python3 -m json.tool | grep -E '"name"|"speaker_id"' | head -20
```

Grab Pascal Weber's `speaker_id`. Then submit:

```bash
SPEAKER_ID="<paste-pascal-id>"
curl -s -X POST http://127.0.0.1:8000/transcribe \
  -F "file=@$HOME/Development/apps/whisper-transcription-app/Tests/15-29-21.m4a" \
  -F "settings={\"engine\": \"whisper\", \"language\": \"auto\", \"enable_diarization\": true, \"speaker_ids\": [\"$SPEAKER_ID\"], \"auto_refine\": null}" \
  | tee /tmp/plan1-job.json
JOB_ID=$(python3 -c "import json; print(json.load(open('/tmp/plan1-job.json'))['job_id'])")
echo "JOB_ID=$JOB_ID"
```

- [ ] **Step 4: Poll until transcription completes**

```bash
until [ "$(curl -s "http://127.0.0.1:8000/job/$JOB_ID" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')" = "completed" ]; do sleep 5; done
echo "transcription completed"
```

- [ ] **Step 5: Confirm B2 dispatched auto-refine**

```bash
curl -s "http://127.0.0.1:8000/job/$JOB_ID" | python3 -m json.tool | grep -E '"refinement_status"|"auto_speaker_matches"' | head -10
```
Expected: `"refinement_status": "pending"` or `"processing"` very soon after completion; `"auto_speaker_matches"` populated with Pascal's match.

- [ ] **Step 6: Wait for refinement to land (~30-180s)**

```bash
until [ "$(curl -s "http://127.0.0.1:8000/refine/job/$JOB_ID" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')" = "completed" ]; do sleep 10; done
echo "refinement completed"
```

- [ ] **Step 7: Verify the proper-noun corrections landed**

```bash
curl -s "http://127.0.0.1:8000/refine/job/$JOB_ID/export?format=txt" > /tmp/refined.txt
grep -c "Manukai" /tmp/refined.txt
grep -c "DMG Mori" /tmp/refined.txt
grep -c "Starrag" /tmp/refined.txt
grep -c "Manuk AI\|BMG Mori\|Stara " /tmp/refined.txt
```
Acceptance: each correct spelling appears ≥1 time; each misspelling appears 0 times. If any misspelling survives, capture the Claude analysis JSON (`curl -s http://127.0.0.1:8000/refine/job/$JOB_ID | python3 -m json.tool | head -60`) to understand whether the term was missed, low-confidence, or absent from the glossary — then iterate on the glossary seed (Task 11 step 3) before retrying.

- [ ] **Step 8: Record the result**

Create a one-shot validation note (do not commit) at `/tmp/plan1-validation.md` with: job_id, refined-transcript snippet showing each of the three terms, full backend log tail (`tail -50 ~/.whisper-backend.log`). Paste the summary into the eventual handoff for Plan 2.

- [ ] **Step 9: Final regression run**

```bash
cd ~/Development/apps/whisper-transcription-app/backend && ./venv/bin/python -m pytest -x -q 2>&1 | tail -5
```
Expected: baseline + new Plan 1 tests, all green.

- [ ] **Step 10: Push the branch**

```bash
cd ~/Development/apps/whisper-transcription-app && git push origin dev
```

---

## Done criteria

Plan 1 is complete when:
- All 11 task commits land on `dev` and pass the full backend pytest suite.
- The Pascal Weber audio's refined transcript contains "Manukai", "DMG Mori", "Starrag" correctly spelled (Task 12 step 7).
- `docs/engines.md` exists and is linked from the README.
- The iCloud `_global.md` template is in place (Task 11).
- Backend daemon is restarted and serving the new code paths.

Plan 2 (continuous learning B7) and Plan 3 (UX B6) can start from this baseline.
