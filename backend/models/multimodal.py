"""
Multi-modal Pydantic models for video, PDF, and PowerPoint processing.
"""
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class VisualContentType(str, Enum):
    """Types of visual content that can be extracted."""
    SLIDE = "slide"
    CODE = "code"
    TERMINAL = "terminal"
    DIAGRAM = "diagram"
    CHART = "chart"
    TABLE = "table"
    IMAGE = "image"
    DOCUMENT = "document"
    PERSON = "person"
    KEYFRAME = "keyframe"
    MIXED = "mixed"
    MINIMAL = "minimal"


class VisualElement(BaseModel):
    """Represents an extracted visual element from video/document."""
    element_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: VisualContentType
    timestamp: Optional[float] = None  # For video (seconds)
    page: Optional[int] = None  # For PDF
    slide: Optional[int] = None  # For PPTX
    description: Optional[str] = None  # VLM-generated description
    text_content: Optional[str] = None  # OCR extracted text
    ocr_confidence: float = 0.0
    image_path: Optional[str] = None  # Path to extracted image
    bounding_box: Optional[Dict[str, float]] = None  # x, y, width, height
    is_key_frame: bool = True


class AudioSegment(BaseModel):
    """Audio transcription segment with optional visual references."""
    id: int = 0
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    confidence: float = 1.0
    words: Optional[List[Dict[str, Any]]] = None  # Word-level timestamps
    visual_refs: List[str] = Field(default_factory=list)  # element_ids


class DocumentSection(BaseModel):
    """Represents a section in a document (PDF/PPTX)."""
    section_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: Literal["heading", "paragraph", "list", "table", "note", "title"]
    level: int = 0  # Heading level
    content: str
    page: Optional[int] = None
    slide: Optional[int] = None
    visual_refs: List[str] = Field(default_factory=list)


class MultimodalSegment(BaseModel):
    """Merged audio + visual segment for timeline."""
    id: int = 0
    start: float
    end: float
    audio: Optional[AudioSegment] = None
    visual: Optional[VisualElement] = None
    relationship: Literal["concurrent", "visual_only", "audio_only"] = "concurrent"
    combined_text: Optional[str] = None  # Merged representation


class ProcessingProgress(BaseModel):
    """Track progress across processing stages."""
    stage: str
    current: int
    total: int
    substage: Optional[str] = None
    percentage: float = 0.0
    eta_seconds: Optional[float] = None
    message: str = ""


class MultiModalJob(BaseModel):
    """Unified job structure for multi-modal processing."""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_type: Literal["video", "pdf", "pptx", "audio"]
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    progress: int = 0
    progress_message: str = ""
    progress_details: Optional[ProcessingProgress] = None

    # Source metadata
    source_filename: str
    duration: Optional[float] = None  # For video/audio (seconds)
    page_count: Optional[int] = None  # For PDF
    slide_count: Optional[int] = None  # For PPTX

    # Audio content (for video/audio)
    audio_transcript: Optional[str] = None
    audio_segments: List[AudioSegment] = Field(default_factory=list)
    detected_language: Optional[str] = None
    language_probability: float = 0.0
    speakers: List[str] = Field(default_factory=list)

    # Visual content
    visual_elements: List[VisualElement] = Field(default_factory=list)
    frames_extracted: int = 0
    frames_analyzed: int = 0

    # Document structure (for PDF/PPTX)
    document_sections: List[DocumentSection] = Field(default_factory=list)
    document_markdown: Optional[str] = None  # Full markdown conversion

    # Merged timeline (for video)
    merged_timeline: List[MultimodalSegment] = Field(default_factory=list)

    # Consolidated output (combines all extracted content into a single document)
    consolidated_output: Optional[str] = None

    # Processing metadata
    models_used: List[str] = Field(default_factory=list)
    pdf_backend_used: Optional[str] = None  # Track which PDF backend was auto-selected
    processing_time_seconds: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    # Temp directory for extracted images (cleaned up on job deletion)
    image_dir: Optional[str] = None

    # Processing flags
    enable_diarization: bool = True
    enable_visual_analysis: bool = True
    enable_ocr: bool = True


class VideoProcessingSettings(BaseModel):
    """Settings for video multi-modal processing."""
    language: str = "auto"
    enable_diarization: bool = True
    num_speakers: Optional[int] = None
    enable_visual_analysis: bool = True
    keyframe_interval: float = 30.0  # Seconds between forced keyframes
    scene_detection: bool = True
    scene_threshold: float = 0.4
    describe_visuals: bool = True
    ocr_enabled: bool = True
    model_size: str = "large-v3-turbo"


class PDFProcessingSettings(BaseModel):
    """Settings for PDF processing."""
    extract_images: bool = True
    describe_charts: bool = True
    preserve_tables: bool = True
    ocr_enabled: bool = False  # For scanned PDFs


class PPTXProcessingSettings(BaseModel):
    """Settings for PowerPoint processing."""
    extract_speaker_notes: bool = True
    describe_slides: bool = True
    extract_embedded_media: bool = True
    render_slides_as_images: bool = True


class ModelStatus(BaseModel):
    """Status of a loaded model."""
    name: str
    loaded: bool = False
    memory_mb: int = 0
    device: str = "cpu"
    last_used: Optional[datetime] = None


class ModelsStatusResponse(BaseModel):
    """Response for /models/status endpoint."""
    whisper: ModelStatus
    vision: ModelStatus
    diarization: ModelStatus
    total_memory_used_mb: int = 0
    total_memory_available_mb: int = 0
