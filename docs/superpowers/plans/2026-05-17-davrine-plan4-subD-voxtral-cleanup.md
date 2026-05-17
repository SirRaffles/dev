# Davrine Quality Dial — Plan 4 Sub-plan D (Voxtral surface removal sweep) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete every dead reference to the Voxtral transcription engine (cloud + local) from the backend, frontend, docs, and deploy config. Pure cleanup — zero behavior changes — so the codebase reflects what Sub-plans A + C have already enforced at runtime: only `auto-best` and `auto-quick` exist.

**Architecture:** Sequential single-layer sweeps. Each task removes Voxtral from one cohesive layer (services module → state/init → model_manager → routes/config → frontend hook+SettingsPanel → docs+deploy) and ends with the test suite + the type-checker green. Sequencing minimises the window where a partially-deleted symbol breaks an import elsewhere: services first (the deepest leaf), then the bootstrap glue that imported it, then the routes/config that surfaced it, then the frontend that consumed it, then docs/deploy that documented it.

**Tech Stack:** Backend Python 3.11 (FastAPI on uvicorn, pydantic v2, pytest), frontend React 18 + TypeScript (Vite 6, tsc in `--noEmit` mode), `nginx.conf` + `docker-compose.yml` for deploy. No new runtime deps — this plan only removes code.

---

## Hard prerequisites (must already be true on `dev`)

This sub-plan **cannot start** until:

1. **Sub-plan A is shipped and merged.** The backend `TranscriptionSettings.engine` is `Literal["auto-best", "auto-quick"]`. `_run_transcription_sync` no longer calls `transcribe_with_voxtral` or `transcribe_with_voxtral_local` from any code path. The orchestrator at `backend/services/orchestrator.py` exists and owns dispatch.
2. **Sub-plan C is shipped and merged.** The frontend `SettingsPanel.tsx` no longer renders the 3-engine selector. `App.tsx` defaults `settings.engine` to `'auto-best'`. The `Settings.engine` type in the frontend is narrowed to `'auto-best' | 'auto-quick'`.
3. **Verify prereqs** before starting. Run from repo root:

   ```bash
   cd ~/Development/apps/whisper-transcription-app

   # Backend: no production call sites for Voxtral transcribers
   grep -rn "transcribe_with_voxtral" backend/ --include="*.py" \
     | grep -v "backend/services/transcription.py" \
     | grep -v "backend/tests/"
   # Expected: zero matches. transcription.py still defines the functions (we delete them here);
   # tests may still reference fixtures (we migrate them here).

   # Backend: engine literal already narrowed
   grep -n 'engine.*Literal' backend/job_models.py
   # Expected: a line containing Literal["auto-best", "auto-quick"]

   # Frontend: dial in place
   grep -n "Quality" src/components/SettingsPanel.tsx | head
   # Expected: the new Quality dial markup is present
   ```

   If any check above fails: **STOP and report `BLOCKED`** — Sub-plan A and/or C are not live yet.

---

## File structure

This is a delete-heavy plan. Most touches are full-file deletions or surgical removals. Here is the complete inventory by task.

### Task 1 — Backend services layer (Voxtral module + transcription functions)

**Delete:**
- `backend/services/voxtral_service.py` — entire file (~200 LOC, `VoxtralService` class for Mistral Voxtral REST API)

**Modify:**
- `backend/services/__init__.py` — drop the `VoxtralService` import + `__all__` entry
- `backend/services/transcription.py` — delete `transcribe_with_voxtral()` (line ~279) and `transcribe_with_voxtral_local()` (line ~358), including any Voxtral-only imports they pull in at module scope (`from services.voxtral_service import VoxtralService`, mlx-audio Voxtral helpers, etc.)

### Task 2 — State, main, model_manager (lifecycle / bootstrap)

**Modify:**
- `backend/state.py` lines 79-93 — delete the Voxtral block:
  - `_voxtral_available`, `_voxtral_service`
  - `_voxtral_local_available`, `_voxtral_local_model`, `_voxtral_local_model_name`
  - the `try: from mlx_audio.stt.utils import load as _mlx_audio_load … except ImportError: pass` block that sets `_voxtral_local_available = True`
- `backend/main.py` lines 140-145, 153-161 — delete:
  - the `if state._voxtral_local_available: …` log block
  - the entire `mistral_api_key = os.environ.get("MISTRAL_API_KEY")` instantiation block (loads `VoxtralService`)
- `backend/services/model_manager.py`:
  - Remove `ModelName.VOXTRAL_LOCAL = "voxtral_local"` (line 25)
  - Remove the `ModelName.VOXTRAL_LOCAL: { … }` entry from `ModelConfig.CONFIGS` (lines 57-65)
  - Delete `async def load_voxtral_local(self, model_path: str) -> bool:` (lines 373-422) in its entirety
  - Remove the `if model_name == ModelName.VOXTRAL_LOCAL: …` branch from `unload_model` (lines 457-463)

### Task 3 — Config + routes (`/models`, `/health`, constants)

**Modify:**
- `backend/config.py` — delete `VOXTRAL_MODELS` (line ~89), `VOXTRAL_LOCAL_MODELS` (line ~103), `VOXTRAL_LOCAL_LANGUAGES` (line ~122) constants
- `backend/routes/models_api.py`:
  - Line 11: drop `VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS` from the `from config import …` line (keep `SUPPORTED_LANGUAGES, MLX_MODELS, PARAKEET_MODELS`)
  - Lines 66, 69-70: remove `"voxtral_available": state._voxtral_available` and the `"voxtral-local"` / `"voxtral-api"` entries from `engines` dict in `/health`
  - Lines 101-117: delete the two `if state._voxtral_local_available:` / `if state._voxtral_available:` blocks that append Voxtral models in `list_models`
  - Lines 123-124: remove `"voxtral_local_available"` and `"voxtral_available"` keys from `/models` response
  - Lines 135-152: delete the `"voxtral-local"` and `"voxtral-api"` entries from the `engine_capabilities` dict (keep only `"whisper"`)
- `backend/job_models.py` lines 398, 405:
  - Delete `context_terms: Optional[List[str]] = None`
  - Delete `two_pass: bool = False`
  - Delete `speed_priority` if present (search before deleting; Sub-plan A may have already dropped it)

### Task 4 — Frontend hook + App.tsx + SettingsPanel + api.ts

**Delete:**
- `src/hooks/useEngineAvailability.ts` — entire file

**Modify:**
- `src/App.tsx`:
  - Line 20: remove `import useEngineAvailability from './hooks/useEngineAvailability';`
  - Lines 100-104: remove the entire `const { voxtralAvailable, voxtralLocalAvailable, backendError, fallbackNotice, dismissFallbackNotice, refreshEngines } = useEngineAvailability();` destructuring
  - Lines 106-112: simplify the `useWakeOnLan({ onAwake: async () => { const fallback = await refreshEngines(); if (fallback) setSettings(prev => ({...prev, ...fallback})); } })` — drop the `onAwake` callback entirely (or pass `onAwake: undefined`, matching the hook's existing optional signature)
  - Line 315-320 region: delete the `{fallbackNotice && ( … )}` JSX block
  - Lines 426-427: remove the `voxtralAvailable={voxtralAvailable}` and `voxtralLocalAvailable={voxtralLocalAvailable}` props from `<SettingsPanel … />`
- `src/components/SettingsPanel.tsx`:
  - Line 3: drop `MODEL_SIZES, VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS` from the `import { … } from '../utils/api'` (keep `LANGUAGES`, `fetchContextTree`, etc.)
  - Lines 28-29: remove the `voxtralAvailable?: boolean;` and `voxtralLocalAvailable?: boolean;` props from `SettingsPanelProps`
  - Lines 40-41: remove the `voxtralAvailable = false, voxtralLocalAvailable = false,` defaults from the destructuring
  - Lines 13-19: drop the `speedPriority?: boolean; engine?: string; contextTerms?: string; twoPass?: boolean;` keys from `Settings` (Sub-plan C should already have narrowed `engine`; verify before removing)
  - Lines 51-56: drop `speedPriority`, `contextTerms`, `twoPass` from the destructuring defaults
  - **Engine capability disclosure block** (lines 275-293 region, `{/* Engine capability disclosure — surface which post-transcription …*/}`): delete entirely. The original block was added in Plan 3 commit `c5e4a53`.
  - **Word Timestamps engine-gating logic** (added in Plan 3 commit `4f57b10`): grep for `wordTimestamps` inside SettingsPanel.tsx and remove any engine-conditional disable / hide. Word Timestamps remains a user-visible knob; only the engine-asymmetry conditional disappears.
  - **Speed Priority knob**: grep `speedPriority` in SettingsPanel.tsx and remove the entire form control (label + input + handler).
  - **Two-Pass Mode knob**: grep `twoPass` in SettingsPanel.tsx and remove the entire form control + the `useEffect(() => { if (!isVoxtralApi && twoPass) … })` at line 172-176.
  - **Context Terms knob**: grep `contextTerms` in SettingsPanel.tsx and remove the entire form control.
- `src/utils/api.ts`:
  - Lines 173-192: delete the `ENGINES` constant
  - Lines 195-210: delete the `MODEL_SIZES` constant
  - Lines 213-215: delete `VOXTRAL_MODELS`
  - Lines 218-222: delete `VOXTRAL_LOCAL_MODELS`
  - Lines 19-23: simplify `HealthResponse` — drop `voxtral_available?` and `engines?` fields (their values are gone from the backend `/health` in Task 3)
  - Lines 103-118 (`TranscriptionOptions`): drop `modelSize?`, `speedPriority?`, `twoPass?`, `contextTerms?` fields. Verify Sub-plan C already narrowed `engine?: string;` to `engine?: 'auto-best' | 'auto-quick';` — if not, narrow it now.
  - Lines 120-125: delete `EngineInfo` interface (only ENGINES used it)

### Task 5 — Docs + deploy config

**Delete:**
- `docs/engines.md` — entire file (replaced by inline help on the Quality dial in Sub-plan C)

**Modify:**
- `README.md`:
  - Remove the line `- **Engine compatibility**: see [`docs/engines.md`](docs/engines.md) for which fixes/features apply to which transcription backend.` (currently line 32). The exact verbatim line is what `grep -n "engines.md" README.md` reports.
- `docker-compose.yml`:
  - Remove the `- MISTRAL_API_KEY=${MISTRAL_API_KEY:-}` env-var passthrough (currently line 13)
- `.claude/settings.local.json`:
  - Run `grep -n "voxtral\|MISTRAL" .claude/settings.local.json`. The only match should be line 90 — a `Bash(find …/mlx_audio/stt/models/voxtral* …)` permission that targets the venv. **Leave that entry alone** (it's a pytest-related permission that doesn't reference our app code). If any other entry surfaces, remove it.

---

## Conventions for all tasks

- **Branch:** `dev`. Each task is its own commit. Push only after Task 5 + the post-plan verification gate (below) both pass.
- **Commit hygiene:** The working tree may contain ~22 unrelated WIP files. Always `git add <specific files>` — **never** `git add -A` or `git add .`. Each commit's `git diff --stat` should mention only the files this plan touches.
- **Verification cadence:** After every task, run:
  ```bash
  cd ~/Development/apps/whisper-transcription-app/backend
  ./venv/bin/python -m pytest tests/ -q
  cd ..
  npx tsc --noEmit
  ```
  Backend pytest **must stay green** (no skips, no errors). Frontend TypeScript **must report zero errors**. If either fails: stop, diagnose, fix in the same task before committing. Never commit a red tree.
- **Grep-driven completeness:** After every task, run the per-task grep checks listed in that task's final step. They are the "is this layer truly Voxtral-free?" gate.
- **No behavior changes.** This plan deletes dead code. If you find yourself adding logic or changing a behavior, stop — it's out of scope.
- **No silent test deletions.** If a test fails because it asserts on a Voxtral-specific path that no longer exists, **delete the test** (and note it in the commit message). Don't `pytest.skip` it. Don't keep the file around for "historical reference".
- **Python style:** Match the file you're editing. The codebase doesn't use a formatter that re-flows whole files. Keep your diff minimal.
- **TypeScript style:** `tsconfig.json` has `strict: false, allowJs: true`. Don't introduce strict-mode-only patterns. Keep the diff minimal.

---

## Task 1: Delete the backend Voxtral service module + transcription functions

**Files:**
- Delete: `backend/services/voxtral_service.py`
- Modify: `backend/services/__init__.py` (remove import + `__all__`)
- Modify: `backend/services/transcription.py` (delete `transcribe_with_voxtral`, `transcribe_with_voxtral_local`, drop now-orphan imports)

This task is the leaf of the dependency tree — nothing inside `services/` (after Sub-plans A + C) should still reach for Voxtral. We cut here first so the symbols are gone before anyone else imports them.

- [ ] **Step 1: Confirm prereq — no remaining production call sites**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -rn "transcribe_with_voxtral\|transcribe_with_voxtral_local" backend/ --include="*.py" \
  | grep -v "backend/services/transcription.py" \
  | grep -v "backend/tests/"
```

Expected: **zero output**. If any line appears, **STOP and report `BLOCKED`** — Sub-plan A is not fully landed.

- [ ] **Step 2: Delete `backend/services/voxtral_service.py`**

```bash
cd ~/Development/apps/whisper-transcription-app
rm backend/services/voxtral_service.py
```

- [ ] **Step 3: Remove `VoxtralService` from `backend/services/__init__.py`**

Open `backend/services/__init__.py`. Final state of the file:

```python
# Multi-modal services
from .model_manager import ModelManager
from .vision_service import VisionService
from .document_service import DocumentService

__all__ = [
    "ModelManager",
    "VisionService",
    "DocumentService",
]
```

- [ ] **Step 4: Delete `transcribe_with_voxtral` and `transcribe_with_voxtral_local` from `backend/services/transcription.py`**

```bash
cd ~/Development/apps/whisper-transcription-app
# Locate the two function definitions to know the byte ranges:
grep -n "^def transcribe_with_voxtral\|^def transcribe_with_voxtral_local\|^def " backend/services/transcription.py | head -20
```

Use the printed line numbers to delete:
- `def transcribe_with_voxtral(audio_path: str, settings: TranscriptionSettings) -> dict:` (starts ~line 279) through to the next top-level `def …:` (exclusive). This is the Voxtral Cloud function.
- `def transcribe_with_voxtral_local(audio_path: str, settings: TranscriptionSettings, job=None) -> dict:` (starts ~line 358) through to the next top-level `def …:` (exclusive). This is the Voxtral Local (mlx-audio) function.

After deletion, also remove any now-unused imports at the top of the file. Run:

```bash
grep -n "voxtral\|VoxtralService\|mlx_audio.*stt\|mlx_audio_load" backend/services/transcription.py
```

For every line that prints: delete the corresponding import or reference (if it's a comment that names "Voxtral", remove the comment too). The grep should print **nothing** when you're done.

- [ ] **Step 5: Verify backend imports still resolve**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -c "import services.transcription; import services; print('ok')"
```

Expected: prints `ok` with no `ImportError`. If you get `ImportError: cannot import name 'VoxtralService'` or similar, find the still-stale importer and fix it in this task.

- [ ] **Step 6: Run pytest**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -m pytest tests/ -q
```

Expected: all tests green. If a test fails because it imports `transcribe_with_voxtral*` directly, **delete the test** (the function no longer exists; the behavior is covered by orchestrator tests added in Sub-plan A).

- [ ] **Step 7: Run the per-task grep gate**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -rn "VoxtralService\|transcribe_with_voxtral\|transcribe_with_voxtral_local" backend/services/ --include="*.py"
```

Expected: **zero matches**.

- [ ] **Step 8: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/services/__init__.py backend/services/transcription.py
git add -u backend/services/voxtral_service.py   # stages the deletion
git status --short                                # confirm: only these 3 files
git commit -m "Plan 4D Task 1: delete Voxtral service module + transcription functions"
```

---

## Task 2: Strip Voxtral from state, main, and model_manager (lifecycle)

**Files:**
- Modify: `backend/state.py` (lines ~79-93)
- Modify: `backend/main.py` (lines ~140-145, ~153-161)
- Modify: `backend/services/model_manager.py` (line 25, lines 57-65, lines 373-422, lines 457-463)

Task 1 cut the leaves. Now we cut the bootstrap glue that imported them. After this task, no Voxtral state survives in process memory.

- [ ] **Step 1: Edit `backend/state.py`**

Delete the entire Voxtral block (currently lines 79-93):

```python
# Voxtral cloud transcription state
_voxtral_available = False
_voxtral_service = None

# Voxtral local transcription state (via mlx-audio)
_voxtral_local_available = False
_voxtral_local_model = None
_voxtral_local_model_name = None

# Check if mlx-audio is available for local Voxtral
try:
    from mlx_audio.stt.utils import load as _mlx_audio_load
    _voxtral_local_available = True
except ImportError:
    pass
```

Leave the surrounding comments (`# Parakeet state.` block) intact. After the edit, the file should jump directly from `diarization_pipeline = None` to the `# Parakeet state.` comment.

Also update the executor docstring at lines ~69-72 — the existing comment says "Diarization (pyannote) + transcription (Whisper/Voxtral)…". Change "Whisper/Voxtral" to just "Whisper".

- [ ] **Step 2: Edit `backend/main.py`**

Delete the Voxtral Local availability log block (currently lines 140-145):

```python
# Check for Voxtral Local availability (via mlx-audio)
if state._voxtral_local_available:
    logger.info("Voxtral Local: Available (mlx-audio installed)")
    logger.info("Note: Voxtral model will be downloaded on first use if not cached")
else:
    logger.info("Voxtral Local: Not available (install mlx-audio for local Voxtral transcription)")
```

Delete the Voxtral API instantiation block (currently lines 153-161):

```python
# Check for Voxtral API availability
mistral_api_key = os.environ.get("MISTRAL_API_KEY")
if mistral_api_key:
    from services.voxtral_service import VoxtralService
    state._voxtral_service = VoxtralService(mistral_api_key)
    state._voxtral_available = True
    logger.info("Voxtral API: Available (MISTRAL_API_KEY set)")
else:
    logger.info("Voxtral API: Not configured (set MISTRAL_API_KEY for cloud transcription)")
```

- [ ] **Step 3: Edit `backend/services/model_manager.py`**

Remove the enum value at line 25:

```python
class ModelName(str, Enum):
    WHISPER = "whisper"
    VISION = "vision"
    DIARIZATION = "diarization"
    EMBEDDING = "embedding"
    # (DELETE this line) VOXTRAL_LOCAL = "voxtral_local"
```

Delete the entire `ModelName.VOXTRAL_LOCAL: { … }` entry from `ModelConfig.CONFIGS` (lines 57-65):

```python
        ModelName.VOXTRAL_LOCAL: {
            "priority": 1,
            "memory_mb": 3500,
            "unloadable": True,
            "load_timeout": 120,
        },
```

Delete the entire `async def load_voxtral_local(self, model_path: str) -> bool:` method (lines 373-422) — about 50 LOC, ending just before `def unload_model(…)`.

Delete the `VOXTRAL_LOCAL` branch from `unload_model` (lines 457-463):

```python
            if model_name == ModelName.VOXTRAL_LOCAL:
                try:
                    import state as state_mod
                    state_mod._voxtral_local_model = None
                    state_mod._voxtral_local_model_name = None
                except Exception:
                    pass
```

- [ ] **Step 4: Verify imports + boot**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -c "import main; print('ok')"
```

Expected: prints `ok`. Any `AttributeError: module 'state' has no attribute '_voxtral_*'` means some leftover reader survived — grep for it and fix:

```bash
grep -rn "_voxtral_available\|_voxtral_service\|_voxtral_local" backend/ --include="*.py" \
  | grep -v "backend/tests/" | grep -v "venv/" | grep -v __pycache__
```

Expected: **zero matches** outside `backend/tests/`. (Task 3 will address `routes/models_api.py`; if that's the only remaining hit, that's expected.) Wait — actually, `routes/models_api.py` still references `state._voxtral_available` until Task 3. So acceptable matches here are **only** in `backend/routes/models_api.py`. If anything else appears, fix it before committing.

- [ ] **Step 5: Run pytest**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -m pytest tests/ -q
```

Expected: green. If a model_manager unit test references `ModelName.VOXTRAL_LOCAL` or `load_voxtral_local`, delete it (the model no longer exists).

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/state.py backend/main.py backend/services/model_manager.py
git status --short
git commit -m "Plan 4D Task 2: remove Voxtral from state, main, and model_manager"
```

---

## Task 3: Strip Voxtral from config, routes, and TranscriptionSettings

**Files:**
- Modify: `backend/config.py` (delete `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`, `VOXTRAL_LOCAL_LANGUAGES`)
- Modify: `backend/routes/models_api.py` (strip Voxtral from `/models` + `/health`)
- Modify: `backend/job_models.py` (drop `speed_priority`, `two_pass`, `context_terms` from `TranscriptionSettings`)

After Task 2, the routes layer is the last place still reading `state._voxtral_*`. This task seals it.

- [ ] **Step 1: Edit `backend/config.py`**

Locate the three Voxtral constants:

```bash
cd ~/Development/apps/whisper-transcription-app
grep -n "VOXTRAL_MODELS\|VOXTRAL_LOCAL_MODELS\|VOXTRAL_LOCAL_LANGUAGES" backend/config.py
```

Delete each constant in its entirety (including the dictionary body and any surrounding comments that name only Voxtral). After deletion, grep should print **zero matches**.

- [ ] **Step 2: Edit `backend/routes/models_api.py`**

The decision in the spec is: "Either retire `/models` entirely or keep only `whisper` + `parakeet`." Keep `/models` — the frontend (post Sub-plan C) doesn't use it heavily but third-party tools (`curl`, dev probes) may. Strip it to `whisper` + `parakeet` only.

Concrete edits:

Line 11 — import statement:

```python
# Before:
from config import SUPPORTED_LANGUAGES, MLX_MODELS, PARAKEET_MODELS, VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS
# After:
from config import SUPPORTED_LANGUAGES, MLX_MODELS, PARAKEET_MODELS
```

Line 66 — remove the `voxtral_available` field from `/health` response:

```python
# Delete this line:
        "voxtral_available": state._voxtral_available,
```

Lines 67-71 — narrow the `engines` dict in `/health` to just whisper:

```python
        "engines": {
            "whisper": {"available": state.whisper_model_ready, "type": "local"},
        },
```

Lines 101-117 — delete both `if state._voxtral_local_available:` and `if state._voxtral_available:` blocks that append models in `list_models`. After deletion, the function should append Whisper (from `MLX_MODELS`) + Parakeet (already gated by `state._parakeet_available`) only.

Lines 123-124 — remove the two Voxtral availability flags from the `/models` response payload:

```python
# Delete these two lines:
        "voxtral_local_available": state._voxtral_local_available,
        "voxtral_available": state._voxtral_available,
```

Lines 135-152 — narrow the `engine_capabilities` dict to whisper only:

```python
        "engine_capabilities": {
            "whisper": {
                "context_bias": False,
                "timestamps": True,
                "word_timestamps": True,
                "diarization": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")),
                "translation": True,
                "noise_reduction": True,
                "two_pass": False,
            },
        },
```

(Delete the entire `"voxtral-local": { … }` and `"voxtral-api": { … }` sub-dicts.)

- [ ] **Step 3: Edit `backend/job_models.py` — clean `TranscriptionSettings`**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -n "speed_priority\|two_pass\|context_terms" backend/job_models.py
```

For each match in `class TranscriptionSettings`, delete the field. Expected deletions:

```python
    context_terms: Optional[List[str]] = None
    two_pass: bool = False
```

And `speed_priority` if it exists (Sub-plan A may have already removed it). After this edit, `TranscriptionSettings` should contain only the fields that the orchestrator + UI surface: `beam_size`, `patience`, `best_of`, `vad_filter`, `word_timestamps`, `language`, `enable_diarization`, `num_speakers`, `enable_noise_reduction`, `translate_to_english`, `engine`, `context_path`, `speaker_ids`, `original_filename`, `output_mode`, `auto_refine`. (Plus whatever Sub-plan A added like a `phase` field elsewhere — those are not in `TranscriptionSettings`.)

If `Optional[List[str]]` is now unused, drop `List` from the `from typing import …` line at the top of the file (but only if the grep confirms zero remaining uses). Don't break unrelated typing imports.

- [ ] **Step 4: Verify boot + grep gate**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -c "import main; print('ok')"

# Final backend grep: nothing should mention Voxtral in production code.
cd ~/Development/apps/whisper-transcription-app
grep -rn "voxtral\|Voxtral\|VOXTRAL\|MISTRAL_API_KEY" backend/ --include="*.py" \
  | grep -v "backend/venv/" \
  | grep -v "backend/__pycache__/" \
  | grep -v "backend/tests/"
```

Expected: **zero matches** in production (`backend/services/`, `backend/routes/`, `backend/main.py`, `backend/state.py`, `backend/config.py`, `backend/job_models.py`).

If matches survive in `backend/tests/`, that's OK for this step — Sub-plan A should have already migrated them; if any test still references Voxtral and pytest passes, leave it for the final gate.

- [ ] **Step 5: Run pytest**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -m pytest tests/ -q
```

Expected: green. Common failures and their fixes:
- `KeyError: 'voxtral-local'` in a `/models` response test → update the test to assert the new (Voxtral-free) shape.
- `AttributeError: TranscriptionSettings has no attribute 'two_pass'` → the test was constructing settings with `two_pass=…`; remove the kwarg.
- A test asserts `voxtral_available` in `/health` → update the assertion to not expect that field.

- [ ] **Step 6: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add backend/config.py backend/routes/models_api.py backend/job_models.py
# Stage any test edits made in Step 5:
git add -u backend/tests/
git status --short
git commit -m "Plan 4D Task 3: strip Voxtral from config, /models, /health, TranscriptionSettings"
```

---

## Task 4: Delete frontend Voxtral surfaces (hook, App.tsx, SettingsPanel, api.ts)

**Files:**
- Delete: `src/hooks/useEngineAvailability.ts`
- Modify: `src/App.tsx`
- Modify: `src/components/SettingsPanel.tsx`
- Modify: `src/utils/api.ts`

By this point the backend's `/health` no longer returns `voxtral_available` or an `engines` dict containing Voxtral, so the frontend hook reading those fields produces dead UI. Time to remove the consumer side.

- [ ] **Step 1: Delete the hook**

```bash
cd ~/Development/apps/whisper-transcription-app
rm src/hooks/useEngineAvailability.ts
```

- [ ] **Step 2: Edit `src/App.tsx`**

Remove the import (line 20):

```typescript
// Delete this line:
import useEngineAvailability from './hooks/useEngineAvailability';
```

Remove the destructuring (lines 100-104):

```typescript
// Delete this block:
  const {
    voxtralAvailable, voxtralLocalAvailable, backendError,
    fallbackNotice, dismissFallbackNotice, refreshEngines,
  } = useEngineAvailability();
```

`backendError` is part of this destructuring. Grep for it elsewhere in `App.tsx`:

```bash
grep -n "backendError" src/App.tsx
```

If it's read anywhere (e.g. a "Cannot connect to backend" banner), either:
- (a) Replace its source: if there's an existing wake-status / backend-reachability signal elsewhere, point the banner at that instead.
- (b) Delete the banner entirely if backend reachability is already surfaced by `useWakeOnLan`.

Pick (b) by default — `useWakeOnLan` already exposes `macState` and the wake-proxy flow surfaces connection issues with the existing wake UI. Confirm by grepping `backendError` again after the edit; result must be zero matches.

Simplify the `useWakeOnLan` call (lines 106-112):

```typescript
// Before:
  const { macState, setMacState, wakeStartTime, detectProxy, triggerWake, queueSubmit, hasPendingSubmit } =
    useWakeOnLan({
      onAwake: async () => {
        const fallback = await refreshEngines();
        if (fallback) setSettings(prev => ({ ...prev, ...fallback }));
      },
    });

// After:
  const { macState, setMacState, wakeStartTime, detectProxy, triggerWake, queueSubmit, hasPendingSubmit } =
    useWakeOnLan();
```

If `useWakeOnLan` requires an options arg, pass `useWakeOnLan({})`. Check the hook's signature:

```bash
grep -n "export default\|^export function\|^function useWakeOnLan" src/hooks/useWakeOnLan.ts
```

Remove the fallback-notice JSX (~lines 315-320):

```tsx
// Delete this entire block:
        {fallbackNotice && (
          <div className="…">
            <span className="text-blue-300 text-sm flex-1">{fallbackNotice}</span>
            <button onClick={dismissFallbackNotice}>…</button>
          </div>
        )}
```

Remove the props from `<SettingsPanel … />` (~lines 426-427):

```tsx
// Delete these two prop lines:
            voxtralAvailable={voxtralAvailable}
            voxtralLocalAvailable={voxtralLocalAvailable}
```

- [ ] **Step 3: Edit `src/components/SettingsPanel.tsx` — imports + props + state**

Line 3 — narrow the import:

```typescript
// Before:
import { LANGUAGES, MODEL_SIZES, VOXTRAL_MODELS, VOXTRAL_LOCAL_MODELS, fetchContextTree, ContextTree, fetchSpeakers, createSpeaker, Speaker } from '../utils/api';
// After:
import { LANGUAGES, fetchContextTree, ContextTree, fetchSpeakers, createSpeaker, Speaker } from '../utils/api';
```

Lines 5-21 — clean the `Settings` interface. Remove these keys:

```typescript
  // Delete:
  modelSize?: string;
  speedPriority?: boolean;
  engine?: string;
  contextTerms?: string;
  twoPass?: boolean;
```

(Verify Sub-plan C already narrowed `engine` to the dial values. If `engine?: string` is still here, Sub-plan C is incomplete — STOP and report BLOCKED.)

Lines 23-30 — drop the two Voxtral props from `SettingsPanelProps`:

```typescript
// Delete:
  voxtralAvailable?: boolean;
  voxtralLocalAvailable?: boolean;
```

Lines 35-42 — drop them from the destructuring:

```typescript
function SettingsPanel({
  settings,
  onSettingsChange,
  showForDocuments = false,
  disabled = false,
  // Delete the next two:
  voxtralAvailable = false,
  voxtralLocalAvailable = false,
}: SettingsPanelProps) {
```

Lines 44-58 — drop the field defaults that no longer exist on `Settings`:

```typescript
// Delete these defaults:
    modelSize = 'large-v3-turbo',
    speedPriority = false,
    engine = 'voxtral-local',   // (Sub-plan C should have already removed this)
    contextTerms = '',
    twoPass = false,
```

- [ ] **Step 4: Edit `src/components/SettingsPanel.tsx` — body cleanups**

Find and remove every remaining reference. Grep first:

```bash
cd ~/Development/apps/whisper-transcription-app
grep -n "isVoxtral\|isWhisper\|voxtralAvailable\|voxtralLocalAvailable\|VOXTRAL\|MODEL_SIZES\|speedPriority\|twoPass\|contextTerms\|PARAKEET_KEYS" src/components/SettingsPanel.tsx
```

For each match, delete the surrounding logic. The grep should be **empty** when you're done. Expected deletions (referencing line numbers from the pre-cleanup file):

- **Lines ~32-33** — `PARAKEET_KEYS` set and any `isParakeet` derivation. The orchestrator owns Parakeet selection; the panel never references it.
- **Lines ~172-176** — `useEffect(() => { if (!isVoxtralApi && twoPass) … })` — gone with `twoPass`.
- **Lines ~178-201** — `isLanguageSupported`, `supportedLabel` helpers — these existed to gate per-engine language restrictions. Remove if unused (grep after removing the model-size dropdown).
- **Lines ~203-206** — `isParakeet`, `currentModelInfo`, `parakeetLanguageInvalid` — remove.
- **Lines ~224-273** — the 3-button engine selector (Voxtral Local / Whisper / Cloud). Sub-plan C replaced this with the Quality dial; if any vestige of the old buttons survived (the grep should catch this), remove it.
- **Lines ~275-293** — engine capability disclosure block (`{/* Engine capability disclosure — surface which post-transcription … */}` … `<span>Voice auto-match, refinement, glossary learning, and insights all run …`). Delete the entire `<div>`.
- **Lines ~328-387** — the "Model Size Selection — different options per engine" section, including the three branches `isVoxtralApi ? … : isVoxtralLocal ? … : …`. Sub-plan C replaced this with the Quality dial; if any vestige survives, remove it.
- **Any Word Timestamps form control that uses an engine conditional**: if you find `wordTimestamps` form control wrapped in `{isWhisper && …}` or similar, remove the conditional but **keep the control** (Word Timestamps remains user-visible; only the gating disappears).
- **Speed Priority form control** — find the `<label>` / `<input>` that toggles `speedPriority` and delete it.
- **Two-Pass Mode form control** — find the `<label>` / `<input>` that toggles `twoPass` and delete it.
- **Context Terms form control** — find the `<label>` / `<input>` / `<textarea>` that edits `contextTerms` and delete it.

Verify by running the grep again — output must be empty.

- [ ] **Step 5: Edit `src/utils/api.ts`**

Lines 19-23 — narrow `HealthResponse`:

```typescript
// Before:
export interface HealthResponse {
  status: string;
  voxtral_available?: boolean;
  engines?: Record<string, { available: boolean }>;
}
// After:
export interface HealthResponse {
  status: string;
}
```

(If `HealthResponse` itself is now unused — `useEngineAvailability` was its only consumer — delete the interface entirely. Grep first:

```bash
grep -n "HealthResponse" src/
```

Zero matches → delete the interface.)

Lines 103-118 — clean `TranscriptionOptions`. Remove these fields:

```typescript
  modelSize?: string;
  speedPriority?: boolean;
  twoPass?: boolean;
  contextTerms?: string;
```

If `engine?: string;` is still loose, narrow to `engine?: 'auto-best' | 'auto-quick';`. (Sub-plan C should have done this; verify.)

Lines 120-125 — delete `EngineInfo` interface (only `ENGINES` consumed it):

```typescript
// Delete:
export interface EngineInfo {
  label: string;
  description: string;
  type: string;
  cost: string | null;
}
```

Lines 127-134 — review `ModelInfo`. It was used by `MODEL_SIZES`, `VOXTRAL_MODELS`, `VOXTRAL_LOCAL_MODELS`. Grep:

```bash
grep -rn "ModelInfo" src/
```

If zero hits remain after this task's deletions, delete the interface.

Lines 173-222 — delete the four constants in one block:

```typescript
// Delete in order:
export const ENGINES: Record<string, EngineInfo> = { … };          // 173-192
export const MODEL_SIZES: Record<string, ModelInfo> = { … };       // 195-210
export const VOXTRAL_MODELS: Record<string, ModelInfo> = { … };    // 213-215
export const VOXTRAL_LOCAL_MODELS: Record<string, ModelInfo> = { … };  // 218-222
```

- [ ] **Step 6: TypeScript verify**

```bash
cd ~/Development/apps/whisper-transcription-app
npx tsc --noEmit
```

Expected: zero errors. Common errors and fixes:
- `Cannot find name 'MODEL_SIZES'` in some other file → either remove the consumer or unblock by importing nothing (depends on the consumer). Grep `MODEL_SIZES` across `src/` to find leftovers and clean each one.
- `Cannot find name 'VOXTRAL_*'` → same pattern.
- `Property 'voxtralAvailable' does not exist on type 'SettingsPanelProps'` → some other call site of `<SettingsPanel … />` still passes the prop. Find and remove (grep `voxtralAvailable=` across `src/`).
- `Property 'modelSize' does not exist on type 'Settings'` → some other component reads `settings.modelSize`. Grep and remove the read.

Iterate `npx tsc --noEmit` → fix until clean.

- [ ] **Step 7: Final frontend grep gate**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -rn "voxtral\|Voxtral\|VOXTRAL\|useEngineAvailability\|MODEL_SIZES" src/
```

Expected: **zero matches** anywhere in `src/`.

- [ ] **Step 8: Run frontend build (smoke test)**

```bash
cd ~/Development/apps/whisper-transcription-app
npm run build
```

Expected: build succeeds. The Vite bundle should still emit. If the build fails on a Tailwind purge issue or an unresolved import, fix it before committing.

- [ ] **Step 9: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add src/App.tsx src/components/SettingsPanel.tsx src/utils/api.ts
git add -u src/hooks/useEngineAvailability.ts   # stages the deletion
git status --short
git commit -m "Plan 4D Task 4: delete frontend Voxtral surfaces (hook, ENGINES, MODEL_SIZES, settings knobs)"
```

---

## Task 5: Delete docs, README link, docker-compose env var

**Files:**
- Delete: `docs/engines.md`
- Modify: `README.md` (remove the link added in Plan 1 Task 10)
- Modify: `docker-compose.yml` (remove `MISTRAL_API_KEY` passthrough)
- Verify: `.claude/settings.local.json` (leave the one venv-path permission alone)

This is the documentation/deploy sweep. Nothing here touches runtime — purely housekeeping so a new reader doesn't find docs pointing at deleted code.

- [ ] **Step 1: Delete `docs/engines.md`**

```bash
cd ~/Development/apps/whisper-transcription-app
rm docs/engines.md
```

- [ ] **Step 2: Edit `README.md`**

Locate the link added in Plan 1 Task 10:

```bash
grep -n "engines.md\|Engine compatibility" README.md
```

Expected match (currently line 32):

```markdown
- **Engine compatibility**: see [`docs/engines.md`](docs/engines.md) for which fixes/features apply to which transcription backend.
```

Delete that line. If the surrounding list now leaves a dangling empty bullet or a blank section header, tidy it (a single removed line in the middle of a list is fine; only intervene if the surrounding markdown structure breaks).

Re-grep to confirm zero matches:

```bash
grep -n "engines.md\|Engine compatibility" README.md
```

Expected: zero output.

- [ ] **Step 3: Edit `docker-compose.yml`**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -n "MISTRAL_API_KEY" docker-compose.yml
```

Expected match (currently line 13):

```yaml
      - MISTRAL_API_KEY=${MISTRAL_API_KEY:-}
```

Delete that line. Re-grep — zero matches expected.

Also check `docker-compose.local.yml`:

```bash
grep -n "MISTRAL_API_KEY\|voxtral" docker-compose.local.yml 2>/dev/null
```

If matches exist, delete those lines too.

- [ ] **Step 3b: Edit `.env.example`** (added per code review)

The onboarding template still references the dead env var.

```bash
cd ~/Development/apps/whisper-transcription-app
grep -n "MISTRAL_API_KEY" .env.example
```

Expected match (line ~25):
```
# MISTRAL_API_KEY=your_mistral_api_key_here
```

Delete that line. Re-grep — zero matches expected.

**Do NOT touch the user's actual `~/Development/apps/whisper-transcription-app/.env`** if it exists — the user may have a real key there for unrelated services. If `MISTRAL_API_KEY` exists in `.env`, flag it to the user; do not delete without confirmation.

- [ ] **Step 4: Audit `.claude/settings.local.json`**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -n "voxtral\|Voxtral\|MISTRAL" .claude/settings.local.json
```

Expected: only **one** match — line ~90, a `Bash(find …/mlx_audio/stt/models/voxtral* …)` permission that targets the Python venv directory (not our app code). That entry is harmless and unrelated to our codebase's Voxtral integration; it permits an investigative `find` over the still-installed `mlx_audio` package. **Leave it alone.**

If any **other** entry mentions our own code paths (e.g. `whisper-transcription-app/.../voxtral_service.py`), remove that entry.

- [ ] **Step 5: Verification — repo-wide grep**

```bash
cd ~/Development/apps/whisper-transcription-app
grep -rin "VoxtralService\|voxtral_service\|transcribe_with_voxtral\|MISTRAL_API_KEY\|useEngineAvailability\|VOXTRAL_MODELS\|VOXTRAL_LOCAL_MODELS\|MODEL_SIZES\|ENGINES\|engines.md" \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  --include="*.md" --include="*.yml" --include="*.yaml" \
  . 2>/dev/null \
  | grep -v "backend/venv/" \
  | grep -v "node_modules/" \
  | grep -v "backend/__pycache__/" \
  | grep -v "docs/superpowers/plans/" \
  | grep -v "docs/superpowers/specs/" \
  | grep -v "backend/tests/test_youtube.py"
```

Expected: **zero matches**.

**Acknowledged false-positives** (these paths intentionally keep references):
- `docs/superpowers/plans/` + `docs/superpowers/specs/` legitimately reference these symbols as part of describing the cleanup.
- `backend/tests/test_youtube.py` lines ~149 + ~177 have generic env-scrubbing security tests that mention `MISTRAL_API_KEY` as a representative secret to scrub from subprocess env. These assertions pass whether or not the env var is set — leave them alone.

If any match survives outside those excluded paths: investigate, remove, and re-run the grep until clean.

- [ ] **Step 6: Run the full test + type-check suite**

```bash
cd ~/Development/apps/whisper-transcription-app/backend
./venv/bin/python -m pytest tests/ -q

cd ~/Development/apps/whisper-transcription-app
npx tsc --noEmit
```

Both must be green.

- [ ] **Step 7: Manual smoke test (optional but recommended)**

Boot the backend and the frontend, submit a short audio file in both Best mode and Quick mode, confirm:
- Both transcriptions complete end-to-end.
- The Settings panel shows the Quality dial only (no engine buttons, no model dropdown, no Speed Priority / Two-Pass / Context Terms knobs).
- The browser console shows no `404` for any Voxtral-related API call.
- The backend log shows no `Voxtral` mentions on startup.

If the smoke test surfaces a leftover reference, fix it before committing.

- [ ] **Step 8: Commit**

```bash
cd ~/Development/apps/whisper-transcription-app
git add README.md docker-compose.yml
git add -u docs/engines.md   # stages the deletion
# Stage docker-compose.local.yml only if you edited it:
git diff --name-only docker-compose.local.yml 2>/dev/null && git add docker-compose.local.yml
git status --short
git commit -m "Plan 4D Task 5: delete engines.md, README link, MISTRAL_API_KEY compose entry"
```

---

## Post-plan verification gate (before pushing to remote)

Run all four checks. Any failure means a task missed something — go back and fix in a new commit on top of Task 5.

```bash
cd ~/Development/apps/whisper-transcription-app

# 1. No production code references Voxtral anywhere
grep -rn "voxtral\|Voxtral\|VOXTRAL\|MISTRAL_API_KEY\|useEngineAvailability" \
  --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
  --include="*.md" --include="*.yml" --include="*.yaml" \
  . 2>/dev/null \
  | grep -v "backend/venv/" \
  | grep -v "node_modules/" \
  | grep -v "backend/__pycache__/" \
  | grep -v "docs/superpowers/plans/" \
  | grep -v "docs/superpowers/specs/" \
  | grep -v ".claude/settings.local.json:90"  # the venv-find permission, harmless
# Expected: empty.

# 2. Backend tests green
cd backend && ./venv/bin/python -m pytest tests/ -q && cd ..

# 3. Frontend type-check clean
npx tsc --noEmit

# 4. Frontend builds
npm run build
```

If all four pass, Plan 4 is complete. Push:

```bash
cd ~/Development/apps/whisper-transcription-app
git log --oneline -6   # confirm Tasks 1-5 commits are present
git push origin dev
```

---

## Self-review notes

- **Spec coverage:** Every removal listed in the spec's "Removed completely — Backend" and "Removed completely — Frontend" subsections maps to a task above (Task 1 = services; Task 2 = state/main/model_manager; Task 3 = config/routes/TranscriptionSettings; Task 4 = frontend hook + SettingsPanel + api.ts; Task 5 = docs/deploy). The spec's "Removed completely — Docs / config" list is fully covered by Task 5.
- **Test fixture migration is OUT of scope for this plan.** Per the spec, test-fixture migration is Sub-plan A's job (see spec §"Test fixture migration (Sub-plan A includes this)"). Sub-plan D only deletes tests that *break* because the underlying function they exercise no longer exists (e.g. a unit test for `transcribe_with_voxtral` directly).
- **JPR watcher** is OUT of scope for this plan. Per the spec, `watcher/config.py` is Sub-plan A's job.
- **No new behavior.** Every step is either a delete or a narrow type. The plan does not add code.
- **Atomicity:** Each task ends with pytest + tsc clean before commit. The repo is never left red between commits.
