"""
Base processor abstract class for multi-modal processing.
"""
from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from pathlib import Path
import logging
import time

from models.multimodal import (
    MultiModalJob,
    ProcessingProgress,
)

logger = logging.getLogger(__name__)


class BaseProcessor(ABC):
    """
    Abstract base class for all multi-modal processors.

    Provides common functionality:
    - Progress tracking
    - Job state management
    - Error handling
    - Cleanup
    """

    def __init__(
        self,
        job: MultiModalJob,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None,
    ):
        self.job = job
        self.progress_callback = progress_callback
        self._start_time: Optional[float] = None
        self._temp_files: list[Path] = []

    @abstractmethod
    async def process(self) -> MultiModalJob:
        """
        Main processing method to be implemented by subclasses.

        Returns:
            Updated MultiModalJob with processing results.
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf', '.PDF'])."""
        pass

    def update_progress(
        self,
        stage: str,
        current: int,
        total: int,
        substage: Optional[str] = None,
        message: str = "",
    ) -> None:
        """Update job progress and notify callback."""
        # Calculate overall percentage
        percentage = (current / total * 100) if total > 0 else 0

        # Estimate ETA if we have timing data
        eta_seconds = None
        if self._start_time and current > 0:
            elapsed = time.time() - self._start_time
            rate = current / elapsed
            remaining = total - current
            if rate > 0:
                eta_seconds = remaining / rate

        progress = ProcessingProgress(
            stage=stage,
            current=current,
            total=total,
            substage=substage,
            percentage=percentage,
            eta_seconds=eta_seconds,
            message=message,
        )

        self.job.progress_details = progress
        self.job.progress = int(percentage)
        self.job.progress_message = message or f"{stage}: {current}/{total}"

        if self.progress_callback:
            self.progress_callback(progress)

        logger.debug(f"Progress: {stage} - {current}/{total} ({percentage:.1f}%)")

    def start_processing(self) -> None:
        """Mark the start of processing."""
        self._start_time = time.time()
        self.job.status = "processing"
        self.job.progress = 0
        logger.info(f"Started processing job {self.job.job_id}: {self.job.source_filename}")

    def complete_processing(self) -> None:
        """Mark processing as complete."""
        if self._start_time:
            self.job.processing_time_seconds = time.time() - self._start_time
        self.job.status = "completed"
        self.job.progress = 100
        self.job.progress_message = "Processing complete"
        from datetime import datetime
        self.job.completed_at = datetime.now()
        logger.info(
            f"Completed job {self.job.job_id} in {self.job.processing_time_seconds:.1f}s"
        )

    def fail_processing(self, error: str) -> None:
        """Mark processing as failed."""
        if self._start_time:
            self.job.processing_time_seconds = time.time() - self._start_time
        self.job.status = "failed"
        self.job.error = error
        self.job.progress_message = f"Failed: {error}"
        logger.error(f"Failed job {self.job.job_id}: {error}")

    def add_temp_file(self, path: Path) -> None:
        """Register a temporary file for cleanup."""
        self._temp_files.append(path)

    def cleanup(self) -> None:
        """Clean up temporary files."""
        for path in self._temp_files:
            try:
                if path.exists():
                    if path.is_dir():
                        import shutil
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    logger.debug(f"Cleaned up: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up {path}: {e}")
        self._temp_files.clear()

    def validate_input(self, file_path: Path) -> bool:
        """Validate that input file exists and is supported."""
        if not file_path.exists():
            self.fail_processing(f"File not found: {file_path}")
            return False

        if file_path.suffix.lower() not in [
            ext.lower() for ext in self.get_supported_extensions()
        ]:
            self.fail_processing(
                f"Unsupported file type: {file_path.suffix}. "
                f"Supported: {self.get_supported_extensions()}"
            )
            return False

        return True

    def generate_consolidated_output(self) -> str:
        """
        Generate a consolidated output document combining all extracted content.

        Combines:
        - Document text (from Docling/MarkItDown/PyMuPDF4LLM)
        - Visual descriptions (from the configured MLX-VLM model)
        - OCR text (from Tesseract)
        - Transcription (for audio/video)
        - Speaker notes (for PPTX)
        - Tables

        Returns:
            Consolidated markdown document
        """
        sections = []

        # Header with metadata
        sections.append(f"# {Path(self.job.source_filename).stem}")
        sections.append("")
        sections.append(f"**Source:** {self.job.source_filename}")
        sections.append(f"**Type:** {self.job.source_type}")
        if self.job.page_count:
            sections.append(f"**Pages:** {self.job.page_count}")
        if self.job.slide_count:
            sections.append(f"**Slides:** {self.job.slide_count}")
        if self.job.duration:
            sections.append(f"**Duration:** {self.job.duration:.1f}s")
        sections.append(f"**Models used:** {', '.join(self.job.models_used)}")
        sections.append("")
        sections.append("---")
        sections.append("")

        # Main document content (from text extraction)
        if self.job.document_markdown:
            sections.append("## Document Content")
            sections.append("")
            sections.append(self.job.document_markdown)
            sections.append("")

        # Audio transcript (for video/audio)
        if self.job.audio_transcript:
            sections.append("## Transcript")
            sections.append("")
            if self.job.detected_language:
                sections.append(f"*Language: {self.job.detected_language}*")
                sections.append("")
            sections.append(self.job.audio_transcript)
            sections.append("")

        # Transcript segments with speakers
        if self.job.audio_segments:
            sections.append("## Transcript with Timestamps")
            sections.append("")
            for seg in self.job.audio_segments:
                speaker = f"**{seg.speaker}:** " if seg.speaker else ""
                time_str = f"[{seg.start:.1f}s - {seg.end:.1f}s]"
                sections.append(f"{time_str} {speaker}{seg.text}")
            sections.append("")

        # Visual elements with descriptions
        visual_with_descriptions = [
            el for el in self.job.visual_elements if el.description
        ]
        if visual_with_descriptions:
            sections.append("## Visual Content Analysis")
            sections.append("")
            for el in visual_with_descriptions:
                # Header based on type and location
                location = ""
                if el.page:
                    location = f"Page {el.page}"
                elif el.slide:
                    location = f"Slide {el.slide}"
                elif el.timestamp is not None:
                    location = f"Time {el.timestamp:.1f}s"

                sections.append(f"### {el.type.value.title()} ({location})")
                sections.append("")
                sections.append(el.description)
                if el.text_content:
                    sections.append("")
                    sections.append("**Extracted text:**")
                    sections.append(f"```\n{el.text_content}\n```")
                sections.append("")

        # Speaker notes (for PPTX)
        notes_sections = [
            s for s in self.job.document_sections if s.type == "note"
        ]
        if notes_sections:
            sections.append("## Speaker Notes")
            sections.append("")
            for note in notes_sections:
                sections.append(f"**Slide {note.slide}:**")
                sections.append(note.content)
                sections.append("")

        # Processing metadata footer
        sections.append("---")
        sections.append("")
        sections.append("*Processing metadata:*")
        if self.job.pdf_backend_used:
            sections.append(f"- PDF backend: {self.job.pdf_backend_used}")
        sections.append(f"- Processing time: {self.job.processing_time_seconds:.1f}s")
        sections.append(f"- Visual elements analyzed: {self.job.frames_analyzed}")

        return "\n".join(sections)

    async def run(self, file_path: Path) -> MultiModalJob:
        """
        Main entry point for processing.
        Handles setup, validation, processing, and cleanup.
        """
        try:
            self.start_processing()

            if not self.validate_input(file_path):
                return self.job

            await self.process()

            if self.job.status != "failed":
                # Generate consolidated output
                self.job.consolidated_output = self.generate_consolidated_output()
                self.complete_processing()

        except Exception as e:
            logger.exception(f"Processing error: {e}")
            self.fail_processing(str(e))

        finally:
            self.cleanup()

        return self.job
