"""
PowerPoint presentation processor.

Extracts slides, speaker notes, images, and embedded media from PPTX files.
"""
import logging
from pathlib import Path
from typing import Optional, Callable, List
import tempfile

from processors.base import BaseProcessor
from models.multimodal import (
    MultiModalJob,
    ProcessingProgress,
    VisualElement,
    VisualContentType,
    DocumentSection,
    PPTXProcessingSettings,
)
from services.document_service import DocumentService, get_document_service
from services.vision_service import VisionService, get_vision_service
from services.model_manager import get_model_manager, ModelName

logger = logging.getLogger(__name__)


class PPTXProcessor(BaseProcessor):
    """
    Processor for PowerPoint presentations.

    Pipeline:
    1. Extract slide content with MarkItDown
    2. Extract speaker notes
    3. Render slides as images (optional)
    4. Extract embedded media
    5. Describe slides with VLM
    """

    def __init__(
        self,
        job: MultiModalJob,
        settings: Optional[PPTXProcessingSettings] = None,
        document_service: Optional[DocumentService] = None,
        vision_service: Optional[VisionService] = None,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None,
    ):
        super().__init__(job, progress_callback)
        self.settings = settings or PPTXProcessingSettings()
        self.document_service = document_service or get_document_service()
        self.vision_service = vision_service or get_vision_service()
        self.model_manager = get_model_manager()
        self._temp_dir: Optional[Path] = None
        self._vision_loaded = False

    def get_supported_extensions(self) -> list[str]:
        return [".pptx", ".PPTX", ".ppt", ".PPT"]

    async def process(self) -> MultiModalJob:
        """Process a PowerPoint file."""
        file_path = Path(self.job.source_filename)

        # Create temp directory for extracted content
        # Note: Don't add to temp_files - this is cleaned up on job deletion
        self._temp_dir = Path(tempfile.mkdtemp(prefix="pptx_process_"))
        self.job.image_dir = str(self._temp_dir)

        total_steps = 5
        current_step = 0

        # Step 1: Get slide count and basic info
        self.update_progress(
            "initialization",
            current_step,
            total_steps,
            message="Opening presentation...",
        )

        try:
            slide_count, slides_data = self._get_presentation_info(file_path)
            self.job.slide_count = slide_count
            current_step += 1
        except Exception as e:
            logger.error(f"Failed to open presentation: {e}")
            self.fail_processing(f"Failed to open presentation: {e}")
            return self.job

        # Step 2: Extract text with MarkItDown
        self.update_progress(
            "text_extraction",
            current_step,
            total_steps,
            message="Extracting slide content...",
        )

        try:
            result = self.document_service.convert_with_images(
                file_path,
                self._temp_dir,
                describe_images=False,
            )
            self.job.document_markdown = result.markdown
            current_step += 1
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            # Continue with python-pptx fallback
            pass

        # Step 3: Extract speaker notes
        if self.settings.extract_speaker_notes:
            self.update_progress(
                "notes_extraction",
                current_step,
                total_steps,
                message="Extracting speaker notes...",
            )

            notes = self._extract_speaker_notes(file_path)
            for slide_num, note_text in notes.items():
                self.job.document_sections.append(DocumentSection(
                    type="note",
                    level=0,
                    content=note_text,
                    slide=slide_num,
                ))

            current_step += 1

        # Step 4: Render slides as images
        if self.settings.render_slides_as_images:
            self.update_progress(
                "slide_rendering",
                current_step,
                total_steps,
                message="Rendering slides as images...",
            )

            slide_images = self._render_slides_as_images(file_path, self._temp_dir)
            self.job.frames_extracted = len(slide_images)

            for img_path, slide_num in slide_images:
                element = VisualElement(
                    type=VisualContentType.SLIDE,
                    slide=slide_num,
                    image_path=str(img_path),
                )
                self.job.visual_elements.append(element)

            current_step += 1

        # Step 5: Describe slides with VLM (GLM-4.6V-Flash)
        if self.settings.describe_slides and self.job.visual_elements:
            self.update_progress(
                "slide_analysis",
                current_step,
                total_steps,
                message="Loading vision model...",
            )

            # Load GLM-4.6V-Flash vision model if not already loaded
            if not self._vision_loaded:
                try:
                    await self.model_manager.load_vision()
                    vision_model = self.model_manager.get_model(ModelName.VISION)
                    if vision_model:
                        self.vision_service.set_model(vision_model)
                        self._vision_loaded = True
                        model_name = vision_model.get("model_name", "qwen2.5-vl")
                        self.job.models_used.append(model_name)
                        logger.info(f"Vision model loaded: {model_name}")
                    else:
                        logger.warning("Vision model not available, using Tesseract fallback")
                except Exception as e:
                    logger.warning(f"Failed to load vision model: {e}. Using Tesseract fallback.")

            self.update_progress(
                "slide_analysis",
                current_step,
                total_steps,
                message="Analyzing slides...",
            )

            analyzed = 0
            for element in self.job.visual_elements:
                if element.image_path and element.type == VisualContentType.SLIDE:
                    try:
                        description = await self.vision_service.describe(
                            Path(element.image_path),
                            content_type=None,  # Will use slide-specific prompt
                        )
                        element.description = description

                        # Also extract any text via OCR
                        text = await self.vision_service.extract_text(
                            Path(element.image_path)
                        )
                        element.text_content = text

                        analyzed += 1
                        self.update_progress(
                            "slide_analysis",
                            current_step,
                            total_steps,
                            substage=f"slide_{element.slide}",
                            message=f"Analyzed slide {element.slide}/{self.job.slide_count}",
                        )

                    except Exception as e:
                        logger.warning(f"Failed to analyze slide {element.slide}: {e}")

            self.job.frames_analyzed = analyzed
            current_step += 1

        # Extract embedded audio if requested
        if self.settings.extract_embedded_media:
            audio_files = self._extract_embedded_audio(file_path, self._temp_dir)
            if audio_files:
                # Note: Audio transcription would be handled by a separate process
                logger.info(f"Found {len(audio_files)} embedded audio files")

        # Build document sections from slides
        self._build_slide_sections(file_path)

        # Mark models used (glm-4.6v-flash already added above if loaded)
        self.job.models_used.append("markitdown")
        if self.settings.describe_slides and not self._vision_loaded:
            self.job.models_used.append("tesseract-ocr")  # Fallback was used

        return self.job

    def _get_presentation_info(self, file_path: Path) -> tuple[int, List[dict]]:
        """Get basic presentation info using python-pptx."""
        try:
            from pptx import Presentation

            prs = Presentation(str(file_path))
            slides_data = []

            for i, slide in enumerate(prs.slides, 1):
                slide_info = {
                    "number": i,
                    "layout": slide.slide_layout.name if slide.slide_layout else None,
                    "shapes_count": len(slide.shapes),
                }
                slides_data.append(slide_info)

            return len(prs.slides), slides_data

        except ImportError:
            logger.warning("python-pptx not installed")
            return 0, []
        except Exception as e:
            logger.error(f"Failed to get presentation info: {e}")
            return 0, []

    def _extract_speaker_notes(self, file_path: Path) -> dict[int, str]:
        """Extract speaker notes from all slides."""
        notes = {}
        try:
            from pptx import Presentation

            prs = Presentation(str(file_path))

            for i, slide in enumerate(prs.slides, 1):
                if slide.has_notes_slide:
                    notes_slide = slide.notes_slide
                    notes_text = notes_slide.notes_text_frame.text.strip()
                    if notes_text:
                        notes[i] = notes_text

        except ImportError:
            logger.warning("python-pptx not installed, skipping notes extraction")
        except Exception as e:
            logger.error(f"Failed to extract speaker notes: {e}")

        return notes

    def _render_slides_as_images(
        self, file_path: Path, output_dir: Path
    ) -> List[tuple[Path, int]]:
        """
        Render slides as images.

        Note: python-pptx doesn't support direct slide rendering.
        We use extracted shapes/images as a fallback or rely on
        external tools like LibreOffice for full rendering.
        """
        slide_images = []

        try:
            from pptx import Presentation
            from pptx.util import Inches
            from PIL import Image
            import io

            prs = Presentation(str(file_path))
            slide_width = prs.slide_width.inches
            slide_height = prs.slide_height.inches

            for i, slide in enumerate(prs.slides, 1):
                # Create a simple representation using shape images
                # This is a fallback - for full rendering, use LibreOffice
                shape_images = []

                for shape in slide.shapes:
                    if hasattr(shape, "image"):
                        try:
                            image_bytes = shape.image.blob
                            img = Image.open(io.BytesIO(image_bytes))
                            shape_images.append(img)
                        except Exception:
                            pass

                # If we got images, save the first one as slide representation
                if shape_images:
                    output_path = output_dir / f"slide_{i:03d}.png"
                    shape_images[0].save(output_path)
                    slide_images.append((output_path, i))
                else:
                    # Try to create a blank placeholder with slide info
                    output_path = self._create_slide_placeholder(
                        output_dir, i, slide_width, slide_height
                    )
                    if output_path:
                        slide_images.append((output_path, i))

        except ImportError:
            logger.warning("Required packages not available for slide rendering")
        except Exception as e:
            logger.error(f"Failed to render slides: {e}")

        return slide_images

    def _create_slide_placeholder(
        self,
        output_dir: Path,
        slide_num: int,
        width: float,
        height: float,
    ) -> Optional[Path]:
        """Create a placeholder image for a slide."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create image with presentation aspect ratio
            img_width = 1280
            img_height = int(img_width * height / width) if width > 0 else 720

            img = Image.new("RGB", (img_width, img_height), color=(240, 240, 240))
            draw = ImageDraw.Draw(img)

            # Add slide number text
            text = f"Slide {slide_num}"
            font = ImageFont.load_default(size=48)

            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (img_width - text_width) // 2
            y = (img_height - text_height) // 2

            draw.text((x, y), text, fill=(100, 100, 100), font=font)

            output_path = output_dir / f"slide_{slide_num:03d}.png"
            img.save(output_path)
            return output_path

        except Exception as e:
            logger.warning(f"Failed to create placeholder: {e}")
            return None

    def _extract_embedded_audio(
        self, file_path: Path, output_dir: Path
    ) -> List[Path]:
        """Extract embedded audio files from presentation."""
        audio_files = []
        try:
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            prs = Presentation(str(file_path))

            for slide_num, slide in enumerate(prs.slides, 1):
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
                        try:
                            # This is a simplified approach
                            # Full media extraction requires accessing the package
                            pass
                        except Exception:
                            pass

            # Alternative: Extract from package directly
            import zipfile
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                for name in zip_ref.namelist():
                    if name.startswith("ppt/media/") and (
                        name.endswith(".mp3")
                        or name.endswith(".wav")
                        or name.endswith(".m4a")
                    ):
                        output_path = output_dir / Path(name).name
                        with open(output_path, "wb") as f:
                            f.write(zip_ref.read(name))
                        audio_files.append(output_path)

        except Exception as e:
            logger.error(f"Failed to extract embedded audio: {e}")

        return audio_files

    def _build_slide_sections(self, file_path: Path) -> None:
        """Build document sections from slide content."""
        try:
            from pptx import Presentation

            prs = Presentation(str(file_path))

            for slide_num, slide in enumerate(prs.slides, 1):
                # Extract title
                if slide.shapes.title:
                    title_text = slide.shapes.title.text.strip()
                    if title_text:
                        self.job.document_sections.append(DocumentSection(
                            type="title",
                            level=1,
                            content=title_text,
                            slide=slide_num,
                        ))

                # Extract text from other shapes
                for shape in slide.shapes:
                    if shape.has_text_frame and shape != slide.shapes.title:
                        for paragraph in shape.text_frame.paragraphs:
                            text = paragraph.text.strip()
                            if text:
                                # Determine type based on bullet level
                                if paragraph.level > 0:
                                    section_type = "list"
                                else:
                                    section_type = "paragraph"

                                self.job.document_sections.append(DocumentSection(
                                    type=section_type,
                                    level=paragraph.level,
                                    content=text,
                                    slide=slide_num,
                                ))

        except ImportError:
            logger.warning("python-pptx not installed, skipping section building")
        except Exception as e:
            logger.error(f"Failed to build slide sections: {e}")
