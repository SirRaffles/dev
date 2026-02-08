"""
Unit tests for multi-modal processors.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import asyncio

import sys
sys.path.insert(0, '/Users/davidmarchesseau/Development/whisper-transcription-app/backend')

from models.multimodal import (
    MultiModalJob,
    ProcessingProgress,
    VisualElement,
    VisualContentType,
    PDFProcessingSettings,
    PPTXProcessingSettings,
)
from processors.base import BaseProcessor
from processors.keyframe_extractor import (
    KeyframeExtractor,
    ExtractionConfig,
    ExtractedFrame,
    VideoType,
)
from processors.pdf_processor import PDFProcessor
from processors.pptx_processor import PPTXProcessor


class ConcreteProcessor(BaseProcessor):
    """Concrete implementation for testing BaseProcessor."""

    def get_supported_extensions(self) -> list[str]:
        return [".wav", ".WAV", ".mp3", ".MP3"]

    async def process(self) -> MultiModalJob:
        self.update_progress("testing", 1, 2, message="Test step 1")
        self.update_progress("testing", 2, 2, message="Test step 2")
        return self.job


class TestBaseProcessor:
    """Tests for BaseProcessor abstract class."""

    def test_processor_initialization(self):
        """Test BaseProcessor initializes correctly."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)
        assert processor.job is job
        assert processor.progress_callback is None
        assert processor._temp_files == []

    def test_processor_with_callback(self):
        """Test processor with progress callback."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        callback = Mock()
        processor = ConcreteProcessor(job, progress_callback=callback)
        assert processor.progress_callback is callback

    def test_get_supported_extensions(self):
        """Test getting supported extensions."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)
        assert ".wav" in processor.get_supported_extensions()
        assert ".WAV" in processor.get_supported_extensions()

    def test_update_progress(self):
        """Test progress update."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        callback = Mock()
        processor = ConcreteProcessor(job, progress_callback=callback)

        processor.update_progress("extraction", 50, 100, message="Halfway done")

        assert job.progress == 50
        assert "Halfway" in job.progress_message
        callback.assert_called_once()
        progress_arg = callback.call_args[0][0]
        assert isinstance(progress_arg, ProcessingProgress)
        assert progress_arg.stage == "extraction"
        assert progress_arg.percentage == 50.0

    def test_start_processing(self):
        """Test marking processing as started."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)
        processor.start_processing()

        assert job.status == "processing"
        assert job.progress == 0
        assert processor._start_time is not None

    def test_complete_processing(self):
        """Test marking processing as complete."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)
        processor.start_processing()
        processor.complete_processing()

        assert job.status == "completed"
        assert job.progress == 100
        assert job.processing_time_seconds > 0
        assert job.completed_at is not None

    def test_fail_processing(self):
        """Test marking processing as failed."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)
        processor.start_processing()
        processor.fail_processing("Test error message")

        assert job.status == "failed"
        assert job.error == "Test error message"
        assert "Failed" in job.progress_message

    def test_validate_input_file_not_found(self):
        """Test validation fails for nonexistent file."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)
        result = processor.validate_input(Path("/nonexistent/file.wav"))

        assert result is False
        assert job.status == "failed"
        assert "not found" in job.error.lower()

    def test_validate_input_unsupported_type(self):
        """Test validation fails for unsupported file type."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = processor.validate_input(temp_path)
            assert result is False
            assert job.status == "failed"
            assert "Unsupported" in job.error
        finally:
            temp_path.unlink()

    def test_validate_input_success(self):
        """Test validation succeeds for supported file."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = Path(f.name)

        try:
            result = processor.validate_input(temp_path)
            assert result is True
        finally:
            temp_path.unlink()

    def test_add_temp_file(self):
        """Test registering temp files."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)

        path1 = Path("/tmp/test1.txt")
        path2 = Path("/tmp/test2.txt")
        processor.add_temp_file(path1)
        processor.add_temp_file(path2)

        assert len(processor._temp_files) == 2
        assert path1 in processor._temp_files
        assert path2 in processor._temp_files

    def test_cleanup_temp_files(self):
        """Test cleanup of temp files."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)

        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        processor.add_temp_file(temp_path)
        assert temp_path.exists()

        processor.cleanup()
        assert not temp_path.exists()
        assert len(processor._temp_files) == 0


class TestExtractionConfig:
    """Tests for ExtractionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ExtractionConfig()
        assert config.min_interval == 2.0
        assert config.max_interval == 30.0
        assert config.scene_threshold == 27.0
        assert config.force_start_end is True
        assert config.output_format == "jpg"
        assert config.output_quality == 85

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ExtractionConfig(
            min_interval=5.0,
            max_interval=60.0,
            scene_threshold=40.0,
            max_frames=100,
        )
        assert config.min_interval == 5.0
        assert config.max_interval == 60.0
        assert config.scene_threshold == 40.0
        assert config.max_frames == 100


class TestExtractedFrame:
    """Tests for ExtractedFrame dataclass."""

    def test_create_frame(self):
        """Test creating an extracted frame."""
        frame = ExtractedFrame(
            timestamp=10.5,
            frame_path=Path("/tmp/frame_001.jpg"),
            extraction_reason="scene_change",
            frame_number=1,
        )
        assert frame.timestamp == 10.5
        assert frame.extraction_reason == "scene_change"
        assert frame.is_key_frame is True


class TestVideoType:
    """Tests for VideoType enum."""

    def test_video_types(self):
        """Test VideoType enum values."""
        assert VideoType.PRESENTATION.value == "presentation"
        assert VideoType.SCREENCAST.value == "screencast"
        assert VideoType.TALKING_HEAD.value == "talking_head"
        assert VideoType.DOCUMENTARY.value == "documentary"
        assert VideoType.LECTURE.value == "lecture"
        assert VideoType.UNKNOWN.value == "unknown"


class TestKeyframeExtractor:
    """Tests for KeyframeExtractor."""

    def test_extractor_initialization(self):
        """Test KeyframeExtractor initializes correctly."""
        extractor = KeyframeExtractor()
        assert extractor.config is not None
        assert extractor._video_duration == 0
        assert extractor._video_fps == 30

    def test_extractor_with_custom_config(self):
        """Test extractor with custom config."""
        config = ExtractionConfig(min_interval=10.0)
        extractor = KeyframeExtractor(config=config)
        assert extractor.config.min_interval == 10.0

    def test_type_configs_exist(self):
        """Test type-specific configs are defined."""
        assert VideoType.PRESENTATION in KeyframeExtractor.TYPE_CONFIGS
        assert VideoType.SCREENCAST in KeyframeExtractor.TYPE_CONFIGS
        assert VideoType.TALKING_HEAD in KeyframeExtractor.TYPE_CONFIGS
        assert VideoType.DOCUMENTARY in KeyframeExtractor.TYPE_CONFIGS
        assert VideoType.LECTURE in KeyframeExtractor.TYPE_CONFIGS
        assert VideoType.UNKNOWN in KeyframeExtractor.TYPE_CONFIGS

    def test_presentation_config(self):
        """Test presentation type config."""
        config = KeyframeExtractor.TYPE_CONFIGS[VideoType.PRESENTATION]
        assert config.min_interval == 5.0
        assert config.max_interval == 60.0

    def test_talking_head_config(self):
        """Test talking head type config."""
        config = KeyframeExtractor.TYPE_CONFIGS[VideoType.TALKING_HEAD]
        assert config.min_interval == 30.0
        assert config.max_interval == 120.0

    def test_generate_interval_samples_empty(self):
        """Test interval generation with no existing timestamps."""
        extractor = KeyframeExtractor()
        extractor.config.max_interval = 30.0
        extractor.config.force_start_end = True

        samples = extractor.generate_interval_samples(90.0, [])

        # Should have start (0) and end, plus samples to fill 90s
        assert 0.0 in samples
        assert len(samples) >= 2

    def test_generate_interval_samples_with_existing(self):
        """Test interval generation fills gaps."""
        extractor = KeyframeExtractor()
        extractor.config.max_interval = 30.0
        extractor.config.min_interval = 2.0

        # 60s video with scene at 30s - no gaps over 30s
        samples = extractor.generate_interval_samples(60.0, [30.0])

        # Should add start (0) and maybe end
        assert 0.0 in samples

    def test_generate_interval_samples_large_gap(self):
        """Test interval generation handles large gaps."""
        extractor = KeyframeExtractor()
        extractor.config.max_interval = 20.0

        # Scene at start and 100s - 100s gap
        samples = extractor.generate_interval_samples(100.0, [0.0, 100.0])

        # Should fill the gap with multiple samples
        assert len(samples) >= 3

    def test_extract_nonexistent_video(self):
        """Test extracting from nonexistent video raises error."""
        extractor = KeyframeExtractor()
        with pytest.raises(FileNotFoundError):
            extractor.extract(Path("/nonexistent/video.mp4"))


class TestPDFProcessor:
    """Tests for PDFProcessor."""

    def test_processor_initialization(self):
        """Test PDFProcessor initializes correctly."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        assert processor.job is job
        assert processor.settings is not None
        assert processor.document_service is not None
        assert processor.vision_service is not None

    def test_processor_with_custom_settings(self):
        """Test processor with custom settings."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        settings = PDFProcessingSettings(
            extract_images=False,
            describe_charts=False,
        )
        processor = PDFProcessor(job, settings=settings)
        assert processor.settings.extract_images is False
        assert processor.settings.describe_charts is False

    def test_supported_extensions(self):
        """Test PDF supported extensions."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        extensions = processor.get_supported_extensions()
        assert ".pdf" in extensions
        assert ".PDF" in extensions

    def test_parse_markdown_structure_empty(self):
        """Test parsing empty markdown."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        sections = processor._parse_markdown_structure("")
        assert sections == []

    def test_parse_markdown_structure_heading(self):
        """Test parsing markdown headings."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        markdown = "# Title\n## Section 1\n### Subsection"
        sections = processor._parse_markdown_structure(markdown)

        assert len(sections) == 3
        assert sections[0].type == "title"
        assert sections[0].level == 1
        assert sections[1].type == "heading"
        assert sections[1].level == 2

    def test_parse_markdown_structure_lists(self):
        """Test parsing markdown lists."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        markdown = "- Item 1\n- Item 2\n* Item 3"
        sections = processor._parse_markdown_structure(markdown)

        assert len(sections) == 3
        for section in sections:
            assert section.type == "list"

    def test_parse_markdown_structure_paragraphs(self):
        """Test parsing markdown paragraphs."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        markdown = "This is a paragraph.\n\nThis is another paragraph."
        sections = processor._parse_markdown_structure(markdown)

        assert len(sections) == 2
        for section in sections:
            assert section.type == "paragraph"

    def test_parse_markdown_structure_tables(self):
        """Test parsing markdown tables."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)
        markdown = "| A | B |\n|---|---|\n| 1 | 2 |"
        sections = processor._parse_markdown_structure(markdown)

        # Tables should be combined
        table_sections = [s for s in sections if s.type == "table"]
        assert len(table_sections) >= 1

    def test_map_content_type(self):
        """Test content type mapping."""
        from services.vision_service import ContentType

        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        processor = PDFProcessor(job)

        assert processor._map_content_type(ContentType.SLIDE) == VisualContentType.SLIDE
        assert processor._map_content_type(ContentType.CHART) == VisualContentType.CHART
        assert processor._map_content_type(ContentType.CODE) == VisualContentType.CODE


class TestPPTXProcessor:
    """Tests for PPTXProcessor."""

    def test_processor_initialization(self):
        """Test PPTXProcessor initializes correctly."""
        job = MultiModalJob(source_type="pptx", source_filename="slides.pptx")
        processor = PPTXProcessor(job)
        assert processor.job is job
        assert processor.settings is not None
        assert processor.document_service is not None
        assert processor.vision_service is not None

    def test_processor_with_custom_settings(self):
        """Test processor with custom settings."""
        job = MultiModalJob(source_type="pptx", source_filename="slides.pptx")
        settings = PPTXProcessingSettings(
            extract_speaker_notes=False,
            describe_slides=False,
        )
        processor = PPTXProcessor(job, settings=settings)
        assert processor.settings.extract_speaker_notes is False
        assert processor.settings.describe_slides is False

    def test_supported_extensions(self):
        """Test PPTX supported extensions."""
        job = MultiModalJob(source_type="pptx", source_filename="slides.pptx")
        processor = PPTXProcessor(job)
        extensions = processor.get_supported_extensions()
        assert ".pptx" in extensions
        assert ".PPTX" in extensions
        assert ".ppt" in extensions
        assert ".PPT" in extensions

    def test_default_settings(self):
        """Test default PPTX settings."""
        settings = PPTXProcessingSettings()
        assert settings.extract_speaker_notes is True
        assert settings.describe_slides is True
        assert settings.extract_embedded_media is True

    def test_create_slide_placeholder(self):
        """Test creating slide placeholder image."""
        job = MultiModalJob(source_type="pptx", source_filename="slides.pptx")
        processor = PPTXProcessor(job)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = processor._create_slide_placeholder(
                output_dir, slide_num=1, width=10, height=7.5
            )

            if result:  # May fail if PIL not configured correctly
                assert result.exists()
                assert result.suffix == ".png"


class TestProcessorIntegration:
    """Integration tests for processors."""

    def test_run_processor_with_callback(self):
        """Test running processor with progress callback."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        callback = Mock()
        processor = ConcreteProcessor(job, progress_callback=callback)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(processor.run(temp_path))

            assert result.status == "completed"
            assert callback.call_count >= 2  # Two progress updates in process()
        finally:
            temp_path.unlink(missing_ok=True)

    def test_run_processor_handles_errors(self):
        """Test processor handles errors gracefully."""
        job = MultiModalJob(source_type="audio", source_filename="test.wav")
        processor = ConcreteProcessor(job)

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(processor.run(Path("/nonexistent.wav")))

        assert result.status == "failed"
        assert result.error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
