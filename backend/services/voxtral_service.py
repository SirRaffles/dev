"""
Voxtral API client for Mistral's Voxtral Mini Transcribe V2.

Cloud-based transcription with built-in speaker diarization,
context biasing, and ~4% WER accuracy.

Pricing: $0.003/minute
"""

import os
import subprocess
import tempfile
import logging

import httpx

logger = logging.getLogger(__name__)

# Voxtral-supported languages (13 total)
VOXTRAL_LANGUAGES = {
    "en", "fr", "de", "es", "it", "pt", "nl", "ru",
    "zh", "ja", "ko", "ar", "hi",
}


class VoxtralService:
    """Client for Mistral's Voxtral Mini Transcribe V2 API."""

    API_URL = "https://api.mistral.ai/v1/audio/transcriptions"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def transcribe(
        self,
        audio_path: str,
        language: str = "auto",
        enable_diarization: bool = True,
        word_timestamps: bool = False,
        context_terms: list[str] | None = None,
    ) -> dict:
        """
        Transcribe audio using Voxtral Mini Transcribe V2 API.

        Args:
            audio_path: Path to audio file (WAV, FLAC, MP3, etc.)
            language: Language code or "auto" for detection
            enable_diarization: Enable built-in speaker diarization
            word_timestamps: Enable word-level timestamps
            context_terms: List of domain-specific terms for context biasing (max 100)

        Returns:
            Dict with 'text', 'segments', 'language', and 'speakers' keys
        """
        # Compress to FLAC for smaller upload
        flac_path = None
        upload_path = audio_path
        if audio_path.endswith(".wav"):
            flac_path = self._compress_to_flac(audio_path)
            if flac_path:
                upload_path = flac_path

        try:
            return self._call_api(
                upload_path,
                language=language,
                enable_diarization=enable_diarization,
                word_timestamps=word_timestamps,
                context_terms=context_terms,
            )
        finally:
            # Clean up temp FLAC file
            if flac_path and os.path.exists(flac_path):
                try:
                    os.remove(flac_path)
                except OSError:
                    pass

    def _call_api(
        self,
        audio_path: str,
        language: str,
        enable_diarization: bool,
        word_timestamps: bool,
        context_terms: list[str] | None,
    ) -> dict:
        """Make the actual API call to Mistral."""
        warnings = []

        timestamp_granularities = ["segment"]
        if word_timestamps:
            timestamp_granularities.append("word")

        # Build multipart form data
        data = {
            "model": "voxtral-mini-latest",
            "response_format": "verbose_json",
        }

        # Constraint: timestamps and language are incompatible in the Mistral API.
        # When both are requested, drop timestamps to preserve language accuracy.
        has_language = language and language != "auto"
        if has_language and timestamp_granularities:
            logger.warning(
                "Mistral API constraint: timestamp_granularities is incompatible with language. "
                "Dropping timestamps to preserve language accuracy."
            )
            warnings.append("Timestamps disabled: incompatible with explicit language setting")
            timestamp_granularities = []

        # Constraint: diarization is not supported in realtime mode.
        if "realtime" in data["model"] and enable_diarization:
            logger.warning("Diarization not supported in realtime mode, disabling")
            warnings.append("Diarization disabled: not supported in realtime mode")
            enable_diarization = False

        # Language (omit for auto-detection)
        if has_language:
            data["language"] = language

        # Diarization
        if enable_diarization:
            data["diarize"] = "true"

        # Timestamp granularities (sent as repeated keys)
        # httpx handles lists in data by sending multiple values
        if timestamp_granularities:
            data["timestamp_granularities[]"] = timestamp_granularities

        # Context biasing (up to 100 terms)
        if context_terms:
            terms = context_terms[:100]
            data["context_bias[]"] = terms

        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f)}

            response = httpx.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=data,
                files=files,
                timeout=600.0,  # 10 min timeout for long audio
            )

        if response.status_code == 401:
            raise RuntimeError("Invalid Mistral API key. Check your MISTRAL_API_KEY.")
        elif response.status_code == 413:
            raise RuntimeError("Audio file too large for Voxtral API (max 3 hours).")
        elif response.status_code == 429:
            raise RuntimeError("Voxtral API rate limit exceeded. Please try again later.")
        elif response.status_code != 200:
            detail = response.text[:500] if response.text else "Unknown error"
            raise RuntimeError(f"Voxtral API error ({response.status_code}): {detail}")

        api_response = response.json()
        result = self._normalize_response(api_response)
        result["warnings"] = warnings
        return result

    def _compress_to_flac(self, wav_path: str) -> str | None:
        """Compress WAV to FLAC for smaller API upload (~50% smaller)."""
        try:
            flac_path = wav_path.rsplit(".", 1)[0] + "_voxtral.flac"
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", wav_path,
                    "-c:a", "flac",
                    "-compression_level", "5",
                    flac_path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0 and os.path.exists(flac_path):
                wav_size = os.path.getsize(wav_path)
                flac_size = os.path.getsize(flac_path)
                logger.info(
                    f"Compressed WAV→FLAC: {wav_size / 1024 / 1024:.1f}MB → {flac_size / 1024 / 1024:.1f}MB "
                    f"({flac_size / wav_size * 100:.0f}%)"
                )
                return flac_path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _normalize_response(self, api_response: dict) -> dict:
        """
        Normalize Voxtral API response to match internal segment format.

        Voxtral returns:
            {"id": 0, "start": 0.0, "end": 5.2, "text": "...", "speaker": "SPEAKER_00", ...}

        We normalize to:
            {"start": 0.0, "end": 5.2, "text": "...", "speaker": "SPEAKER_00"}
        """
        segments = []
        speakers_set = set()

        for seg in api_response.get("segments", []):
            normalized = {
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", "").strip(),
            }

            # Include speaker if present (from diarization)
            speaker = seg.get("speaker")
            if speaker:
                normalized["speaker"] = speaker
                speakers_set.add(speaker)

            # Include word timestamps if present
            words = seg.get("words")
            if words:
                normalized["words"] = [
                    {
                        "word": w.get("word", w.get("text", "")),
                        "start": w.get("start", 0.0),
                        "end": w.get("end", 0.0),
                        "probability": w.get("probability", 1.0),
                    }
                    for w in words
                ]

            segments.append(normalized)

        return {
            "text": api_response.get("text", ""),
            "segments": segments,
            "language": api_response.get("language", "unknown"),
            "speakers": sorted(speakers_set),
        }

    def transcribe_two_pass(
        self,
        audio_path: str,
        language: str,
        enable_diarization: bool = True,
        word_timestamps: bool = False,
        context_terms: list[str] | None = None,
    ) -> dict:
        """Two-pass transcription: timestamps pass + language pass, merged.

        Pass A: timestamps (segment-level), no language, with diarization/bias.
        Pass B: language set, no timestamps.
        Merge: Use Pass A timestamps + Pass B text when alignment is confident.

        Returns dict with text, segments, language, speakers, warnings, edits.
        """
        from difflib import SequenceMatcher

        logger.info("Two-pass transcription: starting Pass A (timestamps)...")

        # Compress once, reuse for both passes
        flac_path = None
        upload_path = audio_path
        if audio_path.endswith(".wav"):
            flac_path = self._compress_to_flac(audio_path)
            if flac_path:
                upload_path = flac_path

        try:
            # Pass A: timestamps, no language
            result_a = self._call_api(
                upload_path,
                language="auto",
                enable_diarization=enable_diarization,
                word_timestamps=word_timestamps,
                context_terms=context_terms,
            )

            logger.info("Two-pass transcription: starting Pass B (language=%s)...", language)

            # Pass B: language, no timestamps (timestamps will be empty since
            # _call_api drops them when language is set)
            result_b = self._call_api(
                upload_path,
                language=language,
                enable_diarization=False,  # only need text from this pass
                word_timestamps=False,
                context_terms=context_terms,
            )
        finally:
            if flac_path and os.path.exists(flac_path):
                try:
                    os.remove(flac_path)
                except OSError:
                    pass

        # Merge: Pass A timestamps + Pass B text
        segs_a = result_a.get("segments", [])
        segs_b = result_b.get("segments", [])
        edits = []
        warnings = result_a.get("warnings", []) + result_b.get("warnings", [])

        if len(segs_a) == len(segs_b):
            # Aligned: replace text segment-by-segment
            for i, (sa, sb) in enumerate(zip(segs_a, segs_b)):
                old_text = sa.get("text", "")
                new_text = sb.get("text", "")
                sim = SequenceMatcher(None, old_text.lower(), new_text.lower()).ratio()
                if sim >= 0.85:
                    edits.append({
                        "segment": i,
                        "old_text": old_text,
                        "new_text": new_text,
                        "similarity": round(sim, 3),
                    })
                    sa["text"] = new_text
                # else: keep Pass A text (timestamps pass), it's close enough
        elif segs_b:
            # Different segment counts: greedy alignment by duration + text similarity
            warnings.append(
                f"Two-pass segment count mismatch (A={len(segs_a)}, B={len(segs_b)}); "
                "using greedy alignment"
            )
            b_idx = 0
            for i, sa in enumerate(segs_a):
                if b_idx >= len(segs_b):
                    break
                sb = segs_b[b_idx]
                old_text = sa.get("text", "")
                new_text = sb.get("text", "")
                sim = SequenceMatcher(None, old_text.lower(), new_text.lower()).ratio()
                if sim >= 0.85:
                    edits.append({
                        "segment": i,
                        "old_text": old_text,
                        "new_text": new_text,
                        "similarity": round(sim, 3),
                    })
                    sa["text"] = new_text
                    b_idx += 1
                elif sim >= 0.5:
                    # Partial match, advance B pointer
                    b_idx += 1

        result = result_a
        result["language"] = result_b.get("language", language)
        result["warnings"] = warnings
        result["edits"] = edits

        # Rebuild full text from merged segments
        result["text"] = " ".join(s.get("text", "") for s in result["segments"])

        logger.info(
            "Two-pass merge complete: %d segments, %d edits applied",
            len(result["segments"]),
            len(edits),
        )

        return result

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate API cost for audio of given duration."""
        minutes = duration_seconds / 60.0
        return round(minutes * 0.003, 4)
