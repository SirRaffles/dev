"""Backend orchestrator: composes the right model stack per quality mode.

Best mode  -> Whisper Large V3 Turbo + pyannote + Sonnet refinement (with
              diarization polish, per Sub-plan B).
Quick mode -> Parakeet v3 multilingual + pyannote + Sonnet refinement.

This module is intentionally thin: it owns dispatch + phase transitions, and
delegates work to existing helpers in services.transcription, services.diarization,
and routes.refinement.
"""

import logging
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional

from services.transcription import (
    transcribe_with_whisper,
    transcribe_with_parakeet,
    _update_job,
    _should_auto_refine,
)
from services.diarization import (
    run_diarization,
    assign_speakers_to_segments,
    assign_speakers_time_proportional,
    stitch_speaker_turns,
)
from services.postprocess import normalize_segments
from services.audio import apply_noise_reduction
import state

logger = logging.getLogger(__name__)

# Phase constants - single source of truth, matches the spec's Phase Lifecycle table.
PHASE_DIARIZING = "diarizing"
PHASE_TRANSCRIBING = "transcribing"
PHASE_ALIGNING = "aligning"
PHASE_REFINING = "refining"
PHASE_LEARNING = "learning"

# Empirical RT (real-time) factors on Apple Silicon, used to estimate the
# expected wall-clock duration of the transcribing phase so the progress bar
# can interpolate smoothly between the start and end milestones instead of
# stalling for minutes at the "Transcribing..." message.
_RT_FACTOR_WHISPER = 10.0  # large-v3-turbo MLX, M-series GPU
_RT_FACTOR_PARAKEET = 6.0  # parakeet-multi-v3 MLX, M-series GPU


def _get_audio_duration_sec(audio_path: str) -> Optional[float]:
    """Probe audio duration via ffprobe. Returns None on any failure — caller
    falls back to a conservative default so the progress ticker never blocks
    on an unparseable file."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None


class _TranscribeProgressTicker:
    """Daemon thread that interpolates `job.progress` between a start and a
    ceiling percentage while the underlying transcribe call is blocking.

    Without this, MLX-Whisper / Parakeet hold the worker for the entire audio
    duration with no intermediate progress updates — the UI shows a stale
    "Transcribing…" at the start percentage until the call returns.

    The ticker estimates expected wall-clock time as
    `audio_duration_sec / rt_factor`, fires every 2 seconds, and caps progress
    at 95% of the band so the actual call-completion update (e.g. progress=65)
    still produces a small forward motion when the call returns. If the call
    runs longer than estimated (dense audio, cold model load) the bar parks at
    the cap until completion — better than overshooting and visually jumping
    backward.
    """

    def __init__(self, job, start_pct: int, ceiling_pct: int,
                 expected_seconds: float, message: str, phase: str):
        self._job = job
        self._start = start_pct
        self._span = ceiling_pct - start_pct
        self._expected = max(5.0, expected_seconds)
        self._message = message
        self._phase = phase
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="transcribe-progress",
        )

    def start(self) -> "_TranscribeProgressTicker":
        self._thread.start()
        return self

    def _run(self) -> None:
        t0 = time.monotonic()
        while not self._stop.wait(2.0):
            elapsed = time.monotonic() - t0
            frac = min(0.95, elapsed / self._expected)
            pct = self._start + int(frac * self._span)
            # Append elapsed time to the message so the user sees the
            # transcription is still progressing even after pct hits the
            # 95% cap (long audio / cold model / over-optimistic RT estimate).
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            elapsed_str = (f" ({mins}m{secs:02d}s elapsed)" if mins
                           else f" ({secs}s elapsed)")
            try:
                _update_job(self._job, progress=pct,
                            message=self._message + elapsed_str,
                            phase=self._phase)
            except Exception:
                logger.debug("progress ticker update failed (job moved on?)",
                             exc_info=True)
                return

    def stop(self) -> None:
        self._stop.set()


def orchestrate_transcription(
    job_id: str,
    audio_path: str,
    settings,
    mode: Literal["best", "quick"] = "best",
) -> None:
    """Run the chosen pipeline. Synchronous; called from the thread pool."""
    job = state.jobs.get(job_id)
    if not job:
        logger.warning("orchestrator: job %s missing - bail", job_id)
        return

    try:
        _update_job(job, progress=5, message="Starting transcription...", status="processing")

        # Optional noise reduction (preserved from legacy path).
        if settings.enable_noise_reduction:
            _update_job(job, progress=8, message="Applying noise reduction...")
            from pathlib import Path
            src = Path(audio_path)
            cleaned_audio_path = str(src.with_stem(src.stem + "_cleaned"))
            audio_path = apply_noise_reduction(audio_path, cleaned_audio_path)

        # Spin up diarization concurrently with transcription (Audit #9 pattern preserved).
        speakers = []
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
        diarization_future = None
        diarization_executor = None
        if settings.enable_diarization and hf_token:
            _update_job(
                job,
                progress=10,
                message=(f"Identifying {settings.num_speakers} speakers..."
                         if settings.num_speakers else "Identifying speakers..."),
                phase=PHASE_DIARIZING,
            )
            diarization_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="diarize")
            diarization_future = diarization_executor.submit(
                run_diarization, audio_path, settings.num_speakers
            )

        # Transcribe (Best->Whisper Turbo, Quick->Parakeet multilingual v3).
        # The transcribe call is blocking and emits no intermediate progress,
        # so we spawn a time-based ticker that interpolates 20% -> ~62% over
        # the expected wall-clock duration (audio_duration / RT_factor). The
        # final 65% milestone after the call returns gives the user a small
        # forward motion as confirmation that transcription finished.
        transcribe_msg = (
            "Transcribing with MLX-Whisper (GPU-accelerated)..." if mode == "best"
            else "Transcribing with Parakeet MLX (multilingual v3)..."
        )
        _update_job(job, progress=20, message=transcribe_msg, phase=PHASE_TRANSCRIBING)

        audio_seconds = _get_audio_duration_sec(audio_path) or 60.0
        rt_factor = _RT_FACTOR_WHISPER if mode == "best" else _RT_FACTOR_PARAKEET
        expected_sec = audio_seconds / rt_factor
        ticker = _TranscribeProgressTicker(
            job, start_pct=20, ceiling_pct=65, expected_seconds=expected_sec,
            message=transcribe_msg, phase=PHASE_TRANSCRIBING,
        ).start()
        try:
            if mode == "best":
                result = transcribe_with_whisper(audio_path, settings, job=job)
            else:
                # Quick: always multilingual v3 (covers EN+FR per spec).
                result = transcribe_with_parakeet(audio_path, model_key="parakeet-multi-v3")
        finally:
            ticker.stop()

        job.language = result.get("language", "unknown")
        job.language_probability = 0.99
        transcription_segments = result.get("segments", [])
        full_text = result.get("text", "")

        # Join diarization (never let a diarization failure kill transcription).
        if diarization_future is not None:
            try:
                speakers = diarization_future.result() or []
                job.speakers = speakers
            except Exception as e:
                logger.warning("Diarization failed, continuing without speakers: %s", e)
                speakers = []
            finally:
                if diarization_executor is not None:
                    diarization_executor.shutdown(wait=False)

        # Align speakers onto segments. Best uses A3 word-boundary; Quick uses A3-light.
        if speakers:
            _update_job(job, progress=65, message="Aligning speakers to segments...",
                        phase=PHASE_ALIGNING)
            if mode == "best":
                transcription_segments = assign_speakers_to_segments(transcription_segments, speakers)
            else:
                transcription_segments = assign_speakers_time_proportional(
                    transcription_segments, speakers
                )
            transcription_segments = stitch_speaker_turns(transcription_segments)

        # B5 inline auto-match - overlay registered speaker names (~1-5s).
        # Same scope logic as the post-job /speakers/auto-match route.
        if speakers and state.refinement_available:
            _update_job(job, progress=68, message="Matching voices to registered speakers...")
            try:
                from routes.transcription import _resolve_match_scope
                restrict_ids, prefer_ids, scope_mode = _resolve_match_scope({
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
                for turn in (job.speakers or []):
                    lbl = turn.get("speaker", "")
                    m = auto_matches.get(lbl)
                    if m and m.get("matched"):
                        turn["speaker"] = m["name"]
                logger.info("B5 auto-match: scope=%s, matched %d/%d",
                            scope_mode, sum(1 for m in auto_matches.values() if m.get("matched")),
                            len(auto_matches))
            except Exception:
                logger.exception("B5 auto-match failed for %s; keeping SPEAKER_XX", job_id)

        # A1: strip internal `words` from emitted segments if user opted out.
        if not settings.word_timestamps:
            for seg in transcription_segments:
                seg.pop("words", None)

        _update_job(job, progress=70, message="Processing segments...")
        normalize_segments(transcription_segments)

        _update_job(job, progress=90, message="Finalizing...")
        job.segments = transcription_segments
        job.result = full_text

        # Clear phase as we transition to completed (verbatim ready).
        _update_job(job, progress=100, message="Complete!", status="completed",
                    phase=None, _clear_phase=True)

        # Auto-refine dispatch (Best mode benefits most; Quick mode also runs
        # so diarization polish + learning fire). Same dispatch as the legacy
        # path - _run_refinement_for_job already chains learning workers.
        if _should_auto_refine(settings) and state.refinement_available:
            try:
                from routes.refinement import _run_refinement_for_job
                job.refinement_status = "pending"
                state.jobs.update(job)
                state.refinement_store.create(job_id)
                job._defer_audio_cleanup = True
                state.transcription_executor.submit(
                    _run_refinement_for_job,
                    job_id,
                    settings.speaker_ids,
                    settings.context_path,
                    audio_path,
                )
                logger.info("Orchestrator: auto-refine dispatched for %s (mode=%s)", job_id, mode)
            except Exception:
                logger.exception("Orchestrator: auto-refine dispatch failed for %s", job_id)
                try:
                    job.refinement_status = "failed"
                    state.jobs.update(job)
                    state.refinement_store.update_status(job_id, "failed", "dispatch failed")
                except Exception:
                    logger.debug("Rollback after dispatch failure failed for %s",
                                 job_id, exc_info=True)
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        state.jobs.update(job)
        logger.exception("Orchestrator failed for job %s", job_id)
