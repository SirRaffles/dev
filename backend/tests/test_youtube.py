"""Tests for the hardened YouTube service."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.youtube import (  # noqa: E402
    YOUTUBE_URL_RE,
    _is_valid_youtube_url,
    _parse_ytdlp_error,
    download_youtube_audio,
)


# ---------------------------------------------------------------------------
# YOUTUBE_URL_RE — positive & negative cases
# ---------------------------------------------------------------------------


VALID_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "http://youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
    "https://www.youtube.com/shorts/abcdefghijk",
    "https://www.youtube.com/live/abcdefghijk",
    "https://www.youtube.com/embed/abcdefghijk",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ?t=90",
    "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
]


INVALID_URLS = [
    # No v= parameter
    "https://www.youtube.com/watch?foo=bar",
    # 10-char id (too short) — 11 chars required, this has only 10
    "https://www.youtube.com/watch?v=shortidxxx",
    # Invalid character in id (spaces / punctuation disallowed)
    "https://www.youtube.com/watch?v=bad!id#####",
    # Wrong host
    "https://vimeo.com/watch?v=dQw4w9WgXcQ",
    # Evil scheme
    "javascript:alert(1)//youtube.com/watch?v=dQw4w9WgXcQ",
    # Missing scheme
    "www.youtube.com/watch?v=dQw4w9WgXcQ",
    # youtu.be with too-short id
    "https://youtu.be/short",
    # Raw IP masquerading
    "https://127.0.0.1/watch?v=dQw4w9WgXcQ",
]


@pytest.mark.parametrize("url", VALID_URLS)
def test_youtube_url_re_matches_valid(url: str) -> None:
    assert YOUTUBE_URL_RE.match(url), f"should match: {url}"


@pytest.mark.parametrize("url", INVALID_URLS)
def test_youtube_url_re_rejects_invalid(url: str) -> None:
    assert not YOUTUBE_URL_RE.match(url), f"should NOT match: {url}"


@pytest.mark.parametrize("url", VALID_URLS)
def test_is_valid_delegates_to_canonical_regex(url: str) -> None:
    assert _is_valid_youtube_url(url) is True


@pytest.mark.parametrize("url", INVALID_URLS)
def test_is_valid_rejects_invalid(url: str) -> None:
    assert _is_valid_youtube_url(url) is False


# ---------------------------------------------------------------------------
# _parse_ytdlp_error — every mapped pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stderr,expected_fragment",
    [
        ("ERROR: Video unavailable", "unavailable or private"),
        ("This is a Private video", "unavailable or private"),
        ("Sign in to confirm your age", "age-restricted"),
        ("age restricted content", "age-restricted"),
        ("Not a valid URL", "Invalid YouTube URL"),
        ("removed for a copyright claim", "copyright"),
        ("Precondition check failed", "authentication"),
        ("ERROR: HTTP Error 429: Too Many Requests", "rate-limited"),
    ],
)
def test_parse_ytdlp_error_patterns(stderr: str, expected_fragment: str) -> None:
    msg = _parse_ytdlp_error(stderr)
    assert expected_fragment.lower() in msg.lower()


def test_parse_ytdlp_error_default() -> None:
    """Unknown errors fall through to the generic message."""
    msg = _parse_ytdlp_error("some totally unexpected yt-dlp failure")
    assert "unavailable or region-restricted" in msg


# ---------------------------------------------------------------------------
# download_youtube_audio — argv, env scrubbing, disk precheck
# ---------------------------------------------------------------------------


URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def tmp_output_dir(tmp_path):
    d = tmp_path / "yt-out"
    d.mkdir()
    return str(d)


def _disk_usage(free: int):
    # shutil.disk_usage returns a NamedTuple(total, used, free); a MagicMock
    # with a .free attribute is enough for our code path.
    m = MagicMock()
    m.free = free
    m.total = free * 2
    m.used = free
    return m


def test_disk_space_precheck_raises_when_low(tmp_output_dir, monkeypatch):
    """Fail fast if less than 2 GB free — before forking yt-dlp."""
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=1 * 1024**3),
    )
    with patch("services.youtube.subprocess.run") as run:
        with pytest.raises(RuntimeError, match="Insufficient disk space"):
            download_youtube_audio(URL, tmp_output_dir)
        run.assert_not_called()


def test_download_scrubs_env_of_secrets(tmp_output_dir, monkeypatch):
    """HF_TOKEN and other secrets must NOT leak into yt-dlp's env."""
    monkeypatch.setenv("HF_TOKEN", "super-secret-value")
    monkeypatch.setenv("MISTRAL_API_KEY", "another-secret")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=10 * 1024**3),
    )

    # Simulate successful yt-dlp run
    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        # Create the fake output wav so the function can find it
        wav = os.path.join(tmp_output_dir, "abc.wav")
        with open(wav, "wb") as f:
            f.write(b"RIFF....WAVE")
        return result

    with patch("services.youtube.subprocess.run", side_effect=fake_run) as run:
        out = download_youtube_audio(URL, tmp_output_dir)

    assert out.endswith(".wav")
    # Inspect env passed to subprocess.run
    _args, kwargs = run.call_args
    env = kwargs.get("env")
    assert env is not None, "env must be passed to subprocess.run"
    assert "PATH" in env
    assert "HF_TOKEN" not in env, "HF_TOKEN must NOT be forwarded"
    assert "MISTRAL_API_KEY" not in env, "API keys must NOT be forwarded"


def test_download_passes_no_playlist_and_match_filter(tmp_output_dir, monkeypatch):
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=10 * 1024**3),
    )
    monkeypatch.delenv("YTDLP_MAX_DURATION_SEC", raising=False)

    def fake_run(cmd, *args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        wav = os.path.join(tmp_output_dir, "abc.wav")
        with open(wav, "wb") as f:
            f.write(b"RIFF....WAVE")
        return result

    with patch("services.youtube.subprocess.run", side_effect=fake_run) as run:
        download_youtube_audio(URL, tmp_output_dir)

    (cmd,), _kwargs = run.call_args
    assert "--no-playlist" in cmd
    # --match-filter followed by duration<=7200 (default)
    mf_idx = cmd.index("--match-filter")
    assert cmd[mf_idx + 1] == "duration<=7200"
    # -- separator present, URL is the last arg
    assert "--" in cmd
    dash_idx = cmd.index("--")
    assert cmd[dash_idx + 1] == URL
    # URL only appears once, and only after the --
    assert cmd.count(URL) == 1


def test_download_respects_custom_max_duration(tmp_output_dir, monkeypatch):
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=10 * 1024**3),
    )
    monkeypatch.setenv("YTDLP_MAX_DURATION_SEC", "300")

    def fake_run(cmd, *args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        wav = os.path.join(tmp_output_dir, "abc.wav")
        with open(wav, "wb") as f:
            f.write(b"RIFF....WAVE")
        return result

    with patch("services.youtube.subprocess.run", side_effect=fake_run) as run:
        download_youtube_audio(URL, tmp_output_dir)

    (cmd,), _kwargs = run.call_args
    mf_idx = cmd.index("--match-filter")
    assert cmd[mf_idx + 1] == "duration<=300"


def test_download_includes_cookies_when_env_set(tmp_output_dir, monkeypatch):
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=10 * 1024**3),
    )
    monkeypatch.setenv("YTDLP_COOKIES_FROM_BROWSER", "safari")
    monkeypatch.setenv("YTDLP_USER_AGENT", "custom-ua/1.0")
    monkeypatch.delenv("YTDLP_COOKIES_FILE", raising=False)

    def fake_run(cmd, *args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        wav = os.path.join(tmp_output_dir, "abc.wav")
        with open(wav, "wb") as f:
            f.write(b"RIFF....WAVE")
        return result

    with patch("services.youtube.subprocess.run", side_effect=fake_run) as run:
        download_youtube_audio(URL, tmp_output_dir)

    (cmd,), _kwargs = run.call_args
    assert "--cookies-from-browser" in cmd
    cfb_idx = cmd.index("--cookies-from-browser")
    assert cmd[cfb_idx + 1] == "safari"
    assert "--user-agent" in cmd
    ua_idx = cmd.index("--user-agent")
    assert cmd[ua_idx + 1] == "custom-ua/1.0"


def test_download_invalid_url_rejected(tmp_output_dir):
    with pytest.raises(ValueError, match="Invalid URL"):
        download_youtube_audio("https://evil.example.com/watch?v=xxx", tmp_output_dir)


def test_download_unexpected_exit_code_surfaces(tmp_output_dir, monkeypatch):
    """Any exit code other than 0 or 1 should raise a distinctive error."""
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=10 * 1024**3),
    )

    def fake_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 137  # SIGKILL-ish
        result.stderr = ""
        return result

    with patch("services.youtube.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="exit 137"):
            download_youtube_audio(URL, tmp_output_dir)


def test_download_timeout_raises(tmp_output_dir, monkeypatch):
    monkeypatch.setattr(
        "services.youtube.shutil.disk_usage",
        lambda _p: _disk_usage(free=10 * 1024**3),
    )

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=600)

    with patch("services.youtube.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="timed out"):
            download_youtube_audio(URL, tmp_output_dir)
