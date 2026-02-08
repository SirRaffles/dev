"""
Core transcription logic: MLX-Whisper, Parakeet, Voxtral engines.
"""

import os
import asyncio
import logging

from config import MLX_MODELS, PARAKEET_MODEL
from job_models import TranscriptionSettings
from services.audio import apply_noise_reduction
from services.diarization import run_diarization, assign_speakers_to_segments
import state

logger = logging.getLogger(__name__)


def get_mlx_model_path():
    """Get the MLX-Whisper model path based on environment or default."""
    mlx_models = {
        "tiny": "mlx-community/whisper-tiny",
        "base": "mlx-community/whisper-base",
        "small": "mlx-community/whisper-small",
        "medium": "mlx-community/whisper-medium",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v2": "mlx-community/whisper-large-v2-mlx",
        "large-v3": "mlx-community/whisper-large-v3-mlx",
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
        "distil-large-v3": "mlx-community/distil-whisper-large-v3",
    }

    model_size = os.environ.get("WHISPER_MODEL_SIZE", "large-v3-turbo")
    return mlx_models.get(model_size, mlx_models["large-v3-turbo"])


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

    logger.info("Transcribing with Voxtral Mini (cloud API)...")

    language = None if settings.language == "auto" else settings.language

    result = state._voxtral_service.transcribe(
        audio_path=audio_path,
        language=language or "auto",
        enable_diarization=settings.enable_diarization,
        word_timestamps=settings.word_timestamps,
        context_terms=settings.context_terms,
    )

    return result


def _run_transcription_sync(job_id: str, audio_path: str, settings: TranscriptionSettings):
    """Synchronous transcription worker - runs in thread pool."""
    job = state.jobs.get(job_id)

    if not job:
        return

    use_voxtral = settings.engine == "voxtral-api"
    use_parakeet = settings.model_size == "parakeet" and not use_voxtral

    if use_voxtral:
        if not state._voxtral_available:
            job.status = "failed"
            job.error = "Voxtral API not configured. Set MISTRAL_API_KEY environment variable."
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

        else:
            # === LOCAL ENGINES (Whisper / Parakeet) ===
            speakers = []
            hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
            if settings.enable_diarization and hf_token:
                job.progress = 10
                if settings.num_speakers:
                    job.progress_message = f"Identifying {settings.num_speakers} speakers..."
                else:
                    job.progress_message = "Identifying speakers..."
                speakers = run_diarization(audio_path, num_speakers=settings.num_speakers)
                job.speakers = speakers

            job.progress = 20

            if use_parakeet:
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

        job.progress = 70
        job.progress_message = "Processing segments..."

        job.progress = 90
        job.progress_message = "Finalizing..."

        job.segments = transcription_segments
        job.result = full_text
        job.progress = 100
        job.progress_message = "Complete!"
        job.status = "completed"
        state.jobs.update(job)
        model_name = "Voxtral" if use_voxtral else ("Parakeet MLX" if use_parakeet else "MLX-Whisper")
        logger.info(f"Transcription complete ({model_name}): {len(transcription_segments)} segments")

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        state.jobs.update(job)
        logger.exception("Transcription failed for job %s", job_id)

    finally:
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
            parent_dir = os.path.dirname(audio_path)
            if os.path.isdir(parent_dir) and not os.listdir(parent_dir):
                os.rmdir(parent_dir)
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
