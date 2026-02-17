"""
macOS notification integration using osascript.
No external dependencies required.
"""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def notify(
    title: str,
    message: str,
    subtitle: Optional[str] = None,
    sound: bool = True,
) -> bool:
    """
    Send a macOS notification using osascript.

    Args:
        title: The notification title
        message: The notification body text
        subtitle: Optional subtitle
        sound: Whether to play the notification sound

    Returns:
        True if notification was sent successfully
    """
    # Escape quotes for AppleScript
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')

    script = f'display notification "{message}" with title "{title}"'

    if subtitle:
        subtitle = subtitle.replace('"', '\\"')
        script = f'display notification "{message}" with title "{title}" subtitle "{subtitle}"'

    if sound:
        script += ' sound name "Glass"'

    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=5,
        )
        logger.debug(f"Notification sent: {title}")
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to send notification: {e}")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Notification timeout")
        return False


def notify_transcription_started(filename: str) -> bool:
    """Notify that transcription has started."""
    return notify(
        title="Transcription Started",
        message=f"Processing: {filename}",
        sound=False,
    )


def notify_transcription_completed(filename: str, transcript_path: str) -> bool:
    """Notify that transcription completed successfully."""
    return notify(
        title="Transcription Complete",
        message=f"Saved: {transcript_path}",
        subtitle=filename,
        sound=True,
    )


def notify_transcription_failed(filename: str, error: str) -> bool:
    """Notify that transcription failed."""
    # Truncate long error messages
    if len(error) > 100:
        error = error[:97] + "..."

    return notify(
        title="Transcription Failed",
        message=error,
        subtitle=filename,
        sound=True,
    )


def notify_watcher_started(watch_path: str) -> bool:
    """Notify that the watcher has started."""
    return notify(
        title="JPR Watcher Started",
        message=f"Monitoring: {watch_path}",
        sound=False,
    )


def notify_new_file_detected(filename: str) -> bool:
    """Notify that a new recording was detected (low priority, no sound)."""
    return notify(
        title="New Recording Detected",
        message=f"Queued: {filename}",
        sound=False,
    )


def notify_backend_offline() -> bool:
    """Notify that the backend is offline."""
    return notify(
        title="Transcription Backend Offline",
        message="Files will be queued for retry",
        sound=True,
    )


def notify_backend_online() -> bool:
    """Notify that the backend is back online."""
    return notify(
        title="Transcription Backend Online",
        message="Resuming transcription",
        sound=False,
    )


def notify_circuit_breaker_open(retry_in_seconds: float) -> bool:
    """Notify that the circuit breaker has opened (backend unreachable)."""
    retry_min = int(retry_in_seconds // 60)
    if retry_min > 0:
        retry_msg = f"Will retry in {retry_min}m"
    else:
        retry_msg = f"Will retry in {int(retry_in_seconds)}s"
    return notify(
        title="Backend Unreachable",
        message=retry_msg,
        sound=True,
    )
