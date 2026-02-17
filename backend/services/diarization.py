"""
Speaker diarization services.

Uses ModelManager singleton to keep pyannote loaded across jobs,
avoiding ~30s model reload overhead per transcription.
"""

import asyncio
import logging
import os
from typing import Optional, List

logger = logging.getLogger(__name__)


def run_diarization(audio_path: str, num_speakers: Optional[int] = None) -> List[dict]:
    """Run speaker diarization using the in-process model singleton.

    The pyannote pipeline is loaded once via ModelManager and reused
    across jobs, saving ~30s of model loading per transcription.
    """
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or ""
    if not hf_token:
        logger.warning(
            "Diarization skipped: HF_TOKEN environment variable is not set. "
            "Set HF_TOKEN to your Hugging Face access token to enable speaker diarization."
        )
        return []

    try:
        from services.model_manager import get_model_manager, ModelName

        manager = get_model_manager()

        # Load pipeline if not already cached
        if not manager.is_loaded(ModelName.DIARIZATION):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're called from a thread (ThreadPoolExecutor), create a new loop
                _loop = asyncio.new_event_loop()
                try:
                    loaded = _loop.run_until_complete(manager.load_diarization())
                finally:
                    _loop.close()
            else:
                loaded = loop.run_until_complete(manager.load_diarization())

            if not loaded:
                logger.warning("Diarization model failed to load")
                return []

        pipeline = manager.get_model(ModelName.DIARIZATION)
        if pipeline is None:
            logger.warning("Diarization pipeline not available")
            return []

        logger.info("Running diarization (in-process singleton)...")

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

        logger.info("Diarization complete: %d speaker segments found", len(speakers))
        return speakers

    except Exception as e:
        # Detect common pyannote/HF auth issues
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            logger.warning(
                "Diarization failed (auth): %s — Check HF_TOKEN is valid.", error_msg
            )
        elif "403" in error_msg or "gated" in error_msg.lower():
            logger.warning(
                "Diarization failed (license): %s — Accept license at "
                "https://huggingface.co/pyannote/speaker-diarization-3.1", error_msg
            )
        else:
            logger.exception("Diarization failed: %s", e)
        return []


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
