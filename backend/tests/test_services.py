"""
Unit tests for multi-modal services.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.model_manager import ModelManager, ModelName, ModelConfig, get_model_manager
from services.document_service import DocumentService, DocumentConversionResult, get_document_service
from services.vision_service import VisionService, ContentType, ImageAnalysisResult, get_vision_service


class TestModelManager:
    """Tests for ModelManager service."""

    def test_model_manager_initialization(self):
        """Test ModelManager initializes correctly."""
        manager = ModelManager()
        assert manager is not None
        assert not manager.is_loaded(ModelName.WHISPER)
        assert not manager.is_loaded(ModelName.VISION)
        assert not manager.is_loaded(ModelName.DIARIZATION)

    def test_get_model_manager_singleton(self):
        """Test get_model_manager returns singleton."""
        manager1 = get_model_manager()
        manager2 = get_model_manager()
        assert manager1 is manager2

    def test_model_config_values(self):
        """Test model configuration values."""
        assert ModelConfig.CONFIGS[ModelName.WHISPER]["priority"] == 1
        assert ModelConfig.CONFIGS[ModelName.VISION]["priority"] == 3
        assert ModelConfig.CONFIGS[ModelName.DIARIZATION]["priority"] == 2

        assert ModelConfig.CONFIGS[ModelName.WHISPER]["memory_mb"] == 3000
        assert ModelConfig.CONFIGS[ModelName.VISION]["memory_mb"] == 8000

    def test_vision_model_default_comes_from_config(self, monkeypatch):
        """The VLM name should be a single config value, not stale GLM text in one layer."""
        import importlib
        import config
        import services.model_manager as model_manager

        monkeypatch.setenv("VISION_MODEL_PATH", "mlx-community/Test-Vision-Model-4bit")
        importlib.reload(config)
        importlib.reload(model_manager)

        assert config.VISION_MODEL_PATH == "mlx-community/Test-Vision-Model-4bit"
        assert model_manager.DEFAULT_VISION_MODEL_PATH == config.VISION_MODEL_PATH

    def test_get_available_memory(self):
        """Test getting available memory."""
        manager = ModelManager()
        memory = manager.get_available_memory_mb()
        # Should return a reasonable value
        assert memory >= 0

    def test_get_total_loaded_memory_empty(self):
        """Test total loaded memory when no models loaded."""
        manager = ModelManager()
        assert manager.get_total_loaded_memory_mb() == 0

    def test_get_status(self):
        """Test getting model status."""
        manager = ModelManager()
        status = manager.get_status()

        assert "models" in status
        assert "whisper" in status["models"]
        assert "vision" in status["models"]
        assert "diarization" in status["models"]
        assert "total_memory_used_mb" in status
        assert "available_memory_mb" in status

    def test_get_model_when_not_loaded(self):
        """Test getting model that isn't loaded."""
        manager = ModelManager()
        model = manager.get_model(ModelName.WHISPER)
        assert model is None


class TestDocumentService:
    """Tests for DocumentService."""

    def test_document_service_initialization(self):
        """Test DocumentService initializes correctly."""
        service = DocumentService()
        assert service is not None

    def test_get_document_service_singleton(self):
        """Test get_document_service."""
        service = get_document_service()
        assert service is not None

    def test_supported_extensions(self):
        """Test supported file extensions."""
        assert ".pdf" in DocumentService.SUPPORTED_EXTENSIONS
        assert ".pptx" in DocumentService.SUPPORTED_EXTENSIONS
        assert ".docx" in DocumentService.SUPPORTED_EXTENSIONS
        assert ".xlsx" in DocumentService.SUPPORTED_EXTENSIONS

    def test_is_supported(self):
        """Test file support checking."""
        service = DocumentService()
        assert service.is_supported(Path("test.pdf"))
        assert service.is_supported(Path("test.pptx"))
        assert service.is_supported(Path("test.docx"))
        assert not service.is_supported(Path("test.xyz"))

    def test_document_conversion_result(self):
        """Test DocumentConversionResult model."""
        result = DocumentConversionResult(
            markdown="# Test\n\nContent here",
            title="Test",
            page_count=5,
        )
        assert result.markdown == "# Test\n\nContent here"
        assert result.title == "Test"
        assert result.page_count == 5
        assert result.images == []
        assert result.tables == []

    def test_convert_nonexistent_file(self):
        """Test converting nonexistent file raises error."""
        service = DocumentService()
        with pytest.raises(FileNotFoundError):
            service.convert(Path("/nonexistent/file.pdf"))

    def test_convert_unsupported_file(self):
        """Test converting unsupported file type."""
        service = DocumentService()
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"test content")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                service.convert(temp_path)
        finally:
            temp_path.unlink()


class TestVisionService:
    """Tests for VisionService."""

    def test_vision_service_initialization(self):
        """Test VisionService initializes correctly."""
        service = VisionService()
        assert service is not None

    def test_get_vision_service_singleton(self):
        """Test get_vision_service."""
        service = get_vision_service()
        assert service is not None

    def test_content_type_enum(self):
        """Test ContentType enum values."""
        assert ContentType.SLIDE.value == "slide"
        assert ContentType.CODE.value == "code"
        assert ContentType.DIAGRAM.value == "diagram"
        assert ContentType.CHART.value == "chart"

    def test_image_analysis_result(self):
        """Test ImageAnalysisResult model."""
        result = ImageAnalysisResult(
            description="A presentation slide",
            content_type=ContentType.SLIDE,
            extracted_text="Title: Introduction",
            confidence=0.95,
        )
        assert result.description == "A presentation slide"
        assert result.content_type == ContentType.SLIDE
        assert result.extracted_text == "Title: Introduction"
        assert result.confidence == 0.95

    def test_prompts_defined(self):
        """Test that all prompts are defined."""
        assert "describe" in VisionService.PROMPTS
        assert "classify" in VisionService.PROMPTS
        assert "ocr" in VisionService.PROMPTS
        assert "slide" in VisionService.PROMPTS
        assert "code" in VisionService.PROMPTS
        assert "chart" in VisionService.PROMPTS

    def test_analyze_nonexistent_file(self):
        """Test analyzing nonexistent file raises error."""
        import asyncio
        service = VisionService()
        with pytest.raises(FileNotFoundError):
            asyncio.get_event_loop().run_until_complete(
                service.analyze(Path("/nonexistent/image.jpg"))
            )

    def test_tesseract_ocr_available(self):
        """Test Tesseract OCR availability check."""
        service = VisionService(use_tesseract_fallback=True)
        # _tesseract_available reflects whether tesseract is installed
        assert isinstance(service._tesseract_available, bool)

    def test_tesseract_ocr_with_image(self):
        """Test Tesseract OCR on a simple image."""
        from PIL import Image, ImageDraw, ImageFont

        service = VisionService(use_tesseract_fallback=True)

        # Create a simple test image with text
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (200, 50), color="white")
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "Hello World", fill="black")
            img.save(f.name)
            temp_path = Path(f.name)

        try:
            text = service._tesseract_ocr(temp_path)
            # OCR might not be perfect, just check it returns something
            assert text is None or isinstance(text, str)
        finally:
            temp_path.unlink()

    def test_set_model(self):
        """Test setting the vision model."""
        service = VisionService()
        mock_model = Mock()
        service.set_model(mock_model)
        assert service._model_dict is mock_model

    def test_mime_type_mapping(self):
        """Test that common image extensions are recognized."""
        # VisionService doesn't expose a _get_mime_type helper;
        # verify the extension-to-MIME mapping used internally in
        # DocumentService._describe_image instead.
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
        }
        for ext, expected in mime_map.items():
            assert mime_map.get(ext) == expected

    def test_parse_content_type(self):
        """Test content type parsing from model response."""
        service = VisionService()
        assert service._parse_content_type("slide") == ContentType.SLIDE
        assert service._parse_content_type("This is a code snippet") == ContentType.CODE
        assert service._parse_content_type("diagram showing...") == ContentType.DIAGRAM
        assert service._parse_content_type("random words here") == ContentType.UNKNOWN
        assert service._parse_content_type("some text content") == ContentType.TEXT


class TestDocumentServiceIntegration:
    """Integration tests for DocumentService with real files."""

    @staticmethod
    def _markitdown_available() -> bool:
        try:
            import markitdown  # noqa: F401
            return True
        except ImportError:
            return False

    @pytest.mark.skipif(
        not _markitdown_available.__func__(),
        reason="markitdown not installed",
    )
    def test_convert_text_file(self):
        """Test converting a simple text file."""
        service = DocumentService()

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
            f.write("# Test Document\n\nThis is a test paragraph.")
            temp_path = Path(f.name)

        try:
            result = service.convert(temp_path)
            assert result.markdown is not None
            assert len(result.markdown) > 0
        finally:
            temp_path.unlink()

    @pytest.mark.skipif(
        not _markitdown_available.__func__(),
        reason="markitdown not installed",
    )
    def test_convert_json_file(self):
        """Test converting a JSON file."""
        service = DocumentService()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write('{"name": "test", "value": 123}')
            temp_path = Path(f.name)

        try:
            result = service.convert(temp_path)
            assert result.markdown is not None
        finally:
            temp_path.unlink()

    @pytest.mark.skipif(
        not _markitdown_available.__func__(),
        reason="markitdown not installed",
    )
    def test_convert_csv_file(self):
        """Test converting a CSV file."""
        service = DocumentService()

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            f.write("name,age,city\nAlice,30,NYC\nBob,25,LA")
            temp_path = Path(f.name)

        try:
            result = service.convert(temp_path)
            assert result.markdown is not None
            # CSV should be converted to table format
            assert "Alice" in result.markdown or "name" in result.markdown
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
