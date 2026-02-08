"""
Document processing service.

Supports multiple backends:
- Docling (IBM) for PDFs - best structure/table extraction
- PyMuPDF4LLM for fast PDF extraction
- MarkItDown for PPTX, DOCX, and other formats

Handles conversion of PDF, PPTX, DOCX, and other documents to markdown format.
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PDFBackend(str, Enum):
    """Available PDF processing backends."""
    DOCLING = "docling"  # Best structure/tables (AI-powered)
    PYMUPDF4LLM = "pymupdf4llm"  # Fastest extraction
    MARKITDOWN = "markitdown"  # Basic fallback


def auto_select_pdf_backend(pdf_path: Path) -> PDFBackend:
    """
    Auto-select the best PDF backend based on document characteristics.

    Uses PyMuPDF to quickly scan the PDF and determine:
    - If it has tables → use Docling (AI-powered table extraction)
    - If it appears scanned (image-only) → use Docling (OCR support)
    - Otherwise → use PyMuPDF4LLM (faster for simple documents)

    Args:
        pdf_path: Path to the PDF file

    Returns:
        PDFBackend enum value
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))

        has_tables = False
        is_scanned = True  # Assume scanned until we find text
        total_text_chars = 0

        # Sample first few pages (max 5) for efficiency
        pages_to_check = min(len(doc), 5)

        for page_num in range(pages_to_check):
            page = doc[page_num]

            # Check for text content
            text = page.get_text()
            if text.strip():
                is_scanned = False
                total_text_chars += len(text)

            # Check for tables by looking for table-like structures
            # Tables often have many small text blocks in grid patterns
            blocks = page.get_text("blocks")
            if len(blocks) > 10:
                # Many blocks might indicate a table
                # Check for grid-like alignment
                x_positions = sorted(set(int(b[0]) for b in blocks if len(b) > 4))
                y_positions = sorted(set(int(b[1]) for b in blocks if len(b) > 4))

                # If we have multiple aligned columns and rows, likely a table
                if len(x_positions) >= 3 and len(y_positions) >= 3:
                    has_tables = True

            # Also check for actual table annotations
            tables = page.find_tables()
            if tables and len(tables.tables) > 0:
                has_tables = True

        doc.close()

        # Decision logic
        if is_scanned:
            logger.info(f"PDF auto-detect: Scanned PDF detected → using Docling (OCR)")
            return PDFBackend.DOCLING
        elif has_tables:
            logger.info(f"PDF auto-detect: Tables detected → using Docling (AI tables)")
            return PDFBackend.DOCLING
        else:
            logger.info(f"PDF auto-detect: Simple PDF → using PyMuPDF4LLM (fast)")
            return PDFBackend.PYMUPDF4LLM

    except Exception as e:
        logger.warning(f"PDF auto-detect failed: {e}. Defaulting to Docling.")
        return PDFBackend.DOCLING


@dataclass
class DocumentConversionResult:
    """Result of document conversion."""
    markdown: str
    title: Optional[str] = None
    page_count: Optional[int] = None
    images: List[Dict[str, Any]] = None  # List of extracted image info
    tables: List[Dict[str, Any]] = None  # List of extracted table info
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.images is None:
            self.images = []
        if self.tables is None:
            self.tables = []
        if self.metadata is None:
            self.metadata = {}


class DocumentService:
    """
    Service for converting documents to markdown using MarkItDown.

    Supports:
    - PDF (.pdf)
    - PowerPoint (.pptx)
    - Word (.docx)
    - Excel (.xlsx)
    - Images (.jpg, .png) - with LLM description
    - HTML (.html)
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf": "PDF document",
        ".pptx": "PowerPoint presentation",
        ".ppt": "PowerPoint presentation (legacy)",
        ".docx": "Word document",
        ".doc": "Word document (legacy)",
        ".xlsx": "Excel spreadsheet",
        ".xls": "Excel spreadsheet (legacy)",
        ".html": "HTML document",
        ".htm": "HTML document",
        ".jpg": "JPEG image",
        ".jpeg": "JPEG image",
        ".png": "PNG image",
        ".gif": "GIF image",
        ".csv": "CSV file",
        ".json": "JSON file",
        ".xml": "XML file",
        ".txt": "Text file",
        ".md": "Markdown file",
    }

    def __init__(
        self,
        llm_client: Optional[Any] = None,
        llm_model: Optional[str] = None,
    ):
        """
        Initialize DocumentService.

        Args:
            llm_client: Optional OpenAI-compatible client for image descriptions
            llm_model: Model name for image descriptions (e.g., "gpt-4o", "glm-4.6v")
        """
        self._markitdown = None
        self._llm_client = llm_client
        self._llm_model = llm_model

    def _get_markitdown(self):
        """Lazy-load MarkItDown instance."""
        if self._markitdown is None:
            try:
                from markitdown import MarkItDown

                # Configure with LLM if available
                if self._llm_client and self._llm_model:
                    self._markitdown = MarkItDown(
                        mlm_client=self._llm_client,
                        mlm_model=self._llm_model,
                    )
                else:
                    self._markitdown = MarkItDown()

                logger.info("MarkItDown initialized successfully")

            except ImportError:
                logger.error(
                    "markitdown not installed. Install with: pip install 'markitdown[all]'"
                )
                raise

        return self._markitdown

    def is_supported(self, file_path: Path) -> bool:
        """Check if a file type is supported."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def convert(self, file_path: Path) -> DocumentConversionResult:
        """
        Convert a document to markdown.

        Args:
            file_path: Path to the document file

        Returns:
            DocumentConversionResult with markdown content and metadata
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not self.is_supported(file_path):
            raise ValueError(
                f"Unsupported file type: {file_path.suffix}. "
                f"Supported: {list(self.SUPPORTED_EXTENSIONS.keys())}"
            )

        logger.info(f"Converting document: {file_path.name}")

        try:
            md = self._get_markitdown()
            result = md.convert(str(file_path))

            # Parse metadata from result if available
            metadata = {}
            page_count = None
            title = None

            # Extract title from first heading if present
            lines = result.text_content.split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Try to get page count for PDFs
            if file_path.suffix.lower() == ".pdf":
                page_count = self._get_pdf_page_count(file_path)

            return DocumentConversionResult(
                markdown=result.text_content,
                title=title,
                page_count=page_count,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"Failed to convert {file_path}: {e}")
            raise

    def _get_pdf_page_count(self, file_path: Path) -> Optional[int]:
        """Get page count from a PDF file."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return None

    def convert_pdf_with_docling(self, file_path: Path) -> DocumentConversionResult:
        """
        Convert a PDF using Docling (IBM) for best structure/table extraction.

        Docling uses AI-powered layout analysis and TableFormer for tables.

        Args:
            file_path: Path to the PDF file

        Returns:
            DocumentConversionResult with markdown content and extracted tables
        """
        file_path = Path(file_path)
        logger.info(f"Converting PDF with Docling: {file_path.name}")

        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(str(file_path))

            # Export to markdown
            markdown = result.document.export_to_markdown()

            # Extract tables
            tables = []
            if hasattr(result.document, 'tables'):
                for i, table in enumerate(result.document.tables):
                    try:
                        tables.append({
                            "index": i,
                            "content": table.export_to_markdown() if hasattr(table, 'export_to_markdown') else str(table),
                        })
                    except Exception as e:
                        logger.warning(f"Failed to export table {i}: {e}")

            # Extract metadata
            metadata = {}
            if hasattr(result.document, 'metadata'):
                metadata = dict(result.document.metadata) if result.document.metadata else {}

            # Get page count
            page_count = self._get_pdf_page_count(file_path)

            # Extract title from markdown
            title = None
            lines = markdown.split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            return DocumentConversionResult(
                markdown=markdown,
                title=title,
                page_count=page_count,
                tables=tables,
                metadata=metadata,
            )

        except ImportError:
            logger.error("docling not installed. Install with: pip install docling")
            raise
        except Exception as e:
            logger.error(f"Docling conversion failed: {e}")
            raise

    def convert_pdf_fast(self, file_path: Path) -> DocumentConversionResult:
        """
        Convert a PDF using PyMuPDF4LLM for fast extraction.

        ~10x faster than Docling but less structure preservation.

        Args:
            file_path: Path to the PDF file

        Returns:
            DocumentConversionResult with markdown content
        """
        file_path = Path(file_path)
        logger.info(f"Converting PDF with PyMuPDF4LLM (fast mode): {file_path.name}")

        try:
            import pymupdf4llm

            markdown = pymupdf4llm.to_markdown(str(file_path))

            # Get page count
            page_count = self._get_pdf_page_count(file_path)

            # Extract title from markdown
            title = None
            lines = markdown.split("\n")
            for line in lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            return DocumentConversionResult(
                markdown=markdown,
                title=title,
                page_count=page_count,
            )

        except ImportError:
            logger.error("pymupdf4llm not installed. Install with: pip install pymupdf4llm")
            raise
        except Exception as e:
            logger.error(f"PyMuPDF4LLM conversion failed: {e}")
            raise

    def convert_pdf(
        self,
        file_path: Path,
        backend: PDFBackend = PDFBackend.DOCLING,
    ) -> DocumentConversionResult:
        """
        Convert a PDF using the specified backend.

        Args:
            file_path: Path to the PDF file
            backend: Which PDF backend to use (docling, pymupdf4llm, markitdown)

        Returns:
            DocumentConversionResult with markdown content
        """
        if backend == PDFBackend.DOCLING:
            return self.convert_pdf_with_docling(file_path)
        elif backend == PDFBackend.PYMUPDF4LLM:
            return self.convert_pdf_fast(file_path)
        else:
            # Fall back to MarkItDown
            return self.convert(file_path)

    def convert_with_images(
        self,
        file_path: Path,
        output_dir: Path,
        describe_images: bool = True,
    ) -> DocumentConversionResult:
        """
        Convert a document and extract images.

        Args:
            file_path: Path to the document file
            output_dir: Directory to save extracted images
            describe_images: Whether to generate descriptions for images

        Returns:
            DocumentConversionResult with markdown, images, and descriptions
        """
        file_path = Path(file_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # First, convert with MarkItDown
        result = self.convert(file_path)

        # Extract images based on file type
        images = []
        extension = file_path.suffix.lower()

        if extension == ".pdf":
            images = self._extract_pdf_images(file_path, output_dir)
        elif extension == ".pptx":
            images = self._extract_pptx_images(file_path, output_dir)
        elif extension == ".docx":
            images = self._extract_docx_images(file_path, output_dir)

        # Describe images if requested and LLM is available
        if describe_images and self._llm_client and images:
            for img_info in images:
                if img_info.get("path"):
                    try:
                        description = self._describe_image(Path(img_info["path"]))
                        img_info["description"] = description
                    except Exception as e:
                        logger.warning(f"Failed to describe image: {e}")
                        img_info["description"] = None

        result.images = images
        return result

    def _extract_pdf_images(
        self, file_path: Path, output_dir: Path
    ) -> List[Dict[str, Any]]:
        """Extract images from a PDF file."""
        images = []
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))

            for page_num, page in enumerate(doc):
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Save image
                    image_filename = f"page{page_num + 1}_img{img_index + 1}.{image_ext}"
                    image_path = output_dir / image_filename

                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    images.append({
                        "path": str(image_path),
                        "page": page_num + 1,
                        "index": img_index + 1,
                        "format": image_ext,
                        "size": len(image_bytes),
                    })

            doc.close()
            logger.info(f"Extracted {len(images)} images from PDF")

        except ImportError:
            logger.warning("PyMuPDF not installed, skipping PDF image extraction")
        except Exception as e:
            logger.error(f"Failed to extract PDF images: {e}")

        return images

    def _extract_pptx_images(
        self, file_path: Path, output_dir: Path
    ) -> List[Dict[str, Any]]:
        """Extract images from a PowerPoint file."""
        images = []
        try:
            from pptx import Presentation
            from pptx.enum.shapes import MSO_SHAPE_TYPE

            prs = Presentation(str(file_path))

            for slide_num, slide in enumerate(prs.slides, 1):
                img_index = 0
                for shape in slide.shapes:
                    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                        img_index += 1
                        image = shape.image
                        image_bytes = image.blob
                        image_ext = image.ext

                        # Save image
                        image_filename = f"slide{slide_num}_img{img_index}.{image_ext}"
                        image_path = output_dir / image_filename

                        with open(image_path, "wb") as f:
                            f.write(image_bytes)

                        images.append({
                            "path": str(image_path),
                            "slide": slide_num,
                            "index": img_index,
                            "format": image_ext,
                            "size": len(image_bytes),
                        })

            logger.info(f"Extracted {len(images)} images from PPTX")

        except ImportError:
            logger.warning("python-pptx not installed, skipping PPTX image extraction")
        except Exception as e:
            logger.error(f"Failed to extract PPTX images: {e}")

        return images

    def _extract_docx_images(
        self, file_path: Path, output_dir: Path
    ) -> List[Dict[str, Any]]:
        """Extract images from a Word document."""
        images = []
        try:
            from docx import Document

            doc = Document(str(file_path))

            for rel_id, rel in doc.part.rels.items():
                if "image" in rel.reltype:
                    image = rel.target_part
                    image_bytes = image.blob
                    image_ext = image.content_type.split("/")[-1]

                    # Save image
                    image_filename = f"image_{rel_id}.{image_ext}"
                    image_path = output_dir / image_filename

                    with open(image_path, "wb") as f:
                        f.write(image_bytes)

                    images.append({
                        "path": str(image_path),
                        "rel_id": rel_id,
                        "format": image_ext,
                        "size": len(image_bytes),
                    })

            logger.info(f"Extracted {len(images)} images from DOCX")

        except ImportError:
            logger.warning("python-docx not installed, skipping DOCX image extraction")
        except Exception as e:
            logger.error(f"Failed to extract DOCX images: {e}")

        return images

    def _describe_image(self, image_path: Path) -> Optional[str]:
        """
        Generate a description for an image using the configured LLM.

        Args:
            image_path: Path to the image file

        Returns:
            Description string or None if failed
        """
        if not self._llm_client or not self._llm_model:
            return None

        try:
            import base64

            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            # Determine MIME type
            ext = image_path.suffix.lower()
            mime_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(ext, "image/jpeg")

            # Call LLM
            response = self._llm_client.chat.completions.create(
                model=self._llm_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Describe this image concisely. Focus on the main "
                                    "content, any text visible, and key visual elements. "
                                    "If it's a chart or diagram, describe what it shows."
                                ),
                            },
                        ],
                    }
                ],
                max_tokens=256,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"Failed to describe image {image_path}: {e}")
            return None


# Singleton instance
_document_service: Optional[DocumentService] = None


def get_document_service(
    llm_client: Optional[Any] = None,
    llm_model: Optional[str] = None,
) -> DocumentService:
    """Get or create the DocumentService instance."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService(llm_client, llm_model)
    return _document_service
