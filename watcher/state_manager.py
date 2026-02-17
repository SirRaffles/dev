"""
State manager for tracking processed files.
Persists state to a JSON file to avoid re-transcription after restarts.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import STATE_FILE

logger = logging.getLogger(__name__)


class StateManager:
    """Manages persistent state for processed files."""

    def __init__(self, state_file: Path = STATE_FILE):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load state from JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                    logger.info(f"Loaded state with {len(state.get('processed_files', {}))} processed files")
                    return state
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load state file: {e}")
                return self._default_state()
        return self._default_state()

    def _default_state(self) -> dict:
        """Return default empty state."""
        return {
            "version": 1,
            "processed_files": {},
            "pending_retries": [],
            "last_scan": None,
        }

    def _save_state(self) -> None:
        """Save state to JSON file atomically."""
        self.state["last_scan"] = datetime.now().isoformat()

        # Write to temp file first, then rename (atomic on POSIX)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=self.state_file.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.state, f, indent=2)
            os.replace(temp_path, self.state_file)
        except Exception:
            os.unlink(temp_path)
            raise

    def is_processed(self, file_path: Path) -> bool:
        """Check if a file has already been successfully processed."""
        key = str(file_path.resolve())
        entry = self.state["processed_files"].get(key)

        if entry is None:
            return False

        # Skip permanently failed files (e.g. corrupt/empty files)
        if entry.get("status") == "permanently_failed":
            return True

        # Check if file was modified since processing
        if entry.get("status") == "completed":
            try:
                current_mtime = file_path.stat().st_mtime
                stored_mtime = entry.get("file_mtime", 0)
                if current_mtime > stored_mtime:
                    logger.info(f"File modified since processing: {file_path.name}")
                    return False
            except OSError:
                pass
            return True

        return False

    def is_processing(self, file_path: Path) -> bool:
        """Check if a file is currently being processed or pending submission."""
        key = str(file_path.resolve())
        entry = self.state["processed_files"].get(key)
        if entry is None:
            return False
        status = entry.get("status")
        return status in ("processing", "pending_submission")

    def mark_pending_submission(self, file_path: Path, pending_id: str) -> None:
        """
        Mark a file as pending submission (before sending to backend).
        This ensures we track the file even if we crash during submission.
        """
        key = str(file_path.resolve())
        stat = file_path.stat()

        self.state["processed_files"][key] = {
            "status": "pending_submission",
            "pending_id": pending_id,
            "started_at": datetime.now().isoformat(),
            "file_size": stat.st_size,
            "file_mtime": stat.st_mtime,
        }
        self._save_state()
        logger.debug(f"Marked as pending submission: {file_path.name}")

    def mark_processing(self, file_path: Path, job_id: str) -> None:
        """Mark a file as currently being processed."""
        key = str(file_path.resolve())
        entry = self.state["processed_files"].get(key, {})

        # Preserve existing data but update status
        entry.update({
            "status": "processing",
            "job_id": job_id,
            "submitted_at": datetime.now().isoformat(),
        })

        # If we don't have file stats yet (shouldn't happen), add them
        if "file_size" not in entry:
            stat = file_path.stat()
            entry["file_size"] = stat.st_size
            entry["file_mtime"] = stat.st_mtime
            entry["started_at"] = datetime.now().isoformat()

        self.state["processed_files"][key] = entry
        self._save_state()
        logger.debug(f"Marked as processing: {file_path.name}")

    def mark_completed(self, file_path: Path, transcript_path: Path) -> None:
        """Mark a file as successfully processed."""
        key = str(file_path.resolve())
        entry = self.state["processed_files"].get(key, {})

        entry.update({
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "transcript_path": str(transcript_path.resolve()),
        })

        self.state["processed_files"][key] = entry
        self._save_state()
        logger.info(f"Marked as completed: {file_path.name}")

    def mark_permanently_failed(self, file_path: Path, error: str) -> None:
        """Mark a file as permanently failed (will not be retried)."""
        key = str(file_path.resolve())
        entry = self.state["processed_files"].get(key, {})
        try:
            entry["file_size"] = file_path.stat().st_size
            entry["file_mtime"] = file_path.stat().st_mtime
        except OSError:
            pass
        entry.update({
            "status": "permanently_failed",
            "failed_at": datetime.now().isoformat(),
            "error": error,
        })
        self.state["processed_files"][key] = entry
        self._save_state()
        logger.warning(f"Permanently failed: {file_path.name} - {error}")

    def mark_failed(self, file_path: Path, error: str, attempt: int = 0) -> None:
        """Mark a file as failed and add to retry queue."""
        key = str(file_path.resolve())
        entry = self.state["processed_files"].get(key, {})

        entry.update({
            "status": "failed",
            "failed_at": datetime.now().isoformat(),
            "error": error,
            "retry_attempt": attempt,
        })

        self.state["processed_files"][key] = entry

        # Add to retry queue if not max attempts, otherwise permanently fail
        from config import RETRY_MAX_ATTEMPTS
        if attempt < RETRY_MAX_ATTEMPTS:
            self._add_to_retry_queue(file_path, attempt + 1)
        else:
            # Max retries exhausted — remove from retry queue and mark permanently failed
            self.state["pending_retries"] = [
                r for r in self.state["pending_retries"]
                if r["file_path"] != key
            ]
            entry["status"] = "permanently_failed"
            logger.warning(f"Max retries exhausted for {file_path.name}, marking permanently failed")

        self._save_state()
        logger.warning(f"Marked as failed: {file_path.name} - {error}")

    def _add_to_retry_queue(self, file_path: Path, attempt: int) -> None:
        """Add file to retry queue with backoff timing."""
        from config import RETRY_DELAY_BASE, RETRY_BACKOFF_MULTIPLIER

        delay_seconds = RETRY_DELAY_BASE * (RETRY_BACKOFF_MULTIPLIER ** (attempt - 1))
        retry_at = datetime.now().timestamp() + delay_seconds

        # Remove any existing entry for this file
        self.state["pending_retries"] = [
            r for r in self.state["pending_retries"]
            if r["file_path"] != str(file_path.resolve())
        ]

        self.state["pending_retries"].append({
            "file_path": str(file_path.resolve()),
            "retry_at": retry_at,
            "attempt": attempt,
        })
        logger.info(f"Added to retry queue: {file_path.name} (attempt {attempt}, retry in {delay_seconds}s)")

    def get_pending_retries(self) -> list:
        """Get files ready for retry."""
        now = datetime.now().timestamp()
        ready = [
            r for r in self.state["pending_retries"]
            if r["retry_at"] <= now
        ]
        return ready

    def remove_from_retry_queue(self, file_path: Path) -> None:
        """Remove a file from the retry queue."""
        key = str(file_path.resolve())
        self.state["pending_retries"] = [
            r for r in self.state["pending_retries"]
            if r["file_path"] != key
        ]
        self._save_state()

    def get_processing_jobs(self) -> list:
        """Get files that were marked as processing (for crash recovery)."""
        return [
            {"file_path": k, **v}
            for k, v in self.state["processed_files"].items()
            if v.get("status") == "processing"
        ]

    def cleanup_orphaned(self, watch_dir: Path) -> None:
        """Remove entries for files that no longer exist."""
        to_remove = []
        for key in self.state["processed_files"]:
            if not Path(key).exists():
                to_remove.append(key)

        for key in to_remove:
            del self.state["processed_files"][key]
            logger.info(f"Removed orphaned entry: {key}")

        if to_remove:
            self._save_state()
