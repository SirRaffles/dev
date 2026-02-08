#!/usr/bin/env python3
"""
Just Press Record Auto-Transcription Watcher

Monitors the iCloud "Just Press Record" folder for new .m4a recordings
and automatically transcribes them using the whisper-transcription-app backend.

Usage:
    python jpr_watcher.py [--scan-existing] [--debug]
"""

import argparse
import logging
import os
import re
import signal
import sys
import threading
import time
import uuid
from datetime import date
from logging.handlers import RotatingFileHandler
from pathlib import Path
from queue import Empty, Queue

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Minimum date filter: only process recordings from this date onwards
MIN_RECORDING_DATE = date(2026, 1, 20)

from api_client import (
    BackendUnavailableError,
    TranscriptionClient,
    TranscriptionError,
)
from config import (
    ICLOUD_PATH,
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_LEVEL,
    LOG_MAX_BYTES,
    SYNC_CHECK_INTERVAL,
    SYNC_STABILITY_DELAY,
    SYNC_TIMEOUT,
    WATCH_EXTENSIONS,
)
from notifier import (
    notify_backend_offline,
    notify_transcription_completed,
    notify_transcription_failed,
    notify_transcription_started,
    notify_watcher_started,
)
from state_manager import StateManager

# Global shutdown flag
shutdown_event = threading.Event()
logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Configure logging with file and console handlers."""
    level = logging.DEBUG if debug else getattr(logging, LOG_LEVEL, logging.INFO)

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # File handler with rotation
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setLevel(level)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    root.addHandler(file_handler)

    # Console handler (for interactive use)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)


def is_icloud_placeholder(file_path: Path) -> bool:
    """Check if file is an iCloud placeholder (not fully downloaded)."""
    try:
        xattrs = os.listxattr(str(file_path))
        # These attributes indicate the file is not fully synced
        placeholder_attrs = [
            "com.apple.icloud.itemDownloadRequested",
            "com.apple.icloud.placeholder",
        ]
        return any(attr in xattrs for attr in placeholder_attrs)
    except (OSError, AttributeError):
        return False


def wait_for_icloud_sync(file_path: Path) -> bool:
    """
    Wait for an iCloud file to fully sync.

    Returns True if file is ready, False if timeout or error.
    """
    start_time = time.time()

    # Quick check: if file is already readable and not a placeholder, return immediately
    if not is_icloud_placeholder(file_path):
        try:
            size = file_path.stat().st_size
            if size > 0:
                with open(file_path, "rb") as f:
                    f.read(1024)
                logger.debug(f"File already synced: {file_path.name}")
                return True
        except Exception:
            pass  # Fall through to retry loop

    # Wait for iCloud sync
    last_size = -1
    stable_count = 0

    while time.time() - start_time < SYNC_TIMEOUT:
        if shutdown_event.is_set():
            return False

        # Check file exists
        if not file_path.exists():
            logger.warning(f"File disappeared: {file_path.name}")
            return False

        # Check for iCloud placeholder (not fully downloaded)
        if is_icloud_placeholder(file_path):
            logger.debug(f"Waiting for iCloud download: {file_path.name}")
            stable_count = 0
            last_size = -1
            time.sleep(SYNC_CHECK_INTERVAL)
            continue

        try:
            current_size = file_path.stat().st_size
            if current_size == 0:
                time.sleep(SYNC_CHECK_INTERVAL)
                continue
        except OSError as e:
            logger.debug(f"Cannot stat file: {e}")
            time.sleep(SYNC_CHECK_INTERVAL)
            continue

        # Check if file size is stable
        if current_size == last_size:
            stable_count += 1
        else:
            stable_count = 0
        last_size = current_size

        # After size is stable, verify file is readable
        if stable_count >= 1:
            try:
                with open(file_path, "rb") as f:
                    f.read(1024)
                logger.debug(f"File synced and ready: {file_path.name}")
                return True
            except Exception as e:
                logger.debug(f"Cannot read file yet: {e}")

        time.sleep(SYNC_CHECK_INTERVAL)

    logger.warning(f"Sync timeout for: {file_path.name}")
    return False


def get_transcript_path(audio_path: Path) -> Path:
    """Get the path for the transcript file (same name, .txt extension)."""
    return audio_path.with_suffix(".txt")


def is_recording_after_min_date(file_path: Path) -> bool:
    """
    Check if recording is from after MIN_RECORDING_DATE.
    JPR files are stored in directories named YYYY-MM-DD.
    Files not in date-named directories are skipped.
    """
    # Look for date pattern in parent directory name
    date_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    match = date_pattern.search(str(file_path.parent))

    if match:
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            recording_date = date(year, month, day)
            return recording_date >= MIN_RECORDING_DATE
        except ValueError:
            pass

    # If we can't determine date, skip the file (strict mode)
    logger.debug(f"Skipping file without date directory: {file_path.name}")
    return False


def process_file(
    file_path: Path,
    client: TranscriptionClient,
    state: StateManager,
    retry_attempt: int = 0,
) -> bool:
    """
    Process a single audio file.

    Returns True if successful, False otherwise.
    """
    filename = file_path.name
    transcript_path = get_transcript_path(file_path)

    # Skip recordings before MIN_RECORDING_DATE
    if not is_recording_after_min_date(file_path):
        logger.debug(f"Skipping (before {MIN_RECORDING_DATE}): {filename}")
        return True

    # Skip if transcript already exists
    if transcript_path.exists():
        logger.info(f"Transcript already exists: {transcript_path.name}")
        state.mark_completed(file_path, transcript_path)
        return True

    # Skip if already processed
    if state.is_processed(file_path):
        logger.debug(f"Already processed: {filename}")
        return True

    # Skip if currently processing
    if state.is_processing(file_path):
        logger.debug(f"Already processing: {filename}")
        return True

    # Wait for iCloud sync
    if not wait_for_icloud_sync(file_path):
        logger.warning(f"Skipping (sync failed): {filename}")
        return False

    logger.info(f"Processing: {filename}")
    notify_transcription_started(filename)

    try:
        # Mark state BEFORE submission to prevent crash orphans
        pending_id = str(uuid.uuid4())
        state.mark_pending_submission(file_path, pending_id)

        # Submit transcription
        job_id = client.submit_transcription(file_path)
        state.mark_processing(file_path, job_id)

        # Progress callback for logging
        def on_progress(progress: int, message: str):
            logger.debug(f"  {filename}: {progress}% - {message}")

        # Poll until complete
        client.poll_until_complete(job_id, progress_callback=on_progress)

        # Download transcript
        transcript_text = client.get_transcript_text(job_id)

        # Save transcript next to audio file
        transcript_path.write_text(transcript_text, encoding="utf-8")
        logger.info(f"Saved transcript: {transcript_path.name}")

        # Update state
        state.mark_completed(file_path, transcript_path)
        state.remove_from_retry_queue(file_path)

        # Notify
        notify_transcription_completed(filename, transcript_path.name)
        return True

    except BackendUnavailableError as e:
        logger.warning(f"Backend unavailable: {e}")
        state.mark_failed(file_path, str(e), retry_attempt)
        if retry_attempt == 0:
            notify_backend_offline()
        return False

    except TranscriptionError as e:
        logger.error(f"Transcription failed: {filename} - {e}")
        state.mark_failed(file_path, str(e), retry_attempt)
        notify_transcription_failed(filename, str(e))
        return False

    except Exception as e:
        logger.exception(f"Unexpected error processing {filename}")
        state.mark_failed(file_path, str(e), retry_attempt)
        notify_transcription_failed(filename, str(e))
        return False


class JPREventHandler(FileSystemEventHandler):
    """Handle file system events for new recordings."""

    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue

    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() in WATCH_EXTENSIONS:
            logger.info(f"New file detected: {path.name}")
            self.queue.put(path)

    def on_modified(self, event):
        """Handle file modification (may indicate sync completion)."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() in WATCH_EXTENSIONS:
            # Only add if not already in queue
            self.queue.put(path)


def process_queue(
    queue: Queue,
    client: TranscriptionClient,
    state: StateManager,
) -> None:
    """Process files from the queue with continuous health monitoring."""
    processed_this_cycle = set()
    backend_available = True
    last_health_check = 0
    health_check_interval = 30  # Check backend health every 30 seconds
    backend_wait_interval = 60  # When backend is down, wait 60 seconds between checks

    while not shutdown_event.is_set():
        current_time = time.time()

        # Periodic health check
        if current_time - last_health_check > health_check_interval:
            was_available = backend_available
            backend_available = client.is_backend_available(bypass_circuit_breaker=True)
            last_health_check = current_time

            if backend_available and not was_available:
                logger.info("Backend is now available, resuming processing")
                notify_backend_offline()  # Actually notify backend is back online
            elif not backend_available and was_available:
                logger.warning("Backend became unavailable, pausing processing")
                notify_backend_offline()

        # If backend is down, wait and skip processing
        if not backend_available:
            # Check circuit breaker state
            if not client.circuit_breaker.can_attempt():
                retry_in = client.circuit_breaker.time_until_retry()
                if retry_in > 0:
                    logger.debug(f"Circuit breaker open, waiting {retry_in:.0f}s")
                    # Sleep for the shorter of retry_in or backend_wait_interval
                    time.sleep(min(retry_in, backend_wait_interval))
                    continue

            time.sleep(backend_wait_interval)
            continue

        try:
            # Get file from queue with timeout
            file_path = queue.get(timeout=1.0)

            # Deduplicate within cycle
            key = str(file_path.resolve())
            if key in processed_this_cycle:
                continue
            processed_this_cycle.add(key)

            # Small delay to let file settle
            time.sleep(1)

            # Process the file
            success = process_file(file_path, client, state)

            # Update backend availability based on result
            if not success:
                # Re-check backend health after failure
                backend_available = client.is_backend_available(bypass_circuit_breaker=True)
                last_health_check = current_time

        except Empty:
            # Check for pending retries only if backend is available
            if backend_available:
                for retry in state.get_pending_retries():
                    file_path = Path(retry["file_path"])
                    if file_path.exists():
                        logger.info(f"Retrying: {file_path.name} (attempt {retry['attempt']})")
                        process_file(file_path, client, state, retry["attempt"])
                    else:
                        state.remove_from_retry_queue(file_path)

            processed_this_cycle.clear()


def scan_existing_files(watch_dir: Path, queue: Queue, state: StateManager) -> int:
    """Scan for existing unprocessed files and add to queue."""
    count = 0
    skipped = 0
    for ext in WATCH_EXTENSIONS:
        for file_path in watch_dir.rglob(f"*{ext}"):
            # Skip recordings before MIN_RECORDING_DATE
            if not is_recording_after_min_date(file_path):
                skipped += 1
                continue

            if not state.is_processed(file_path):
                transcript_path = get_transcript_path(file_path)
                if not transcript_path.exists():
                    logger.info(f"Found unprocessed file: {file_path.name}")
                    queue.put(file_path)
                    count += 1

    if skipped > 0:
        logger.info(f"Skipped {skipped} files before {MIN_RECORDING_DATE}")
    return count


def recover_processing_jobs(client: TranscriptionClient, state: StateManager) -> None:
    """Recover jobs that were processing when watcher stopped."""
    for job in state.get_processing_jobs():
        file_path = Path(job["file_path"])
        job_id = job.get("job_id")

        if not file_path.exists():
            logger.info(f"Removing orphaned job: {file_path}")
            state.remove_from_retry_queue(file_path)
            continue

        if job_id:
            try:
                # Check if job is still running on backend
                status = client.get_job_status(job_id)
                if status.get("status") == "completed":
                    # Download and save transcript
                    transcript_text = client.get_transcript_text(job_id)
                    transcript_path = get_transcript_path(file_path)
                    transcript_path.write_text(transcript_text, encoding="utf-8")
                    state.mark_completed(file_path, transcript_path)
                    logger.info(f"Recovered completed job: {file_path.name}")
                elif status.get("status") == "failed":
                    state.mark_failed(file_path, status.get("error", "Unknown"), 0)
                else:
                    # Still processing, continue polling
                    logger.info(f"Job still processing: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not recover job {job_id}: {e}")
                state.mark_failed(file_path, str(e), 0)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info("Shutdown signal received, stopping...")
    shutdown_event.set()


def main():
    parser = argparse.ArgumentParser(
        description="Auto-transcribe Just Press Record recordings"
    )
    parser.add_argument(
        "--scan-existing",
        action="store_true",
        help="Scan and process existing unprocessed files on startup",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--watch-dir",
        type=Path,
        default=ICLOUD_PATH,
        help=f"Directory to watch (default: {ICLOUD_PATH})",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(debug=args.debug)

    # Expand user path
    watch_dir = args.watch_dir.expanduser()

    # Verify watch directory exists
    if not watch_dir.exists():
        logger.error(f"Watch directory does not exist: {watch_dir}")
        logger.error("Make sure iCloud is syncing and Just Press Record is installed")
        sys.exit(1)

    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Initialize components
    client = TranscriptionClient()
    state = StateManager()
    file_queue: Queue = Queue()

    logger.info("=" * 50)
    logger.info("Just Press Record Auto-Transcription Watcher")
    logger.info("=" * 50)
    logger.info(f"Watching: {watch_dir}")

    # Check backend availability
    if client.is_backend_available():
        logger.info("Backend is available")
    else:
        logger.warning("Backend is not available - files will be queued for retry")

    # Recover any interrupted jobs
    if client.is_backend_available():
        recover_processing_jobs(client, state)

    # Cleanup orphaned entries
    state.cleanup_orphaned(watch_dir)

    # Scan existing files if requested
    if args.scan_existing:
        count = scan_existing_files(watch_dir, file_queue, state)
        logger.info(f"Found {count} unprocessed files")

    # Send startup notification
    notify_watcher_started(str(watch_dir))

    # Setup file system observer
    event_handler = JPREventHandler(file_queue)
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=True)
    observer.start()

    logger.info("Watcher started - press Ctrl+C to stop")

    try:
        # Process queue in main thread
        process_queue(file_queue, client, state)
    finally:
        observer.stop()
        observer.join()
        logger.info("Watcher stopped")


if __name__ == "__main__":
    main()
