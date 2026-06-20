"""
PDF document processor.

Extracts text, images, tables, and structure from PDF files
using MarkItDown and PyMuPDF.

For scanned PDFs (no extractable text), renders pages as images
and uses Tesseract OCR to extract text.
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
    PDFProcessingSettings,
)
from services.document_service import (
    DocumentService,
    get_document_service,
    PDFBackend,
    auto_select_pdf_backend,
)
from services.vision_service import VisionService, get_vision_service
from services.model_manager import get_model_manager, ModelName

logger = logging.getLogger(__name__)


class PDFProcessor(BaseProcessor):
    """
    Processor for PDF documents.

    Pipeline:
    1. Extract text/structure with MarkItDown
    2. Extract images with PyMuPDF
    3. Optionally describe images/charts with VLM
    4. Generate structured output
    """

    def __init__(
        self,
        job: MultiModalJob,
        settings: Optional[PDFProcessingSettings] = None,
        document_service: Optional[DocumentService] = None,
        vision_service: Optional[VisionService] = None,
        progress_callback: Optional[Callable[[ProcessingProgress], None]] = None,
        pdf_backend: Optional[PDFBackend] = None,  # None = auto-detect
    ):
        super().__init__(job, progress_callback)
        self.settings = settings or PDFProcessingSettings()
        self.document_service = document_service or get_document_service()
        self.vision_service = vision_service or get_vision_service()
        self.model_manager = get_model_manager()
        self._requested_backend = pdf_backend  # Store for later auto-detection
        self._temp_dir: Optional[Path] = None
        self._vision_loaded = False

    def get_supported_extensions(self) -> list[str]:
        return [".pdf", ".PDF"]

    async def process(self) -> MultiModalJob:
        """Process a PDF file."""
        file_path = Path(self.job.source_filename)

        # Create temp directory for extracted images
        # Note: Don't add to temp_files - this is cleaned up on job deletion
        self._temp_dir = Path(tempfile.mkdtemp(prefix="pdf_process_"))
        self.job.image_dir = str(self._temp_dir)

        total_steps = 4  # text, images, describe, structure
        current_step = 0

        # Step 1: Extract text with MarkItDown
        self.update_progress(
            "text_extraction",
            current_step,
            total_steps,
            message="Extracting text from PDF...",
        )

        try:
            # Auto-detect best backend if not specified
            if self._requested_backend is None:
                self._selected_backend = auto_select_pdf_backend(file_path)
            else:
                self._selected_backend = self._requested_backend

            backend_name = self._selected_backend.value
            logger.info(f"Using PDF backend: {backend_name}")

            if self.settings.extract_images:
                # For image extraction, still use PyMuPDF-based method
                result = self.document_service.convert_with_images(
                    file_path,
                    self._temp_dir,
                    describe_images=False,  # We'll do this separately
                )
                # But use the selected backend for better text extraction
                try:
                    backend_result = self.document_service.convert_pdf(
                        file_path, backend=self._selected_backend
                    )
                    result.markdown = backend_result.markdown
                    result.tables = backend_result.tables
                except Exception as e:
                    logger.warning(f"{backend_name} extraction failed, using MarkItDown: {e}")
            else:
                result = self.document_service.convert_pdf(file_path, backend=self._selected_backend)

            self.job.document_markdown = result.markdown
            self.job.page_count = result.page_count

            # Check if PDF is scanned (no text extracted)
            if not result.markdown or len(result.markdown.strip()) < 50:
                logger.info("PDF appears to be scanned (no text). Using OCR fallback...")
                self.update_progress(
                    "text_extraction",
                    current_step,
                    total_steps,
                    message="Scanned PDF detected, running OCR...",
                )
                ocr_text = await self._ocr_scanned_pdf(file_path)
                if ocr_text:
                    self.job.document_markdown = ocr_text
                    self.job.models_used.append("tesseract-ocr")

            current_step += 1
            self.update_progress(
                "text_extraction",
                current_step,
                total_steps,
                message=f"Extracted text from {result.page_count or 'unknown'} pages",
            )

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            self.fail_processing(f"Text extraction failed: {e}")
            return self.job

        # Step 2: Extract and process images
        if self.settings.extract_images:
            self.update_progress(
                "image_extraction",
                current_step,
                total_steps,
                message="Extracting images from PDF...",
            )

            images = result.images or []
            self.job.frames_extracted = len(images)

            # Convert to VisualElements
            for img_info in images:
                element = VisualElement(
                    type=VisualContentType.IMAGE,
                    page=img_info.get("page"),
                    image_path=img_info.get("path"),
                )
                self.job.visual_elements.append(element)

            current_step += 1
            self.update_progress(
                "image_extraction",
                current_step,
                total_steps,
                message=f"Extracted {len(images)} images",
            )

        # Step 3: Describe images/charts with the configured VLM
        if self.settings.describe_charts and self.job.visual_elements:
            self.update_progress(
                "visual_analysis",
                current_step,
                total_steps,
                message="Loading vision model...",
            )

            # Load the configured vision model if not already loaded
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
                "visual_analysis",
                current_step,
                total_steps,
                message="Analyzing visual content...",
            )

            analyzed = 0
            for element in self.job.visual_elements:
                if element.image_path:
                    try:
                        # Classify content type
                        content_type = await self.vision_service.classify(
                            Path(element.image_path)
                        )
                        element.type = self._map_content_type(content_type)

                        # Get description for charts/diagrams
                        if element.type in [
                            VisualContentType.CHART,
                            VisualContentType.DIAGRAM,
                            VisualContentType.TABLE,
                        ]:
                            description = await self.vision_service.describe(
                                Path(element.image_path),
                                content_type=content_type,
                            )
                            element.description = description

                        analyzed += 1
                        self.update_progress(
                            "visual_analysis",
                            current_step,
                            total_steps,
                            substage=f"image_{analyzed}",
                            message=f"Analyzed {analyzed}/{len(self.job.visual_elements)} images",
                        )

                    except Exception as e:
                        logger.warning(f"Failed to analyze image: {e}")

            self.job.frames_analyzed = analyzed
            current_step += 1

        # Step 4: Parse document structure
        self.update_progress(
            "structure_parsing",
            current_step,
            total_steps,
            message="Parsing document structure...",
        )

        sections = self._parse_markdown_structure(self.job.document_markdown)
        self.job.document_sections = sections

        current_step += 1
        self.update_progress(
            "structure_parsing",
            current_step,
            total_steps,
            message=f"Parsed {len(sections)} sections",
        )

        # Mark models used and track which backend was used
        self.job.models_used.append(self._selected_backend.value)
        self.job.pdf_backend_used = self._selected_backend.value
        if self.settings.describe_charts:
            self.job.models_used.append("vision")

        return self.job

    def _map_content_type(self, content_type) -> VisualContentType:
        """Map VisionService ContentType to VisualContentType."""
        from services.vision_service import ContentType

        mapping = {
            ContentType.SLIDE: VisualContentType.SLIDE,
            ContentType.CODE: VisualContentType.CODE,
            ContentType.DIAGRAM: VisualContentType.DIAGRAM,
            ContentType.CHART: VisualContentType.CHART,
            ContentType.TABLE: VisualContentType.TABLE,
            ContentType.TEXT: VisualContentType.DOCUMENT,
            ContentType.SCREENSHOT: VisualContentType.IMAGE,
            ContentType.PHOTO: VisualContentType.IMAGE,
        }
        return mapping.get(content_type, VisualContentType.IMAGE)

    def _parse_markdown_structure(self, markdown: str) -> List[DocumentSection]:
        """Parse markdown into document sections."""
        sections = []
        if not markdown:
            return sections

        current_page = 1
        lines = markdown.split("\n")
        current_section = None

        for line in lines:
            # Check for page markers (MarkItDown may include these)
            if "---" in line or "Page" in line:
                # Simple page detection heuristic
                if any(c.isdigit() for c in line):
                    try:
                        current_page = int("".join(c for c in line if c.isdigit()))
                    except ValueError:
                        pass
                continue

            # Parse headings
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                content = line.lstrip("#").strip()

                if content:
                    section_type = "title" if level == 1 else "heading"
                    current_section = DocumentSection(
                        type=section_type,
                        level=level,
                        content=content,
                        page=current_page,
                    )
                    sections.append(current_section)

            # Parse lists
            elif line.strip().startswith(("-", "*", "•")) or (
                len(line.strip()) > 2 and line.strip()[0].isdigit() and line.strip()[1] == "."
            ):
                content = line.strip().lstrip("-*•0123456789.").strip()
                if content:
                    sections.append(DocumentSection(
                        type="list",
                        level=0,
                        content=content,
                        page=current_page,
                    ))

            # Parse paragraphs (non-empty, non-heading lines)
            elif line.strip() and not line.startswith("|"):
                # Skip table rows
                sections.append(DocumentSection(
                    type="paragraph",
                    level=0,
                    content=line.strip(),
                    page=current_page,
                ))

            # Parse tables
            elif line.startswith("|"):
                # Simple table detection - group consecutive table lines
                if sections and sections[-1].type == "table":
                    # Append to existing table
                    sections[-1].content += "\n" + line
                else:
                    sections.append(DocumentSection(
                        type="table",
                        level=0,
                        content=line,
                        page=current_page,
                    ))

        return sections

    async def _ocr_scanned_pdf(self, file_path: Path) -> Optional[str]:
        """
        Extract text from a scanned PDF using OCR.

        Renders each page as an image and runs Tesseract OCR.
        """
        try:
            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image
            import io

            doc = fitz.open(str(file_path))
            all_text = []

            total_pages = len(doc)
            logger.info(f"Running OCR on {total_pages} pages...")

            for page_num in range(total_pages):
                page = doc[page_num]

                # Render page at 200 DPI for good OCR quality
                mat = fitz.Matrix(200 / 72, 200 / 72)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                # Run OCR
                try:
                    text = pytesseract.image_to_string(image)
                    if text.strip():
                        all_text.append(f"## Page {page_num + 1}\n\n{text.strip()}")

                    # Update progress
                    self.update_progress(
                        "text_extraction",
                        0,
                        4,
                        substage=f"ocr_page_{page_num + 1}",
                        message=f"OCR: Page {page_num + 1}/{total_pages}",
                    )

                except Exception as e:
                    logger.warning(f"OCR failed for page {page_num + 1}: {e}")

                # Also save page image as visual element
                page_img_path = self._temp_dir / f"page_{page_num + 1}.png"
                image.save(str(page_img_path))

                element = VisualElement(
                    type=VisualContentType.SLIDE,
                    page=page_num + 1,
                    image_path=str(page_img_path),
                    description=f"Page {page_num + 1}",
                )
                self.job.visual_elements.append(element)

            doc.close()

            if all_text:
                return "\n\n".join(all_text)
            return None

        except ImportError as e:
            logger.error(f"OCR dependencies not available: {e}")
            return None
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None
