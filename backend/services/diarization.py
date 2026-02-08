"""
Speaker diarization services.
"""

import os
import json
import logging
import tempfile
import multiprocessing
import time
from typing import Optional, List

logger = logging.getLogger(__name__)


def _diarization_worker(audio_path: str, num_speakers: Optional[int], output_file: str, hf_token: str):
    """Subprocess worker for diarization. Runs in separate process to avoid blocking main server."""
    try:
        os.environ["HF_TOKEN"] = hf_token

        from pyannote.audio import Pipeline
        import torch

        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token
        )

        if torch.backends.mps.is_available():
            pipeline.to(torch.device("mps"))

        if num_speakers and num_speakers > 0:
            diarization = pipeline(audio_path, num_speakers=num_speakers)
        else:
            diarization = pipeline(audio_path)

        speakers = []

        if hasattr(diarization, 'speaker_diarization'):
            annotation = diarization.speaker_diarization
            for turn, _, speaker in annotation.itertracks(yield_label=True):
                speakers.append({
                    "start": float(turn.start),
                    "end": float(turn.end),
                    "speaker": str(speaker)
                })
        else:
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speakers.append({
                    "start": float(turn.start),
                    "end": float(turn.end),
                    "speaker": str(speaker)
                })

        with open(output_file, 'w') as f:
            json.dump({"status": "success", "speakers": speakers}, f)

    except Exception as e:
        import traceback
        with open(output_file, 'w') as f:
            json.dump({"status": "error", "error": str(e), "traceback": traceback.format_exc()}, f)


def run_diarization_subprocess(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization in a separate subprocess to prevent blocking."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""

    if not hf_token:
        logger.warning("HF_TOKEN not set, diarization will fail")
        return []

    _tf = tempfile.NamedTemporaryFile(suffix="_diarization.json", delete=False)
    output_file = _tf.name
    _tf.close()

    try:
        process = multiprocessing.Process(
            target=_diarization_worker,
            args=(audio_path, num_speakers, output_file, hf_token)
        )
        process.start()

        poll_interval = 5
        max_wait = 7200
        elapsed = 0

        while process.is_alive() and elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval
            if elapsed % 60 == 0:
                logger.info("Diarization in progress... (%ds elapsed)", elapsed)

        if process.is_alive():
            logger.warning("Diarization timeout after %ds, terminating...", max_wait)
            process.terminate()
            process.join(timeout=10)
            if process.is_alive():
                process.kill()
            return []

        process.join(timeout=5)

        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                result = json.load(f)

            if result.get("status") == "success":
                speakers = result.get("speakers", [])
                logger.info("Diarization complete: %d speaker segments found", len(speakers))
                return speakers
            else:
                logger.error("Diarization subprocess error: %s", result.get('error'))
                if result.get('traceback'):
                    logger.debug("Diarization traceback:\n%s", result.get('traceback'))
                return []
        else:
            logger.error("Diarization subprocess did not produce output")
            return []

    except Exception as e:
        logger.exception("Diarization subprocess failed: %s", e)
        return []
    finally:
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
            except OSError:
                pass


def run_diarization(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization on audio file."""
    return run_diarization_subprocess(audio_path, num_speakers)


def assign_speakers_to_segments(segments: List[dict], speakers: List[dict]) -> List[dict]:
    """Assign speaker labels to transcription segments."""
    if not speakers:
        return segments

    for segment in segments:
        seg_mid = (segment["start"] + segment["end"]) / 2

        assigned_speaker = None
        for speaker_turn in speakers:
            if speaker_turn["start"] <= seg_mid <= speaker_turn["end"]:
                assigned_speaker = speaker_turn["speaker"]
                break

        segment["speaker"] = assigned_speaker or "Unknown"

    return segments
