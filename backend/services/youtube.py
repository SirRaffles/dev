"""
YouTube audio download and transcript utilities.
"""

import concurrent.futures
import logging
import os
import re
import shutil
import subprocess
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# Canonical YouTube URL regex — the ONE source of truth for URL validation.
# KEEP IN SYNC WITH src/components/YouTubeInput.tsx YOUTUBE_URL_RE
# Requires an 11-char video id in every variant (current YouTube spec).
YOUTUBE_URL_RE = re.compile(
    r"^https?://(?:www\.)?"
    r"(?:youtube\.com/(?:watch\?(?:[^#]*&)?v=[A-Za-z0-9_-]{11}"
    r"|shorts/[A-Za-z0-9_-]{11}"
    r"|live/[A-Za-z0-9_-]{11}"
    r"|embed/[A-Za-z0-9_-]{11})"
    r"|youtu\.be/[A-Za-z0-9_-]{11}"
    r"|music\.youtube\.com/watch\?(?:[^#]*&)?v=[A-Za-z0-9_-]{11})"
)


def _is_valid_youtube_url(url: str) -> bool:
    """Validate that the URL is a legitimate YouTube URL."""
    return bool(YOUTUBE_URL_RE.match(url))


def _parse_ytdlp_error(stderr: str) -> str:
    """Map common yt-dlp error patterns to user-friendly messages."""
    stderr_lower = stderr.lower()
    if "video unavailable" in stderr_lower or "private video" in stderr_lower:
        return "This video is unavailable or private"
    if "sign in to confirm" in stderr_lower or "age" in stderr_lower:
        return "This video is age-restricted and cannot be downloaded"
    if "not a valid url" in stderr_lower:
        return "Invalid YouTube URL"
    if "copyright" in stderr_lower:
        return "This video is unavailable due to a copyright claim"
    if "precondition check failed" in stderr_lower:
        return (
            "Video requires authentication. Set YTDLP_COOKIES_FROM_BROWSER "
            "or YTDLP_COOKIES_FILE."
        )
    if "http error 429" in stderr_lower:
        return "YouTube rate-limited this IP. Wait a few minutes and retry."
    return "YouTube download failed. The video may be unavailable or region-restricted."


def download_youtube_audio(url: str, output_dir: str) -> str:
    """Download audio from YouTube URL using yt-dlp.

    Hardened with:
      - URL validation via the canonical YOUTUBE_URL_RE
      - --no-playlist so a watch URL with a list= param can't fan out
      - --match-filter duration<=YTDLP_MAX_DURATION_SEC (default 2h)
      - Optional --user-agent / --cookies / --cookies-from-browser via env vars
      - Scrubbed environment (no HF_TOKEN / API keys bleed into yt-dlp)
      - Disk-space precheck (need at least 2 GB free)
    """
    if not _is_valid_youtube_url(url):
        raise ValueError("Invalid URL. Only YouTube URLs are accepted.")

    output_template = os.path.join(output_dir, "%(id)s.%(ext)s")

    # Audit #10: refuse to start a download if the output dir's filesystem is
    # dangerously low on free space. Threshold is arbitrary but catches the
    # "laptop SSD with 500 MB free" footgun.
    free = shutil.disk_usage(output_dir).free
    if free < 2 * 1024**3:
        raise RuntimeError(
            "Insufficient disk space (< 2 GB free) for YouTube download"
        )

    max_duration = int(os.environ.get("YTDLP_MAX_DURATION_SEC", "7200"))

    # "--" terminates option parsing so a URL that starts with "-" cannot be
    # interpreted as a flag (audit #5).
    cmd = [
        "yt-dlp",
        "--no-exec",
        "--no-batch",
        "--no-playlist",
        "--match-filter", f"duration<={max_duration}",
        "-x",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "-ar 16000 -ac 1",
        "-o", output_template,
    ]

    user_agent = os.environ.get("YTDLP_USER_AGENT")
    if user_agent:
        cmd.extend(["--user-agent", user_agent])

    cookies_file = os.environ.get("YTDLP_COOKIES_FILE")
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])

    cookies_from_browser = os.environ.get("YTDLP_COOKIES_FROM_BROWSER")
    if cookies_from_browser:
        cmd.extend(["--cookies-from-browser", cookies_from_browser])

    cmd.extend(["--", url])

    # Audit #9: strip secrets from the child process environment. Only a tiny
    # allowlist passes through, plus any YTDLP_* variables yt-dlp itself reads.
    allowed_env_keys = {
        "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    }
    clean_env = {
        k: v for k, v in os.environ.items()
        if k in allowed_env_keys or k.startswith("YTDLP_")
    }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env=clean_env,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("YouTube download timed out after 10 minutes")

    if result.returncode != 0:
        # yt-dlp exits 1 for user-facing errors we can parse; anything else is
        # a crash we should surface verbatim.
        if result.returncode != 1:
            raise RuntimeError(
                f"Download terminated unexpectedly (exit {result.returncode})"
            )
        raise RuntimeError(_parse_ytdlp_error(result.stderr))

    for f in os.listdir(output_dir):
        if f.endswith(".wav"):
            return os.path.join(output_dir, f)

    raise RuntimeError("No audio file found after download")


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/live\/)([a-zA-Z0-9_-]{11})',
        r'(?:youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
        r'(?:music\.youtube\.com\/watch\?.*v=)([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


# Timeout for network calls into youtube-transcript-api. The library has no
# native timeout, so we run each call in a worker thread and cancel via the
# executor's timeout machinery.
_TRANSCRIPT_NET_TIMEOUT_SECONDS = 15


def _run_with_timeout(fn, *args, **kwargs):
    """Execute a blocking call in a worker thread with a hard timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        return future.result(timeout=_TRANSCRIPT_NET_TIMEOUT_SECONDS)


def get_youtube_transcript(video_id: str, language: str = "auto") -> Optional[dict]:
    """Try to get existing YouTube transcript (instant, no download needed).

    Returns transcript in our segment format, or None if no transcript available.

    Only swallows well-defined "no captions" errors and network/timeout errors;
    any other exception propagates so the route handler can return 500.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        )
    except ImportError:
        logger.warning("youtube-transcript-api not installed")
        return None

    try:
        api = YouTubeTranscriptApi()

        transcript_list = _run_with_timeout(api.list, video_id)

        transcript = None
        detected_language = None
        is_generated = False

        if language != "auto":
            try:
                found = transcript_list.find_transcript([language])
                transcript = _run_with_timeout(found.fetch)
                detected_language = language
                if hasattr(found, "is_generated"):
                    is_generated = bool(found.is_generated)
            except NoTranscriptFound:
                for t in transcript_list:
                    if t.is_translatable:
                        try:
                            translated = t.translate(language)
                            transcript = _run_with_timeout(translated.fetch)
                            detected_language = language
                            # Translated transcripts are by definition generated.
                            is_generated = True
                            break
                        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
                            continue

        if transcript is None:
            for t in transcript_list:
                transcript = _run_with_timeout(t.fetch)
                detected_language = t.language_code
                if hasattr(t, "is_generated"):
                    is_generated = bool(t.is_generated)
                break

        if transcript is None:
            transcript = _run_with_timeout(api.fetch, video_id)
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
            "is_generated": bool(is_generated),
        }

    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        return None
    except (requests.RequestException, concurrent.futures.TimeoutError) as e:
        logger.warning("Network error fetching YouTube transcript: %s", e)
        return None
