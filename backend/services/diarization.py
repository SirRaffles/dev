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
            # Always create a fresh event loop — this runs in a ThreadPoolExecutor
            # worker thread which has no event loop by default.
            _loop = asyncio.new_event_loop()
            try:
                loaded = _loop.run_until_complete(manager.load_diarization())
            finally:
                _loop.close()

            if not loaded:
                logger.warning("Diarization model failed to load")
                return []

        pipeline = manager.get_model(ModelName.DIARIZATION)
        if pipeline is None:
            logger.warning("Diarization pipeline not available")
            return []

        logger.info("Running diarization (in-process singleton)...")

        # Pre-load audio as an in-memory tensor so pyannote-audio 4.x
        # doesn't rely on torchcodec (which ABI-breaks against torch 2.8
        # on this venv). soundfile is already a transitive dep.
        import soundfile as sf
        import torch
        audio_np, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)
        # pyannote expects (channel, time) float32 torch tensor
        waveform = torch.from_numpy(audio_np.T)
        audio_input = {"waveform": waveform, "sample_rate": sample_rate}

        if num_speakers and num_speakers > 0:
            diarization = pipeline(audio_input, num_speakers=num_speakers)
        else:
            diarization = pipeline(audio_input)

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
                "Diarization failed (access): %s — Check HF connectivity. "
                "Model at https://huggingface.co/pyannote/speaker-diarization-community-1 "
                "is open-source (no terms acceptance required).", error_msg
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
    """Assign speaker labels to transcription segments.

    If per-word timestamps are available on a segment, the segment is split at
    speaker-turn boundaries so each output sub-segment has exactly one speaker.
    If word timestamps are absent (Voxtral/Parakeet path), falls back to the
    midpoint-of-segment heuristic.
    """
    if not speakers:
        return segments

    def speaker_at(t: float) -> str:
        for turn in speakers:
            if turn["start"] <= t < turn["end"]:
                return turn["speaker"]
        return "Unknown"

    out: List[dict] = []
    for seg in segments:
        words = seg.get("words") or []

        if not words:
            mid = (seg.get("start", 0) + seg.get("end", 0)) / 2
            new_seg = dict(seg)
            new_seg["speaker"] = speaker_at(mid)
            out.append(new_seg)
            continue

        current_speaker = speaker_at(words[0].get("start", seg.get("start", 0)))
        buf_words: List[dict] = []
        buf_start = words[0].get("start", seg.get("start", 0))

        def _flush(end_time: float):
            if not buf_words:
                return
            text = " ".join(w.get("word", "").strip() for w in buf_words if w.get("word", "").strip())
            out.append({
                "start": buf_start,
                "end": end_time,
                "text": text,
                "speaker": current_speaker,
                "words": list(buf_words),
            })

        for w in words:
            t = w.get("start", w.get("end", buf_start))
            w_speaker = speaker_at(t)
            if w_speaker != current_speaker and buf_words:
                _flush(buf_words[-1].get("end", buf_start))
                current_speaker = w_speaker
                buf_words = []
                buf_start = t
            buf_words.append(w)

        if buf_words:
            _flush(buf_words[-1].get("end", seg.get("end", buf_start)))

    return out
