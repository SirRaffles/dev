"""
YouTube audio download and transcript utilities.
"""

import os
import re
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def _is_valid_youtube_url(url: str) -> bool:
    """Validate that the URL is a legitimate YouTube URL."""
    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/watch\?',
        r'^https?://(www\.)?youtube\.com/shorts/',
        r'^https?://(www\.)?youtube\.com/embed/',
        r'^https?://youtu\.be/',
        r'^https?://music\.youtube\.com/watch\?',
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


def download_youtube_audio(url: str, output_dir: str) -> str:
    """Download audio from YouTube URL using yt-dlp."""
    if not _is_valid_youtube_url(url):
        raise ValueError("Invalid URL. Only YouTube URLs are accepted.")

    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-exec",
        "--no-batch",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "-ar 16000 -ac 1",
        "-o", output_template,
        url,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        raise RuntimeError("YouTube download timed out after 10 minutes")

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")

    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise RuntimeError("No audio file found after download")


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


def get_youtube_transcript(video_id: str, language: str = "auto") -> Optional[dict]:
    """Try to get existing YouTube transcript (instant, no download needed).

    Returns transcript in our segment format, or None if no transcript available.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        )

        try:
            api = YouTubeTranscriptApi()

            transcript_list = api.list(video_id)

            transcript = None
            detected_language = None

            if language != "auto":
                try:
                    transcript = transcript_list.find_transcript([language]).fetch()
                    detected_language = language
                except NoTranscriptFound:
                    try:
                        for t in transcript_list:
                            if t.is_translatable:
                                transcript = t.translate(language).fetch()
                                detected_language = language
                                break
                    except Exception:
                        pass

            if transcript is None:
                for t in transcript_list:
                    transcript = t.fetch()
                    detected_language = t.language_code
                    break

            if transcript is None:
                transcript = api.fetch(video_id)
                detected_language = "auto"

            if transcript is None:
                return None

            segments = []
            for item in transcript:
                if hasattr(item, 'text'):
                    start = float(item.start)
                    duration = float(item.duration) if hasattr(item, 'duration') else 0
                    text = item.text.strip()
                else:
                    start = float(item.get("start", 0))
                    duration = float(item.get("duration", 0))
                    text = item.get("text", "").strip()

                segments.append({
                    "start": start,
                    "end": start + duration,
                    "text": text,
                })

            full_text = " ".join(seg["text"] for seg in segments)

            return {
                "segments": segments,
                "text": full_text,
                "language": detected_language,
                "source": "youtube_captions",
            }

        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
            return None

    except ImportError:
        logger.warning("youtube-transcript-api not installed")
        return None
    except Exception as e:
        logger.warning("Error getting YouTube transcript: %s", e)
        return None
