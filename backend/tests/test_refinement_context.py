"""B1 + B3 unit tests: refinement context injection and model/timeout args."""

import json
from unittest.mock import patch


def _make_service():
    from services.refinement import RefinementService
    return RefinementService(claude_path="/fake/claude")


def _stub_run_claude_capture(captured):
    """Replace _run_claude so analyze() returns a minimal valid response and
    we capture the prompt that was sent."""
    def fake_run(prompt, schema, claude_path, timeout=120):
        captured["prompt"] = prompt
        captured["timeout"] = timeout
        return {
            "language": "en",
            "domain": "test",
            "summary": "...",
            "speakers": [],
            "corrections": [],
            "uncertain_terms": [],
        }
    return fake_run


def test_analyze_omits_known_context_when_no_context():
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze([{"start": 0, "end": 1, "text": "hello", "speaker": "SPEAKER_00"}])
    assert "## Known context" not in captured["prompt"]
    assert "ARE present in the audio" not in captured["prompt"]


def test_analyze_injects_glossary_terms_block():
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hello", "speaker": "SPEAKER_00"}],
            glossary_terms=["Manukai", "DMG Mori", "Starrag"],
        )
    prompt = captured["prompt"]
    assert "## Known context" in prompt
    assert "Manukai" in prompt
    assert "DMG Mori" in prompt
    assert "Starrag" in prompt
    assert "ARE present in the audio" in prompt
    assert "confidence=high" in prompt


def test_analyze_injects_context_text_block():
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            context_text="# Speaker: Pascal Weber\n\nHead of partnerships at Manukai.",
        )
    prompt = captured["prompt"]
    assert "## Known context" in prompt
    assert "Pascal Weber" in prompt
    assert "Manukai" in prompt


def test_refine_propagates_context_and_glossary():
    """refine() must forward both kwargs to analyze()."""
    svc = _make_service()
    captured = {}
    with patch.object(svc, "analyze", return_value={
        "language": "en", "domain": "test", "summary": "",
        "speakers": [], "corrections": [], "uncertain_terms": [],
    }) as mock_analyze:
        svc.refine(
            [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
            context_text="ctx",
            glossary_terms=["t1", "t2"],
        )
    mock_analyze.assert_called_once()
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("context_text") == "ctx"
    assert kwargs.get("glossary_terms") == ["t1", "t2"]
