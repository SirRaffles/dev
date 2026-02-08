"""
Vision language model service using MLX-VLM.

Provides image analysis, OCR, and content description capabilities
optimized for Apple Silicon using MLX.
"""
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Types of content that can be detected in images."""
    SLIDE = "slide"
    CODE = "code"
    DIAGRAM = "diagram"
    CHART = "chart"
    TABLE = "table"
    TEXT = "text"
    PERSON = "person"
    SCREENSHOT = "screenshot"
    PHOTO = "photo"
    UNKNOWN = "unknown"


@dataclass
class ImageAnalysisResult:
    """Result of image analysis."""
    description: str
    content_type: ContentType
    extracted_text: Optional[str] = None
    confidence: float = 0.0
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class VisionService:
    """
    Vision language model service for image analysis.

    Uses MLX-VLM (optimized for Apple Silicon) for:
    - Image description and understanding
    - OCR (text extraction from images)
    - Content classification
    - Chart/diagram interpretation
    """

    # Prompts for different tasks
    PROMPTS = {
        "describe": (
            "Describe this image concisely. Focus on the main content, "
            "any text visible, and key visual elements."
        ),
        "classify": (
            "What type of content is shown in this image? "
            "Reply with one of: slide, code, diagram, chart, table, text, "
            "person, screenshot, photo, unknown. Just the single word."
        ),
        "ocr": (
            "Extract all visible text from this image. "
            "Preserve the original formatting and structure as much as possible. "
            "If there's no text, respond with 'NO_TEXT'."
        ),
        "slide": (
            "This appears to be a presentation slide. "
            "Provide a structured description including: "
            "1) The slide title if visible "
            "2) Key bullet points or content "
            "3) Any diagrams, charts, or images and what they show"
        ),
        "code": (
            "This image contains code. Extract the code exactly as shown, "
            "preserving formatting. Identify the programming language if possible."
        ),
        "chart": (
            "Analyze this chart or graph. Describe: "
            "1) The type of chart (bar, line, pie, etc.) "
            "2) What data it represents "
            "3) Key trends or insights shown "
            "4) Axis labels and legend if visible"
        ),
        "diagram": (
            "Analyze this diagram. Describe: "
            "1) The type of diagram (flowchart, architecture, UML, etc.) "
            "2) The main components or elements "
            "3) The relationships or flow between components "
            "4) The overall concept being illustrated"
        ),
    }

    def __init__(
        self,
        model: Optional[Any] = None,
        use_tesseract_fallback: bool = True,
    ):
        """
        Initialize VisionService.

        Args:
            model: Pre-loaded MLX-VLM model dict from ModelManager
                   (contains 'model', 'processor', 'config', 'model_name')
            use_tesseract_fallback: Whether to use Tesseract for OCR fallback
        """
        self._model_dict = model
        self._use_tesseract = use_tesseract_fallback
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def set_model(self, model: Any) -> None:
        """Set the vision model instance (dict from ModelManager)."""
        self._model_dict = model

    async def analyze(
        self,
        image_path: Path,
        task: str = "describe",
        custom_prompt: Optional[str] = None,
    ) -> ImageAnalysisResult:
        """
        Analyze an image using the vision model.

        Args:
            image_path: Path to the image file
            task: Type of analysis ("describe", "classify", "ocr", etc.)
            custom_prompt: Optional custom prompt override

        Returns:
            ImageAnalysisResult with analysis results
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Get prompt
        prompt = custom_prompt or self.PROMPTS.get(task, self.PROMPTS["describe"])

        # If no model available, try OCR fallback for text extraction
        if self._model_dict is None:
            if task == "ocr" and self._tesseract_available:
                text = self._tesseract_ocr(image_path)
                return ImageAnalysisResult(
                    description="Text extracted via Tesseract OCR",
                    content_type=ContentType.TEXT,
                    extracted_text=text,
                    confidence=0.7,
                )
            else:
                return ImageAnalysisResult(
                    description="Vision model not available",
                    content_type=ContentType.UNKNOWN,
                    confidence=0.0,
                )

        try:
            from mlx_vlm import generate
            from mlx_vlm.prompt_utils import apply_chat_template

            model = self._model_dict["model"]
            processor = self._model_dict["processor"]
            config = self._model_dict["config"]

            # Apply chat template with image
            formatted_prompt = apply_chat_template(
                processor,
                config,
                prompt,
                num_images=1,
            )

            # Generate response
            generation_result = generate(
                model,
                processor,
                formatted_prompt,
                image=str(image_path),
                max_tokens=512,
                temperature=0.3,
                verbose=False,
            )

            result_text = generation_result.text.strip()

            # Process based on task
            if task == "classify":
                content_type = self._parse_content_type(result_text)
                return ImageAnalysisResult(
                    description=f"Content type: {content_type.value}",
                    content_type=content_type,
                    confidence=0.8,
                )
            elif task == "ocr":
                text = result_text if result_text != "NO_TEXT" else None
                return ImageAnalysisResult(
                    description="OCR extraction complete",
                    content_type=ContentType.TEXT,
                    extracted_text=text,
                    confidence=0.85,
                )
            else:
                return ImageAnalysisResult(
                    description=result_text,
                    content_type=ContentType.UNKNOWN,
                    confidence=0.8,
                )

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")

            # Fallback to Tesseract for OCR if available
            if task == "ocr" and self._tesseract_available:
                text = self._tesseract_ocr(image_path)
                return ImageAnalysisResult(
                    description="Text extracted via Tesseract OCR (fallback)",
                    content_type=ContentType.TEXT,
                    extracted_text=text,
                    confidence=0.6,
                )

            return ImageAnalysisResult(
                description=f"Analysis failed: {str(e)}",
                content_type=ContentType.UNKNOWN,
                confidence=0.0,
            )

    async def classify(self, image_path: Path) -> ContentType:
        """Classify the content type of an image."""
        result = await self.analyze(image_path, task="classify")
        return result.content_type

    async def extract_text(self, image_path: Path) -> Optional[str]:
        """Extract text from an image (OCR)."""
        result = await self.analyze(image_path, task="ocr")
        return result.extracted_text

    async def describe(
        self,
        image_path: Path,
        content_type: Optional[ContentType] = None,
    ) -> str:
        """
        Generate a description of an image.

        Args:
            image_path: Path to the image
            content_type: Optional hint about content type for better prompting

        Returns:
            Description string
        """
        # Use content-specific prompt if type is known
        task = "describe"
        if content_type:
            if content_type == ContentType.SLIDE:
                task = "slide"
            elif content_type == ContentType.CODE:
                task = "code"
            elif content_type == ContentType.CHART:
                task = "chart"
            elif content_type == ContentType.DIAGRAM:
                task = "diagram"

        result = await self.analyze(image_path, task=task)
        return result.description

    async def analyze_batch(
        self,
        image_paths: List[Path],
        task: str = "describe",
    ) -> List[ImageAnalysisResult]:
        """
        Analyze multiple images in batch.

        Args:
            image_paths: List of image paths
            task: Analysis task type

        Returns:
            List of analysis results
        """
        results = []
        for path in image_paths:
            try:
                result = await self.analyze(path, task=task)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch analysis failed for {path}: {e}")
                results.append(ImageAnalysisResult(
                    description=f"Analysis failed: {str(e)}",
                    content_type=ContentType.UNKNOWN,
                    confidence=0.0,
                ))
        return results

    def _parse_content_type(self, text: str) -> ContentType:
        """Parse content type from model response."""
        text = text.lower().strip()

        mapping = {
            "slide": ContentType.SLIDE,
            "code": ContentType.CODE,
            "diagram": ContentType.DIAGRAM,
            "chart": ContentType.CHART,
            "table": ContentType.TABLE,
            "text": ContentType.TEXT,
            "person": ContentType.PERSON,
            "screenshot": ContentType.SCREENSHOT,
            "photo": ContentType.PHOTO,
        }

        for key, value in mapping.items():
            if key in text:
                return value

        return ContentType.UNKNOWN

    def _tesseract_ocr(self, image_path: Path) -> Optional[str]:
        """Extract text using Tesseract OCR."""
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            text = pytesseract.image_to_string(image)
            return text.strip() if text.strip() else None

        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return None

    def tesseract_ocr_with_confidence(
        self, image_path: Path
    ) -> tuple[Optional[str], float]:
        """
        Extract text using Tesseract with confidence score.

        Returns:
            Tuple of (text, confidence)
        """
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)
            data = pytesseract.image_to_data(
                image, output_type=pytesseract.Output.DICT
            )

            # Calculate average confidence
            confidences = [
                int(c) for c in data["conf"] if c != "-1"
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            # Get text
            text = pytesseract.image_to_string(image)
            return text.strip() if text.strip() else None, avg_confidence / 100.0

        except Exception as e:
            logger.error(f"Tesseract OCR with confidence failed: {e}")
            return None, 0.0


# Singleton instance
_vision_service: Optional[VisionService] = None


def get_vision_service(model: Optional[Any] = None) -> VisionService:
    """Get or create the VisionService instance."""
    global _vision_service
    if _vision_service is None:
        _vision_service = VisionService(model=model)
    elif model is not None:
        _vision_service.set_model(model)
    return _vision_service
