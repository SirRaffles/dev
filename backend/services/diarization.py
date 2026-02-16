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

        import torch
        import torch.serialization

        # PyTorch 2.6+ defaults to weights_only=True in torch.load, but
        # pyannote model checkpoints contain custom classes that aren't in
        # the safe-globals list. We trust HuggingFace-hosted pyannote models,
        # so override the default in this isolated subprocess.
        torch.serialization._default_to_weights_only = lambda pickle_module: False

        from pyannote.audio import Pipeline

        # HF_TOKEN is already set in os.environ (line 19) — pyannote reads it
        # from there. Passing use_auth_token= causes errors with newer
        # huggingface_hub which removed that parameter from hf_hub_download().
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
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
        error_msg = str(e)
        tb = traceback.format_exc()

        # Detect common pyannote/HF auth issues and provide actionable messages
        if "401" in error_msg or "Unauthorized" in error_msg or "Invalid credentials" in error_msg:
            error_msg = (
                f"Hugging Face authentication failed: {error_msg}. "
                "Check that your HF_TOKEN is valid and has not expired."
            )
        elif "403" in error_msg or "gated" in error_msg.lower() or "access" in error_msg.lower():
            error_msg = (
                f"Pyannote model license not accepted: {error_msg}. "
                "You must accept the license agreements at: "
                "https://huggingface.co/pyannote/speaker-diarization-3.1 and "
                "https://huggingface.co/pyannote/segmentation-3.0"
            )

        with open(output_file, 'w') as f:
            json.dump({"status": "error", "error": error_msg, "traceback": tb}, f)


def run_diarization_subprocess(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization in a separate subprocess to prevent blocking."""
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""

    if not hf_token:
        logger.warning(
            "Diarization skipped: HF_TOKEN environment variable is not set. "
            "Set HF_TOKEN to your Hugging Face access token to enable speaker diarization."
        )
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
                error_msg = result.get('error', 'Unknown error')
                logger.warning("Diarization skipped: %s", error_msg)
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


def stitch_speaker_turns(segments: List[dict], max_gap_ms: float = 600) -> List[dict]:
    """Merge adjacent segments with the same speaker when the gap is small.

    Never changes the outer timestamps of a merged segment (uses first start,
    last end).  Only merges text fields.

    Args:
        segments: List of segment dicts with start, end, text, and optionally speaker.
        max_gap_ms: Maximum gap in milliseconds between segments to merge.

    Returns:
        New list of (possibly merged) segments.
    """
    if not segments:
        return []

    merged = [dict(segments[0])]  # shallow copy first segment

    for seg in segments[1:]:
        prev = merged[-1]
        same_speaker = (
            prev.get("speaker")
            and seg.get("speaker")
            and prev["speaker"] == seg["speaker"]
        )
        gap_ms = (seg.get("start", 0) - prev.get("end", 0)) * 1000

        if same_speaker and gap_ms < max_gap_ms:
            # Merge: extend previous segment
            prev["end"] = seg["end"]
            prev["text"] = prev["text"] + " " + seg.get("text", "")
        else:
            merged.append(dict(seg))

    return merged


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
