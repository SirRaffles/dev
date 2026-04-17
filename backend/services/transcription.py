"""
Core transcription logic: MLX-Whisper, Parakeet, Voxtral engines.
"""

import os
import asyncio
import logging
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import MLX_MODELS, PARAKEET_MODEL, PARAKEET_MODELS, VOXTRAL_LOCAL_MODELS
from job_models import TranscriptionSettings
from services.audio import apply_noise_reduction
from services.diarization import run_diarization, assign_speakers_to_segments, stitch_speaker_turns
from services.postprocess import normalize_segments, apply_readable_mode
import state

logger = logging.getLogger(__name__)

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


def transcribe_with_voxtral(audio_path: str, settings: TranscriptionSettings) -> dict:
    """Transcribe audio using Voxtral Mini Transcribe V2 (Mistral API)."""
    if not state._voxtral_service:
        raise RuntimeError("Voxtral API not configured. Set MISTRAL_API_KEY environment variable.")

    language = None if settings.language == "auto" else settings.language

    # Two-pass mode: get both timestamps and language accuracy (2x API cost)
    if settings.two_pass and language:
        logger.info("Transcribing with Voxtral Mini (cloud API, two-pass mode)...")
        result = state._voxtral_service.transcribe_two_pass(
            audio_path=audio_path,
            language=language,
            enable_diarization=settings.enable_diarization,
            word_timestamps=settings.word_timestamps,
            context_terms=settings.context_terms,
        )
    else:
        logger.info("Transcribing with Voxtral Mini (cloud API)...")
        result = state._voxtral_service.transcribe(
            audio_path=audio_path,
            language=language or "auto",
            enable_diarization=settings.enable_diarization,
            word_timestamps=settings.word_timestamps,
            context_terms=settings.context_terms,
        )

    return result


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _extract_audio_chunk(audio_path: str, start: float, duration: float, output_path: str) -> bool:
    """Extract a chunk of audio as 16kHz mono WAV for Voxtral."""
    import subprocess
    try:
        # Audit #10: -ss must precede -i for keyframe seek.
        subprocess.run(
            ["ffmpeg", "-ss", str(start), "-i", audio_path, "-t", str(duration),
             "-ar", "16000", "-ac", "1", output_path, "-y", "-loglevel", "error"],
            capture_output=True, timeout=60, check=True,
        )
        return True
    except Exception:
        return False


def transcribe_with_voxtral_local(audio_path: str, settings: TranscriptionSettings) -> dict:
    """Transcribe audio using Voxtral Mini 3B locally via mlx-audio.

    Automatically chunks audio into 30-second segments (the encoder's max)
    and merges results with correct timestamps.
    """
    import tempfile
    from services.model_manager import get_model_manager, ModelName

    CHUNK_DURATION = 30  # seconds — Voxtral encoder max (WhisperFeatureExtractor chunk_length)
    MAX_TOKENS_PER_CHUNK = 4096

    # Determine which model variant to use
    model_key = settings.model_size if settings.model_size in VOXTRAL_LOCAL_MODELS else "voxtral-mini-3b"
    model_path = VOXTRAL_LOCAL_MODELS[model_key]["path"]

    logger.info("Transcribing with Voxtral Local (%s)...", model_path)

    # Audit #12: route through ModelManager so memory accounting is respected.
    manager = get_model_manager()
    model = None
    if manager.is_loaded(ModelName.VOXTRAL_LOCAL) and manager.get_model(ModelName.VOXTRAL_LOCAL) is not None:
        cached = manager.get_model(ModelName.VOXTRAL_LOCAL)
        if isinstance(cached, dict) and cached.get("path") == model_path:
            model = cached.get("model")

    if model is None:
        _loop = asyncio.new_event_loop()
        try:
            loaded = _loop.run_until_complete(manager.load_voxtral_local(model_path))
        finally:
            _loop.close()
        if not loaded:
            raise RuntimeError("Failed to load Voxtral Local model")
        cached = manager.get_model(ModelName.VOXTRAL_LOCAL)
        model = cached.get("model") if isinstance(cached, dict) else cached

    language = settings.language if settings.language != "auto" else None

    # Get total duration to determine chunking
    total_duration = _get_audio_duration(audio_path)
    if total_duration <= 0:
        total_duration = CHUNK_DURATION  # fallback: treat as single chunk

    num_chunks = max(1, int(total_duration / CHUNK_DURATION) + (1 if total_duration % CHUNK_DURATION > 0.5 else 0))
    logger.info("Audio duration: %.1fs, splitting into %d chunk(s) of %ds", total_duration, num_chunks, CHUNK_DURATION)

    segments = []
    all_text_parts = []

    for i in range(num_chunks):
        chunk_start = i * CHUNK_DURATION
        chunk_dur = min(CHUNK_DURATION, total_duration - chunk_start)
        if chunk_dur < 0.5:
            break

        # Extract chunk as WAV
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if not _extract_audio_chunk(audio_path, chunk_start, chunk_dur, tmp_path):
                logger.warning("Failed to extract chunk %d (%.1fs-%.1fs), skipping", i, chunk_start, chunk_start + chunk_dur)
                continue

            gen_kwargs = {"max_tokens": MAX_TOKENS_PER_CHUNK}
            if language:
                gen_kwargs["language"] = language

            result = model.generate(tmp_path, **gen_kwargs)

            # Parse chunk result
            chunk_text = ""
            if hasattr(result, "text"):
                chunk_text = str(result.text).strip()
            elif isinstance(result, dict):
                chunk_text = result.get("text", "").strip()
            elif isinstance(result, str):
                chunk_text = result.strip()
            else:
                chunk_text = str(result).strip()

            if chunk_text and chunk_text != ".":
                segments.append({
                    "start": chunk_start,
                    "end": chunk_start + chunk_dur,
                    "text": chunk_text,
                })
                all_text_parts.append(chunk_text)

            logger.info("Chunk %d/%d (%.0fs-%.0fs): %d chars", i + 1, num_chunks, chunk_start, chunk_start + chunk_dur, len(chunk_text))

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    full_text = " ".join(all_text_parts)

    return {
        "text": full_text,
        "segments": segments,
        "language": language or "auto",
    }


def _update_job(job, progress: int = None, message: str = None, status: str = None):
    """Update job fields and persist to DB so progress survives restarts."""
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.progress_message = message
    state.jobs.update(job)


def _run_transcription_sync(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Synchronous transcription worker - runs in thread pool."""
    job = state.jobs.get(job_id)

    if not job:
        return

    use_voxtral = settings.engine == "voxtral-api"
    use_voxtral_local = settings.engine == "voxtral-local"
    use_parakeet = is_parakeet_key(settings.model_size) and not use_voxtral and not use_voxtral_local

    if use_voxtral:
        if not state._voxtral_available:
            job.status = "failed"
            job.error = "Voxtral API not configured. Set MISTRAL_API_KEY environment variable."
            state.jobs.update(job)
            return
    elif use_voxtral_local:
        if not state._voxtral_local_available:
            job.status = "failed"
            job.error = "Voxtral Local not available. Install with: pip install mlx-audio"
            state.jobs.update(job)
            return
    elif use_parakeet:
        if not state._parakeet_available:
            job.status = "failed"
            job.error = "Parakeet MLX not installed. Install with: pip install parakeet-mlx"
            state.jobs.update(job)
            return
    elif not state.whisper_model_ready:
        job.status = "failed"
        job.error = "MLX-Whisper not configured. Please restart the server."
        state.jobs.update(job)
        return

    try:
        _update_job(job, progress=5, message="Starting transcription...", status="processing")

        if settings.enable_noise_reduction:
            _update_job(job, progress=8, message="Applying noise reduction...")
            # Audit #15: use Path.with_stem for safe suffix append.
            src = Path(audio_path)
            cleaned_audio_path = str(src.with_stem(src.stem + "_cleaned"))
            audio_path = apply_noise_reduction(audio_path, cleaned_audio_path)

        # === VOXTRAL API ENGINE ===
        if use_voxtral:
            _update_job(job, progress=15, message="Transcribing with Voxtral (cloud API)...")

            result = transcribe_with_voxtral(audio_path, settings)

            job.language = result.get("language", "unknown")
            job.language_probability = 0.99

            transcription_segments = result.get("segments", [])
            full_text = result.get("text", "")

            voxtral_speakers = result.get("speakers", [])
            if voxtral_speakers:
                job.speakers = [{"speaker": s} for s in voxtral_speakers]
                transcription_segments = stitch_speaker_turns(transcription_segments)

        else:
            # === LOCAL ENGINES (Whisper / Parakeet / Voxtral Local) ===
            # Audit #9: diarize concurrently with transcription via a side executor.
            speakers = []
            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
            diarization_future = None
            diarization_executor = None

            if settings.enable_diarization and hf_token:
                if settings.num_speakers:
                    _update_job(job, progress=10, message=f"Identifying {settings.num_speakers} speakers...")
                else:
                    _update_job(job, progress=10, message="Identifying speakers...")
                diarization_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="diarize")
                diarization_future = diarization_executor.submit(
                    run_diarization, audio_path, settings.num_speakers
                )
            elif settings.enable_diarization and not hf_token:
                logger.warning(
                    "Diarization requested but HF_TOKEN is not set. "
                    "Skipping speaker identification."
                )

            if use_voxtral_local:
                if settings.word_timestamps:
                    logger.warning("word_timestamps=True ignored: Voxtral Local does not support word-level timestamps")
                _update_job(job, progress=20, message="Transcribing with Voxtral Local (~4% WER)...")
                logger.info("Using Voxtral Local for transcription")

                result = transcribe_with_voxtral_local(audio_path, settings)

                job.language = result.get("language", "auto")
                job.language_probability = 0.99

                transcription_segments = result.get("segments", [])
                full_text = result.get("text", "")

            elif use_parakeet:
                if settings.word_timestamps:
                    logger.warning("word_timestamps=True ignored: Parakeet does not support word-level timestamps")

                parakeet_key = resolve_parakeet_key(settings.model_size)
                parakeet_info = PARAKEET_MODELS[parakeet_key]
                _update_job(
                    job,
                    progress=20,
                    message=f"Transcribing with Parakeet MLX ({parakeet_key})...",
                )
                logger.info("Using Parakeet MLX for transcription: %s", parakeet_key)

                result = transcribe_with_parakeet(audio_path, parakeet_key)

                # v2 is English-only; v3 is multilingual — keep label consistent.
                job.language = parakeet_info.get("language", "en")
                job.language_probability = 0.99

                transcription_segments = result.get("segments", [])
                full_text = result.get("text", "")

            else:
                import mlx_whisper

                _update_job(job, progress=20, message="Transcribing with MLX-Whisper (GPU-accelerated)...")

                language = None if settings.language == "auto" else settings.language

                model_info = MLX_MODELS.get(settings.model_size, MLX_MODELS["large-v3-turbo"])
                model_path = model_info["path"]
                logger.info("Using model: %s (%s)", settings.model_size, model_path)

                result = mlx_whisper.transcribe(
                    audio_path,
                    path_or_hf_repo=model_path,
                    language=language,
                    task="translate" if settings.translate_to_english else "transcribe",
                    word_timestamps=settings.word_timestamps,
                    condition_on_previous_text=True,
                    no_speech_threshold=0.6,
                    compression_ratio_threshold=2.4,
                    verbose=False,
                    fp16=True,
                )

                job.language = result.get("language", "unknown")
                job.language_probability = 0.99

                transcription_segments = []
                full_text_parts = []

                for segment in result.get("segments", []):
                    seg_data = {
                        "start": segment["start"],
                        "end": segment["end"],
                        "text": segment["text"].strip(),
                    }

                    if settings.word_timestamps and "words" in segment:
                        seg_data["words"] = [
                            {
                                "word": w.get("word", w.get("text", "")),
                                "start": w["start"],
                                "end": w["end"],
                                "probability": w.get("probability", 1.0)
                            }
                            for w in segment["words"]
                        ]

                    transcription_segments.append(seg_data)
                    full_text_parts.append(segment["text"].strip())

                full_text = result.get("text", " ".join(full_text_parts))

            # Join the concurrent diarization (audit #9). Never let a diarization
            # failure prevent transcription from being returned.
            if diarization_future is not None:
                try:
                    speakers = diarization_future.result() or []
                    job.speakers = speakers
                except Exception as e:
                    logger.warning("Diarization failed, continuing without speaker identification: %s", e)
                    speakers = []
                finally:
                    if diarization_executor is not None:
                        diarization_executor.shutdown(wait=False)

            if speakers:
                transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)
                transcription_segments = stitch_speaker_turns(transcription_segments)

        _update_job(job, progress=70, message="Processing segments...")

        # Apply text normalization (whitespace, punctuation, stutter removal)
        normalize_segments(transcription_segments)

        # Apply readable-mode postprocessing if requested
        if settings.output_mode == "readable":
            apply_readable_mode(transcription_segments)
            # Reconstruct full_text from cleaned segments
            full_text = " ".join(
                seg["text"].strip() for seg in transcription_segments if seg.get("text")
            )

        _update_job(job, progress=90, message="Finalizing...")

        job.segments = transcription_segments
        job.result = full_text
        _update_job(job, progress=100, message="Complete!", status="completed")
        model_name = "Voxtral API" if use_voxtral else ("Voxtral Local" if use_voxtral_local else ("Parakeet MLX" if use_parakeet else "MLX-Whisper"))
        logger.info(f"Transcription complete ({model_name}): {len(transcription_segments)} segments")

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        state.jobs.update(job)
        logger.exception("Transcription failed for job %s", job_id)

    finally:
        # Audit #16: retries re-use the same file_path. Don't rmtree if this
        # job was created from a retry — the parent dir is still wanted by any
        # subsequent retry attempt.
        retry_of = getattr(job, "_retry_of", None) if job is not None else None
        if retry_of:
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
