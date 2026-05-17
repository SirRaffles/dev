"""
Core transcription logic: MLX-Whisper and Parakeet engines.
"""

import os
import re
import asyncio
import logging
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

from config import ICLOUD_BASE_PATH, MLX_MODELS, PARAKEET_MODEL, PARAKEET_MODELS
from job_models import TranscriptionSettings
from services.audio import apply_noise_reduction
from services.diarization import run_diarization, assign_speakers_to_segments, stitch_speaker_turns
from services.postprocess import normalize_segments
import state

logger = logging.getLogger(__name__)

# Plan 4A: forward-declared for monkeypatching in tests. The real import
# happens lazily inside _run_transcription_sync to avoid the circular load
# (services.orchestrator imports from this module).
orchestrate_transcription = None  # type: ignore

# Cap the context document at ~4 KB of text; enough for a dense glossary, and
# keeps downstream prompt-length limits satisfied (MLX-Whisper tolerates
# ~224 tokens, we clamp further at use sites).
_CONTEXT_MAX_CHARS = 4000
# A context term is a word starting with an uppercase letter or digit, or any
# consecutive-uppercase acronym (SDG, SAFc, etc.). Used to derive context
# bias terms from a narrative markdown context.
_CONTEXT_TERM_RE = re.compile(r"\b[A-Z][A-Za-z0-9]{2,}(?:-[A-Za-z0-9]+)*\b|\b[A-Z]{2,}[0-9]*\b")


def load_context_document(context_path: Optional[str]) -> Optional[str]:
    """Load a user-selected context document from ICLOUD_BASE_PATH/contexts.

    `context_path` may point at either a specific .md file or a context
    folder. If a folder, we prefer `{folder}/context.md`; otherwise we
    pick the first top-level .md alphabetically. Returns None if the path
    is empty, unsafe, or unreadable.
    """
    if not context_path:
        return None
    rel = context_path.strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        logger.warning("Rejected context path: %s", context_path)
        return None
    contexts_root = (ICLOUD_BASE_PATH / "contexts").resolve()
    target = (contexts_root / rel).resolve()
    if not str(target).startswith(str(contexts_root)):
        logger.warning("Context path escapes CONTEXTS_DIR: %s", context_path)
        return None

    # Directory? Auto-discover the primary .md inside.
    if target.is_dir():
        candidate = target / "context.md"
        if not candidate.is_file():
            md_files = sorted(
                p for p in target.iterdir()
                if p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith(".")
            )
            candidate = md_files[0] if md_files else None  # type: ignore
        if candidate is None or not candidate.is_file():
            logger.warning("No .md file found in context folder: %s", target)
            return None
        target = candidate

    if not target.is_file():
        logger.warning("Context file not found: %s", target)
        return None
    try:
        text = target.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("Failed to read context %s: %s", target, exc)
        return None
    if not text.strip():
        return None
    return text[:_CONTEXT_MAX_CHARS]


def derive_context_terms(context_text: Optional[str], limit: int = 100) -> List[str]:
    """Extract domain terms (proper nouns, acronyms) from a context document.

    Used as a context bias list when the caller didn't provide an explicit
    terms list (e.g., for downstream glossary derivation).
    """
    if not context_text:
        return []
    seen = []
    seen_lower = set()
    for match in _CONTEXT_TERM_RE.finditer(context_text):
        term = match.group(0).strip()
        if 2 <= len(term) <= 40 and term.lower() not in seen_lower:
            seen_lower.add(term.lower())
            seen.append(term)
            if len(seen) >= limit:
                break
    return seen


def load_speakers_context(speaker_ids: Optional[List[str]]) -> Optional[str]:
    """Concatenate the personality.md of every expected speaker into one blob.

    Used to seed transcription with domain/biographical context the user
    already knows about the people likely on the recording — spellings of
    names, recurring topics, jargon they use — which helps Whisper get
    proper nouns right on the first pass.
    """
    if not speaker_ids:
        return None
    speakers_root = (ICLOUD_BASE_PATH / "speakers").resolve()
    pieces: List[str] = []
    for sid in speaker_ids:
        if not sid:
            continue
        try:
            speaker = state.speaker_store.get(sid)
        except Exception:
            speaker = None
        if not speaker:
            continue
        name = speaker.get("name", "").strip()
        if not name:
            continue
        # Safe-resolve the speaker's folder first; reject any name that
        # resolves outside the speakers tree (defense-in-depth on names).
        speaker_dir = (speakers_root / name).resolve()
        if not str(speaker_dir).startswith(str(speakers_root)):
            continue
        # Merge the 4 profile files (3 markdown + we skip the .npy voice
        # file). Order matches the product spec: bio → explicit → implicit.
        # Legacy personality.md is a fallback for older data that was never
        # migrated in this session.
        sections: List[str] = []
        for fname in ("profile.md", "explicit_insights.md", "implicit_insights.md", "personality.md"):
            try:
                fpath = speaker_dir / fname
                if not fpath.is_file():
                    continue
                chunk = fpath.read_text(encoding="utf-8", errors="ignore").strip()
                # Skip placeholder scaffolding so we don't pollute the prompt.
                if not chunk or "will land here" in chunk or "*No personality insights yet" in chunk:
                    continue
                sections.append(chunk)
            except OSError:
                continue
        if sections:
            joined = "\n\n".join(sections)
            pieces.append(f"# Speaker: {name}\n\n{joined}")
    if not pieces:
        return None
    combined = "\n\n---\n\n".join(pieces)
    return combined[: _CONTEXT_MAX_CHARS * 2]  # allow a bit more headroom


def merge_context_sources(*texts: Optional[str]) -> Optional[str]:
    """Concatenate multiple context blobs (context doc + speakers) into one."""
    parts = [t.strip() for t in texts if t and t.strip()]
    if not parts:
        return None
    return "\n\n---\n\n".join(parts)


def build_initial_prompt(context_text: Optional[str], max_chars: int = 900) -> Optional[str]:
    """Build a short initial_prompt from a context doc, clamped to Whisper's
    token budget (Whisper decoder ctx is 448 tokens; half for input keeps
    headroom for audio). ~900 chars ≈ ~200 tokens for English; shorter for
    many European languages.
    """
    if not context_text:
        return None
    cleaned = " ".join(context_text.split())
    return cleaned[:max_chars] if cleaned else None

# Parakeet model keys accepted by the `model_size` setting.
# "parakeet" is a legacy alias for the English v2 model.
_PARAKEET_ALIASES = {
    "parakeet": "parakeet-en-v2",
    "parakeet-en-v2": "parakeet-en-v2",
    "parakeet-multi-v3": "parakeet-multi-v3",
}


def is_parakeet_key(model_size: str) -> bool:
    """Return True if model_size selects any Parakeet variant."""
    return model_size in _PARAKEET_ALIASES


def resolve_parakeet_key(model_size: str) -> str:
    """Normalize a Parakeet model_size to a canonical PARAKEET_MODELS key."""
    return _PARAKEET_ALIASES.get(model_size, "parakeet-en-v2")


def get_mlx_model_path():
    """Get the MLX-Whisper model path based on environment or default."""
    model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3-turbo")
    model_info = MLX_MODELS.get(model_size, MLX_MODELS["large-v3-turbo"])
    return model_info["path"]


def select_optimal_model(language: str, model_size: str, speed_priority: bool = False) -> str:
    """Select the optimal model based on language and speed preference."""
    if speed_priority and language == "en":
        if state._parakeet_available:
            return "parakeet"
        return "large-v3-turbo"
    return model_size


def transcribe_with_parakeet(audio_path: str, model_key: str = "parakeet-en-v2") -> dict:
    """Transcribe audio using Parakeet MLX (60x real-time on Apple Silicon).

    Args:
        audio_path: Path to the input audio file.
        model_key: Key into PARAKEET_MODELS. Defaults to the English v2 model
            for backwards compatibility with callers that don't specify a variant.
    """
    import parakeet_mlx

    model_key = resolve_parakeet_key(model_key)
    model_info = PARAKEET_MODELS[model_key]
    model_path = model_info["path"]
    language_tag = model_info.get("language", "en")

    logger.info("Transcribing with Parakeet MLX (%s)...", model_key)

    # Cache a single loaded model per process. Reload if the user switched variant.
    cached_path = getattr(state, "_parakeet_model_path", None)
    if state._parakeet_model is None or cached_path != model_path:
        logger.info("Loading Parakeet model: %s", model_path)
        state._parakeet_model = parakeet_mlx.from_pretrained(model_path)
        state._parakeet_model_path = model_path
        logger.info("Parakeet model loaded successfully")

    result = state._parakeet_model.transcribe(audio_path)

    segments = []
    all_text_parts = []

    if hasattr(result, 'tokens') and result.tokens:
        for token in result.tokens:
            text_part = ""
            start_time = 0.0
            end_time = 0.0

            if hasattr(token, 'text'):
                text_part = str(token.text).strip()
            elif hasattr(token, '__str__'):
                text_part = str(token).strip()

            if hasattr(token, 'start'):
                start_time = float(token.start)
            if hasattr(token, 'end'):
                end_time = float(token.end)

            if text_part:
                all_text_parts.append(text_part)
                segments.append({
                    "start": start_time,
                    "end": end_time,
                    "text": text_part,
                })
    elif hasattr(result, '__str__'):
        text = str(result).strip()
        all_text_parts.append(text)
        segments.append({"start": 0, "end": 0, "text": text})

    full_text = " ".join(all_text_parts)

    # For the multilingual model we don't know the detected language without
    # extra inference; label as the canonical tag ("en" for v2, "multi" for v3).
    return {
        "text": full_text,
        "segments": segments,
        "language": language_tag,
    }


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


def _should_auto_refine(settings: TranscriptionSettings) -> bool:
    """B2 trigger rule. Tri-state auto_refine: explicit True/False overrides;
    None means auto-on iff speaker_ids or context_path is set."""
    if settings.auto_refine is True:
        return True
    if settings.auto_refine is False:
        return False
    return bool(settings.speaker_ids or settings.context_path)


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


def _run_transcription_sync(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Synchronous transcription worker — runs in the thread pool.

    Routes to the orchestrator based on settings.engine. All quality-mode
    composition lives in services.orchestrator; this function is now a
    routing shim plus the tmp-audio cleanup guard.
    """
    # Local import — services.orchestrator imports from this module, so a
    # top-level import would be circular at module load time.
    from services.orchestrator import orchestrate_transcription as _orchestrate
    # Allow tests to monkeypatch the module-level name.
    _dispatch = orchestrate_transcription or _orchestrate

    job = state.jobs.get(job_id)
    if not job:
        return

    try:
        if settings.engine == "auto-best":
            _dispatch(job_id, audio_path, settings, mode="best")
        elif settings.engine == "auto-quick":
            _dispatch(job_id, audio_path, settings, mode="quick")
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


async def transcribe_audio(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Run transcription in thread pool to keep event loop responsive."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        state.transcription_executor,
        _run_transcription_sync,
        job_id,
        audio_path,
        settings
    )
