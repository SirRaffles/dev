"""
Core transcription logic: MLX-Whisper, Parakeet, Voxtral engines.
"""

import os
import asyncio
import logging
import shutil
import tempfile

from config import MLX_MODELS, PARAKEET_MODEL, VOXTRAL_LOCAL_MODELS
from job_models import TranscriptionSettings
from services.audio import apply_noise_reduction
from services.diarization import run_diarization, assign_speakers_to_segments, stitch_speaker_turns
from services.postprocess import normalize_segments, apply_readable_mode
import state

logger = logging.getLogger(__name__)


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


def transcribe_with_parakeet(audio_path: str) -> dict:
    """Transcribe audio using Parakeet MLX (60x real-time on Apple Silicon)."""
    import parakeet_mlx

    logger.info("Transcribing with Parakeet MLX (60x real-time)...")

    if state._parakeet_model is None:
        logger.info("Loading Parakeet model: %s", PARAKEET_MODEL['path'])
        state._parakeet_model = parakeet_mlx.from_pretrained(PARAKEET_MODEL["path"])
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

    return {
        "text": full_text,
        "segments": segments,
        "language": "en",
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
        subprocess.run(
            ["ffmpeg", "-i", audio_path, "-ss", str(start), "-t", str(duration),
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
    from mlx_audio.stt.utils import load as mlx_audio_load

    CHUNK_DURATION = 30  # seconds — Voxtral encoder max (WhisperFeatureExtractor chunk_length)
    MAX_TOKENS_PER_CHUNK = 4096

    # Determine which model variant to use
    model_key = settings.model_size if settings.model_size in VOXTRAL_LOCAL_MODELS else "voxtral-mini-3b"
    model_path = VOXTRAL_LOCAL_MODELS[model_key]["path"]

    logger.info("Transcribing with Voxtral Local (%s)...", model_path)

    # Lazy-load: cache model in state to avoid reloading on every request
    if state._voxtral_local_model is None or state._voxtral_local_model_name != model_path:
        logger.info("Loading Voxtral Local model: %s", model_path)
        state._voxtral_local_model = mlx_audio_load(model_path)
        state._voxtral_local_model_name = model_path
        logger.info("Voxtral Local model loaded successfully")

    model = state._voxtral_local_model
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


def _run_transcription_sync(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Synchronous transcription worker - runs in thread pool."""
    job = state.jobs.get(job_id)

    if not job:
        return

    use_voxtral = settings.engine == "voxtral-api"
    use_voxtral_local = settings.engine == "voxtral-local"
    use_parakeet = settings.model_size == "parakeet" and not use_voxtral and not use_voxtral_local

    if use_voxtral:
        if not state._voxtral_available:
            job.status = "failed"
            job.error = "Voxtral API not configured. Set MISTRAL_API_KEY environment variable."
            return
    elif use_voxtral_local:
        if not state._voxtral_local_available:
            job.status = "failed"
            job.error = "Voxtral Local not available. Install with: pip install mlx-audio"
            return
    elif use_parakeet:
        if not state._parakeet_available:
            job.status = "failed"
            job.error = "Parakeet MLX not installed. Install with: pip install parakeet-mlx"
            return
    elif not state.whisper_model_ready:
        job.status = "failed"
        job.error = "MLX-Whisper not configured. Please restart the server."
        return

    try:
        job.status = "processing"
        job.progress = 5
        job.progress_message = "Starting transcription..."

        if settings.enable_noise_reduction:
            job.progress = 8
            job.progress_message = "Applying noise reduction..."
            cleaned_audio_path = audio_path.replace(".wav", "_cleaned.wav")
            audio_path = apply_noise_reduction(audio_path, cleaned_audio_path)

        # === VOXTRAL API ENGINE ===
        if use_voxtral:
            job.progress = 15
            job.progress_message = "Transcribing with Voxtral (cloud API)..."

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
            speakers = []
            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
            if settings.enable_diarization:
                if not hf_token:
                    logger.warning(
                        "Diarization requested but HF_TOKEN is not set. "
                        "Skipping speaker identification."
                    )
                else:
                    job.progress = 10
                    if settings.num_speakers:
                        job.progress_message = f"Identifying {settings.num_speakers} speakers..."
                    else:
                        job.progress_message = "Identifying speakers..."
                    try:
                        speakers = run_diarization(audio_path, num_speakers=settings.num_speakers)
                    except Exception as e:
                        logger.warning("Diarization failed, continuing without speaker identification: %s", e)
                        speakers = []
                    job.speakers = speakers

            job.progress = 20

            if use_voxtral_local:
                if settings.word_timestamps:
                    logger.warning("word_timestamps=True ignored: Voxtral Local does not support word-level timestamps")
                job.progress_message = "Transcribing with Voxtral Local (~4% WER)..."
                logger.info("Using Voxtral Local for transcription")

                result = transcribe_with_voxtral_local(audio_path, settings)

                job.language = result.get("language", "auto")
                job.language_probability = 0.99

                transcription_segments = result.get("segments", [])
                full_text = result.get("text", "")

            elif use_parakeet:
                if settings.word_timestamps:
                    logger.warning("word_timestamps=True ignored: Parakeet does not support word-level timestamps")
                job.progress_message = "Transcribing with Parakeet MLX (60x real-time)..."
                logger.info("Using Parakeet MLX for English transcription")

                result = transcribe_with_parakeet(audio_path)

                job.language = "en"
                job.language_probability = 0.99

                transcription_segments = result.get("segments", [])
                full_text = result.get("text", "")

            else:
                import mlx_whisper

                job.progress_message = "Transcribing with MLX-Whisper (GPU-accelerated)..."

                language = None if settings.language == "auto" else settings.language

                model_info = MLX_MODELS.get(settings.model_size, MLX_MODELS["large-v3"])
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

            if speakers:
                transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)
                transcription_segments = stitch_speaker_turns(transcription_segments)

        job.progress = 70
        job.progress_message = "Processing segments..."

        # Apply text normalization (whitespace, punctuation, stutter removal)
        normalize_segments(transcription_segments)

        # Apply readable-mode postprocessing if requested
        if settings.output_mode == "readable":
            apply_readable_mode(transcription_segments)
            # Reconstruct full_text from cleaned segments
            full_text = " ".join(
                seg["text"].strip() for seg in transcription_segments if seg.get("text")
            )

        job.progress = 90
        job.progress_message = "Finalizing..."

        job.segments = transcription_segments
        job.result = full_text
        job.progress = 100
        job.progress_message = "Complete!"
        job.status = "completed"
        state.jobs.update(job)
        model_name = "Voxtral API" if use_voxtral else ("Voxtral Local" if use_voxtral_local else ("Parakeet MLX" if use_parakeet else "MLX-Whisper"))
        logger.info(f"Transcription complete ({model_name}): {len(transcription_segments)} segments")

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        state.jobs.update(job)
        logger.exception("Transcription failed for job %s", job_id)

    finally:
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
