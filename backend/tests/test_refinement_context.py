"""B1 + B3 unit tests: refinement context injection and model/timeout args."""

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


def test_run_claude_uses_sonnet_and_300s_timeout(monkeypatch):
    """B3: _run_claude must invoke claude CLI with --model sonnet and accept timeout=300."""
    import subprocess
    from services import refinement

    captured = {}

    class _Result:
        returncode = 0
        stdout = '{"language": "en", "domain": "", "summary": "", "speakers": [], "corrections": [], "uncertain_terms": []}'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        return _Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    refinement._run_claude("hi", "{}", "/fake/claude", timeout=300)

    cmd = captured["cmd"]
    assert "--model" in cmd
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "sonnet", f"expected sonnet, got {cmd[model_idx + 1]!r}"
    assert captured["timeout"] == 300


def test_analyze_passes_300s_timeout_to_run_claude():
    """B3: analyze() must request the 300s budget for Sonnet on full transcripts."""
    from unittest.mock import patch
    svc = _make_service()
    captured = {}
    def fake_run(prompt, schema, claude_path, timeout=120):
        captured["timeout"] = timeout
        return {"language": "en", "domain": "", "summary": "",
                "speakers": [], "corrections": [], "uncertain_terms": []}
    with patch("services.refinement._run_claude", side_effect=fake_run):
        svc.analyze([{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])
    assert captured["timeout"] == 300


def test_analysis_schema_includes_speaker_corrections():
    """The exported schema must declare speaker_corrections so Sonnet's
    output is recognized as valid when the field is present."""
    import json
    from services.refinement import ANALYSIS_SCHEMA

    schema = json.loads(ANALYSIS_SCHEMA)
    props = schema["properties"]
    assert "speaker_corrections" in props, (
        "ANALYSIS_SCHEMA must declare speaker_corrections for Combo C diarization polish"
    )
    sc = props["speaker_corrections"]
    assert sc["type"] == "array"
    item = sc["items"]
    assert item["type"] == "object"
    assert set(item["required"]) == {"segment_index", "speaker", "reason"}
    assert item["properties"]["segment_index"]["type"] == "integer"
    assert item["properties"]["speaker"]["type"] == "string"
    assert item["properties"]["reason"]["type"] == "string"
    # speaker_corrections must NOT be in top-level required — it's optional
    assert "speaker_corrections" not in schema["required"]
