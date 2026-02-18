"""
API client for the whisper-transcription-app backend.
Handles file upload, job polling, and transcript retrieval.
Includes circuit breaker pattern to prevent hammering unavailable backend.
"""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

import requests
from requests.exceptions import ConnectionError, Timeout

from config import (
    API_TIMEOUT,
    BACKEND_URL,
    ENABLE_CALL_INTELLIGENCE,
    MAX_POLL_TIME,
    POLL_INTERVAL,
    REFINEMENT_TIMEOUT,
    TRANSCRIPTION_SETTINGS,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker to prevent hammering backend when it's down.

    States:
    - closed: Normal operation, requests pass through
    - open: Backend is down, requests fail fast
    - half-open: Testing if backend recovered
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open

    def record_success(self) -> None:
        """Record a successful request, reset failure count."""
        self.failures = 0
        self.state = "closed"
        logger.debug("Circuit breaker: success recorded, state=closed")

    def record_failure(self) -> None:
        """Record a failed request, potentially open the circuit."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            if self.state != "open":
                logger.warning(
                    f"Circuit breaker OPEN after {self.failures} failures. "
                    f"Will retry in {self.recovery_timeout}s"
                )
            self.state = "open"

    def can_attempt(self) -> bool:
        """Check if a request can be attempted."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if recovery timeout has elapsed
            if self.last_failure_time and \
               time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("Circuit breaker: recovery timeout elapsed, trying half-open")
                self.state = "half-open"
                return True
            return False

        # half-open: allow one request to test recovery
        return self.state == "half-open"

    def time_until_retry(self) -> float:
        """Get seconds until next retry is allowed."""
        if self.state != "open" or not self.last_failure_time:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, self.recovery_timeout - elapsed)


class TranscriptionError(Exception):
    """Raised when transcription fails."""
    pass


class BackendUnavailableError(Exception):
    """Raised when backend is not reachable."""
    pass


class TranscriptionClient:
    """HTTP client for the transcription backend API."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=300)

    def is_backend_available(self, bypass_circuit_breaker: bool = False) -> bool:
        """
        Check if the backend is running and healthy.

        Args:
            bypass_circuit_breaker: If True, check backend even if circuit is open
        """
        # Check circuit breaker first (unless bypassed for health checks)
        if not bypass_circuit_breaker and not self.circuit_breaker.can_attempt():
            retry_in = self.circuit_breaker.time_until_retry()
            logger.debug(f"Circuit breaker open, retry in {retry_in:.0f}s")
            return False

        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            if response.status_code == 200:
                # Check if model is actually loaded
                data = response.json()
                if data.get("model_loaded", False):
                    self.circuit_breaker.record_success()
                    return True
                else:
                    logger.warning("Backend healthy but model not loaded")
                    return False
            self.circuit_breaker.record_failure()
            return False
        except (ConnectionError, Timeout):
            self.circuit_breaker.record_failure()
            return False

    def submit_transcription(self, file_path: Path) -> str:
        """
        Upload a file for transcription.

        Args:
            file_path: Path to the audio file

        Returns:
            job_id: The job ID to poll for status

        Raises:
            BackendUnavailableError: If backend is not reachable
            TranscriptionError: If upload fails
        """
        # Check circuit breaker first
        if not self.circuit_breaker.can_attempt():
            retry_in = self.circuit_breaker.time_until_retry()
            raise BackendUnavailableError(
                f"Circuit breaker open, backend unavailable. Retry in {retry_in:.0f}s"
            )

        if not self.is_backend_available():
            raise BackendUnavailableError("Backend is not available")

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path.name, f, "audio/mp4")}
                response = self.session.post(
                    f"{self.base_url}/transcribe/file",
                    files=files,
                    params=TRANSCRIPTION_SETTINGS,
                    timeout=API_TIMEOUT,
                )

            if response.status_code != 200:
                self.circuit_breaker.record_failure()
                raise TranscriptionError(
                    f"Upload failed with status {response.status_code}: {response.text}"
                )

            data = response.json()
            job_id = data.get("job_id")
            if not job_id:
                raise TranscriptionError("No job_id in response")

            self.circuit_breaker.record_success()
            logger.info(f"Submitted transcription job: {job_id}")
            return job_id

        except ConnectionError as e:
            self.circuit_breaker.record_failure()
            raise BackendUnavailableError(f"Connection error: {e}")
        except Timeout as e:
            self.circuit_breaker.record_failure()
            raise TranscriptionError(f"Upload timeout: {e}")

    def get_job_status(self, job_id: str) -> dict:
        """
        Get the current status of a transcription job.

        Returns:
            dict with keys: status, progress, progress_message, result (if complete)
        """
        try:
            response = self.session.get(
                f"{self.base_url}/job/{job_id}",
                timeout=API_TIMEOUT,
            )
            if response.status_code == 404:
                raise TranscriptionError(f"Job not found: {job_id}")
            response.raise_for_status()
            self.circuit_breaker.record_success()
            return response.json()
        except ConnectionError as e:
            self.circuit_breaker.record_failure()
            raise BackendUnavailableError(f"Connection error: {e}")

    def poll_until_complete(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict:
        """
        Poll job status until completion or failure.

        Args:
            job_id: The job ID to poll
            progress_callback: Optional callback(progress, message) for progress updates

        Returns:
            The completed job data

        Raises:
            TranscriptionError: If job fails or times out
            BackendUnavailableError: If backend becomes unavailable
        """
        start_time = time.time()
        last_progress = -1

        while True:
            elapsed = time.time() - start_time
            if elapsed > MAX_POLL_TIME:
                raise TranscriptionError(
                    f"Transcription timeout after {MAX_POLL_TIME}s"
                )

            status = self.get_job_status(job_id)
            job_status = status.get("status")
            progress = status.get("progress", 0)
            message = status.get("progress_message", "")

            # Call progress callback if progress changed
            if progress != last_progress and progress_callback:
                progress_callback(progress, message)
                last_progress = progress

            if job_status == "completed":
                logger.info(f"Job {job_id} completed in {elapsed:.1f}s")
                return status

            if job_status == "failed":
                error = status.get("error", "Unknown error")
                raise TranscriptionError(f"Transcription failed: {error}")

            time.sleep(POLL_INTERVAL)

    def get_transcript_text(self, job_id: str) -> str:
        """
        Download the transcript as plain text.

        Returns:
            The transcript text with timestamps and speakers
        """
        try:
            response = self.session.get(
                f"{self.base_url}/job/{job_id}/export",
                params={"format": "txt"},
                timeout=API_TIMEOUT,
            )
            response.raise_for_status()
            self.circuit_breaker.record_success()
            return response.text
        except ConnectionError as e:
            self.circuit_breaker.record_failure()
            raise BackendUnavailableError(f"Connection error: {e}")

    def submit_refinement(self, job_id: str) -> bool:
        """
        Submit a completed job for transcript refinement.

        Returns True if refinement was started, False otherwise.
        """
        try:
            response = self.session.post(
                f"{self.base_url}/refine/job/{job_id}",
                timeout=API_TIMEOUT,
            )
            if response.status_code == 503:
                logger.info("Refinement not available on backend")
                return False
            response.raise_for_status()
            data = response.json()
            logger.info("Refinement started for job %s: %s", job_id, data.get("message", ""))
            return True
        except Exception as e:
            logger.warning("Failed to submit refinement for job %s: %s", job_id, e)
            return False

    def poll_refinement(self, job_id: str) -> Optional[dict]:
        """
        Poll refinement status until complete or timeout.

        Returns refinement result dict, or None on failure/timeout.
        """
        start_time = time.time()
        poll_interval = 5

        while time.time() - start_time < REFINEMENT_TIMEOUT:
            try:
                response = self.session.get(
                    f"{self.base_url}/refine/job/{job_id}",
                    timeout=API_TIMEOUT,
                )
                if response.status_code == 404:
                    logger.warning("Refinement not found for job %s", job_id)
                    return None
                response.raise_for_status()
                data = response.json()
                status = data.get("status", "")

                if status == "completed":
                    logger.info("Refinement completed for job %s", job_id)
                    return data
                elif status == "failed":
                    logger.warning("Refinement failed for job %s: %s", job_id, data.get("error", ""))
                    return None

                time.sleep(poll_interval)
            except Exception as e:
                logger.warning("Error polling refinement for job %s: %s", job_id, e)
                time.sleep(poll_interval)

        logger.warning("Refinement timeout for job %s after %ds", job_id, REFINEMENT_TIMEOUT)
        return None

    def get_refined_transcript_text(self, job_id: str) -> Optional[str]:
        """
        Download the refined transcript as plain text.

        Returns the refined transcript text, or None on failure.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/refine/job/{job_id}/export",
                params={"format": "txt"},
                timeout=API_TIMEOUT,
            )
            if response.status_code != 200:
                logger.warning("Failed to get refined transcript for job %s: %s", job_id, response.status_code)
                return None
            return response.text
        except Exception as e:
            logger.warning("Error getting refined transcript for job %s: %s", job_id, e)
            return None

    def register_call(self, job_id: str, source_path: str) -> Optional[dict]:
        """
        Register a completed transcription as a call for intelligence processing.

        Returns call metadata dict, or None on failure.
        """
        if not ENABLE_CALL_INTELLIGENCE:
            return None

        try:
            response = self.session.post(
                f"{self.base_url}/calls/{job_id}/register",
                json={
                    "source_type": "jpr_watcher",
                    "source_path": source_path,
                },
                timeout=API_TIMEOUT,
            )
            if response.status_code == 200:
                logger.info("Registered call for job %s", job_id)
                return response.json()
            else:
                logger.warning("Failed to register call for job %s: %s", job_id, response.status_code)
                return None
        except Exception as e:
            logger.warning("Error registering call for job %s: %s", job_id, e)
            return None

    def identify_speakers(self, job_id: str) -> Optional[dict]:
        """
        Trigger automatic speaker identification for a call.

        Returns identification results, or None on failure.
        """
        if not ENABLE_CALL_INTELLIGENCE:
            return None

        try:
            response = self.session.post(
                f"{self.base_url}/calls/{job_id}/identify-speakers",
                timeout=120,  # Speaker identification can take a while
            )
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    "Speaker identification for job %s: all_matched=%s",
                    job_id, data.get("all_matched"),
                )
                return data
            else:
                logger.warning(
                    "Speaker identification failed for job %s: %s",
                    job_id, response.status_code,
                )
                return None
        except Exception as e:
            logger.warning("Error identifying speakers for job %s: %s", job_id, e)
            return None

    def transcribe_file(
        self,
        file_path: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> str:
        """
        Complete transcription workflow: upload, poll, download.

        Args:
            file_path: Path to the audio file
            progress_callback: Optional callback for progress updates

        Returns:
            The transcript text

        Raises:
            TranscriptionError: If any step fails
            BackendUnavailableError: If backend is unavailable
        """
        # Submit the job
        job_id = self.submit_transcription(file_path)

        # Poll until complete
        self.poll_until_complete(job_id, progress_callback)

        # Download transcript
        transcript = self.get_transcript_text(job_id)

        return transcript
