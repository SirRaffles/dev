"""
Unit tests for multi-modal Pydantic models.
"""
import pytest
from datetime import datetime

import sys
sys.path.insert(0, '/Users/davidmarchesseau/Development/whisper-transcription-app/backend')

from models.multimodal import (
    VisualElement,
    VisualContentType,
    AudioSegment,
    DocumentSection,
    MultiModalJob,
    MultimodalSegment,
    ProcessingProgress,
    VideoProcessingSettings,
    PDFProcessingSettings,
    PPTXProcessingSettings,
)


class TestVisualElement:
    """Tests for VisualElement model."""

    def test_create_visual_element(self):
        """Test creating a basic visual element."""
        elem = VisualElement(
            type=VisualContentType.SLIDE,
            timestamp=10.5,
            description="A presentation slide",
        )
        assert elem.type == VisualContentType.SLIDE
        assert elem.timestamp == 10.5
        assert elem.description == "A presentation slide"
        assert elem.element_id is not None
        assert len(elem.element_id) == 8

    def test_visual_element_with_page(self):
        """Test visual element with page number (PDF)."""
        elem = VisualElement(
            type=VisualContentType.CHART,
            page=5,
            text_content="Sales Q1 2024",
        )
        assert elem.page == 5
        assert elem.text_content == "Sales Q1 2024"
        assert elem.timestamp is None

    def test_visual_element_with_slide(self):
        """Test visual element with slide number (PPTX)."""
        elem = VisualElement(
            type=VisualContentType.DIAGRAM,
            slide=3,
            ocr_confidence=0.95,
        )
        assert elem.slide == 3
        assert elem.ocr_confidence == 0.95


class TestAudioSegment:
    """Tests for AudioSegment model."""

    def test_create_audio_segment(self):
        """Test creating an audio segment."""
        seg = AudioSegment(
            id=0,
            start=0.0,
            end=5.5,
            text="Hello, welcome to the presentation.",
            speaker="SPEAKER_00",
        )
        assert seg.start == 0.0
        assert seg.end == 5.5
        assert seg.text == "Hello, welcome to the presentation."
        assert seg.speaker == "SPEAKER_00"

    def test_audio_segment_with_words(self):
        """Test audio segment with word timestamps."""
        seg = AudioSegment(
            id=1,
            start=5.5,
            end=10.0,
            text="This is a test.",
            words=[
                {"word": "This", "start": 5.5, "end": 5.8},
                {"word": "is", "start": 5.8, "end": 6.0},
                {"word": "a", "start": 6.0, "end": 6.1},
                {"word": "test", "start": 6.1, "end": 6.5},
            ],
        )
        assert len(seg.words) == 4
        assert seg.words[0]["word"] == "This"

    def test_audio_segment_visual_refs(self):
        """Test audio segment with visual references."""
        seg = AudioSegment(
            id=2,
            start=10.0,
            end=15.0,
            text="As you can see on the slide...",
            visual_refs=["abc123", "def456"],
        )
        assert len(seg.visual_refs) == 2
        assert "abc123" in seg.visual_refs


class TestDocumentSection:
    """Tests for DocumentSection model."""

    def test_create_heading_section(self):
        """Test creating a heading section."""
        sec = DocumentSection(
            type="heading",
            level=1,
            content="Introduction",
            page=1,
        )
        assert sec.type == "heading"
        assert sec.level == 1
        assert sec.content == "Introduction"

    def test_create_paragraph_section(self):
        """Test creating a paragraph section."""
        sec = DocumentSection(
            type="paragraph",
            level=0,
            content="This is the first paragraph of the document.",
            slide=1,
        )
        assert sec.type == "paragraph"
        assert sec.slide == 1

    def test_section_with_visual_refs(self):
        """Test section with visual references."""
        sec = DocumentSection(
            type="table",
            level=0,
            content="| A | B | C |",
            visual_refs=["table_001"],
        )
        assert sec.type == "table"
        assert len(sec.visual_refs) == 1


class TestMultiModalJob:
    """Tests for MultiModalJob model."""

    def test_create_video_job(self):
        """Test creating a video processing job."""
        job = MultiModalJob(
            source_type="video",
            source_filename="lecture.mp4",
        )
        assert job.source_type == "video"
        assert job.status == "pending"
        assert job.progress == 0
        assert job.job_id is not None

    def test_create_pdf_job(self):
        """Test creating a PDF processing job."""
        job = MultiModalJob(
            source_type="pdf",
            source_filename="report.pdf",
            page_count=10,
        )
        assert job.source_type == "pdf"
        assert job.page_count == 10

    def test_create_pptx_job(self):
        """Test creating a PPTX processing job."""
        job = MultiModalJob(
            source_type="pptx",
            source_filename="presentation.pptx",
            slide_count=25,
        )
        assert job.source_type == "pptx"
        assert job.slide_count == 25

    def test_job_with_audio_segments(self):
        """Test job with audio segments."""
        job = MultiModalJob(
            source_type="video",
            source_filename="video.mp4",
            audio_segments=[
                AudioSegment(id=0, start=0, end=5, text="Hello"),
                AudioSegment(id=1, start=5, end=10, text="World"),
            ],
        )
        assert len(job.audio_segments) == 2
        assert job.audio_segments[0].text == "Hello"

    def test_job_with_visual_elements(self):
        """Test job with visual elements."""
        job = MultiModalJob(
            source_type="video",
            source_filename="video.mp4",
            visual_elements=[
                VisualElement(type=VisualContentType.SLIDE, timestamp=0),
                VisualElement(type=VisualContentType.CODE, timestamp=30),
            ],
        )
        assert len(job.visual_elements) == 2
        assert job.visual_elements[1].type == VisualContentType.CODE

    def test_job_status_transitions(self):
        """Test job status values."""
        job = MultiModalJob(source_type="pdf", source_filename="doc.pdf")
        assert job.status == "pending"

        job.status = "processing"
        job.progress = 50
        assert job.status == "processing"

        job.status = "completed"
        job.progress = 100
        assert job.status == "completed"


class TestMultimodalSegment:
    """Tests for MultimodalSegment model."""

    def test_create_concurrent_segment(self):
        """Test creating a segment with audio and visual."""
        audio = AudioSegment(id=0, start=0, end=5, text="Look at this slide")
        visual = VisualElement(type=VisualContentType.SLIDE, timestamp=2.5)

        seg = MultimodalSegment(
            id=0,
            start=0,
            end=5,
            audio=audio,
            visual=visual,
            relationship="concurrent",
        )
        assert seg.relationship == "concurrent"
        assert seg.audio.text == "Look at this slide"
        assert seg.visual.type == VisualContentType.SLIDE

    def test_create_visual_only_segment(self):
        """Test creating a visual-only segment."""
        visual = VisualElement(type=VisualContentType.DIAGRAM, timestamp=30)

        seg = MultimodalSegment(
            id=1,
            start=30,
            end=35,
            visual=visual,
            relationship="visual_only",
        )
        assert seg.relationship == "visual_only"
        assert seg.audio is None

    def test_create_audio_only_segment(self):
        """Test creating an audio-only segment."""
        audio = AudioSegment(id=2, start=60, end=65, text="Let me explain...")

        seg = MultimodalSegment(
            id=2,
            start=60,
            end=65,
            audio=audio,
            relationship="audio_only",
        )
        assert seg.relationship == "audio_only"
        assert seg.visual is None


class TestProcessingProgress:
    """Tests for ProcessingProgress model."""

    def test_create_progress(self):
        """Test creating progress tracker."""
        progress = ProcessingProgress(
            stage="frame_extraction",
            current=50,
            total=100,
            percentage=50.0,
            message="Extracting frames...",
        )
        assert progress.stage == "frame_extraction"
        assert progress.percentage == 50.0

    def test_progress_with_eta(self):
        """Test progress with ETA."""
        progress = ProcessingProgress(
            stage="visual_analysis",
            current=10,
            total=50,
            percentage=20.0,
            eta_seconds=120.5,
            substage="frame_10",
        )
        assert progress.eta_seconds == 120.5
        assert progress.substage == "frame_10"


class TestSettings:
    """Tests for processing settings models."""

    def test_video_settings_defaults(self):
        """Test VideoProcessingSettings defaults."""
        settings = VideoProcessingSettings()
        assert settings.language == "auto"
        assert settings.enable_diarization is True
        assert settings.keyframe_interval == 30.0
        assert settings.scene_detection is True
        assert settings.model_size == "large-v3-turbo"

    def test_video_settings_custom(self):
        """Test VideoProcessingSettings with custom values."""
        settings = VideoProcessingSettings(
            language="en",
            enable_diarization=False,
            keyframe_interval=60.0,
            scene_threshold=0.5,
        )
        assert settings.language == "en"
        assert settings.enable_diarization is False
        assert settings.keyframe_interval == 60.0

    def test_pdf_settings_defaults(self):
        """Test PDFProcessingSettings defaults."""
        settings = PDFProcessingSettings()
        assert settings.extract_images is True
        assert settings.describe_charts is True
        assert settings.ocr_enabled is False

    def test_pptx_settings_defaults(self):
        """Test PPTXProcessingSettings defaults."""
        settings = PPTXProcessingSettings()
        assert settings.extract_speaker_notes is True
        assert settings.describe_slides is True
        assert settings.extract_embedded_media is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
