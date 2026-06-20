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


def test_run_claude_uses_configured_model(monkeypatch):
    """The Claude refinement model must be configurable instead of hardcoded."""
    import subprocess
    from services import refinement

    captured = {}

    class _Result:
        returncode = 0
        stdout = '{"language": "en", "domain": "", "summary": "", "speakers": [], "corrections": [], "uncertain_terms": []}'
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    refinement._run_claude("hi", "{}", "/fake/claude", timeout=300, model="opus")

    cmd = captured["cmd"]
    model_idx = cmd.index("--model")
    assert cmd[model_idx + 1] == "opus"


def test_ollama_provider_parses_structured_json(monkeypatch):
    """Local refinement should be able to use Ollama as a structured JSON provider."""
    import json
    import urllib.request
    from services.refinement import RefinementService

    captured = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({
                "response": '{"language":"en","domain":"test","summary":"","speakers":[],"corrections":[],"uncertain_terms":[]}'
            }).encode("utf-8")

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    svc = RefinementService(provider="ollama", model="qwen3.5:27b", ollama_host="http://127.0.0.1:11434")
    result = svc.analyze([{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])

    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["payload"]["model"] == "qwen3.5:27b"
    assert captured["payload"]["format"] == "json"
    assert result["language"] == "en"


def test_analyze_passes_600s_timeout_to_run_claude():
    """analyze() requests a 600s budget for Sonnet on full transcripts.

    Bumped from 300s after a real-world timeout on a 158-segment Pascal
    Weber/Manukai call: global glossary + speaker bios + diarization context
    pushed Sonnet past 5min. 600s gives comfortable headroom while still
    catching truly hung calls."""
    from unittest.mock import patch
    svc = _make_service()
    captured = {}
    def fake_run(prompt, schema, claude_path, timeout=120):
        captured["timeout"] = timeout
        return {"language": "en", "domain": "", "summary": "",
                "speakers": [], "corrections": [], "uncertain_terms": []}
    with patch("services.refinement._run_claude", side_effect=fake_run):
        svc.analyze([{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])
    assert captured["timeout"] == 600


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


def test_analyze_omits_diarization_block_when_no_speaker_turns():
    """Backward compat: callers that don't pass speaker_turns get the
    original prompt with no Diarization context section."""
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze([{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}])
    assert "## Diarization context" not in captured["prompt"]
    assert "Pyannote detected" not in captured["prompt"]
    assert "speaker_corrections" not in captured["prompt"]


def test_analyze_omits_diarization_block_when_speaker_turns_empty():
    """Empty list is treated identically to None — no block emitted."""
    svc = _make_service()
    captured = {}
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=[],
        )
    assert "## Diarization context" not in captured["prompt"]


def test_analyze_injects_diarization_block_when_speaker_turns_provided():
    """When pyannote turns are passed, the prompt must include the
    Diarization context block, the turn list, and the speaker_corrections
    instruction."""
    svc = _make_service()
    captured = {}
    turns = [
        {"start": 2.4, "end": 15.7, "speaker": "SPEAKER_00"},
        {"start": 15.7, "end": 18.2, "speaker": "SPEAKER_01"},
        {"start": 18.2, "end": 32.1, "speaker": "SPEAKER_00"},
    ]
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=turns,
        )
    prompt = captured["prompt"]
    assert "## Diarization context" in prompt
    assert "Pyannote detected" in prompt
    # Turn timestamps formatted as [start s - end s] with speaker label
    assert "SPEAKER_00" in prompt
    assert "SPEAKER_01" in prompt
    assert "2.40" in prompt or "2.4" in prompt
    assert "15.70" in prompt or "15.7" in prompt
    # The instruction telling Sonnet what to emit
    assert "speaker_corrections" in prompt
    assert "Do NOT rewrite segment text" in prompt


def test_analyze_caps_diarization_turns_at_50():
    """Prompt budget protection: only the first 50 turns appear in the
    Diarization context block, even if more are passed."""
    svc = _make_service()
    captured = {}
    turns = [
        {"start": float(i), "end": float(i + 1), "speaker": f"SPEAKER_{i % 3:02d}"}
        for i in range(75)
    ]
    with patch("services.refinement._run_claude", side_effect=_stub_run_claude_capture(captured)):
        svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=turns,
        )
    prompt = captured["prompt"]
    # Turn 49 (the 50th, 0-indexed) should appear
    assert "49.00" in prompt or "49.0" in prompt
    # Turn 50 (the 51st) and beyond should NOT appear in the diarization block.
    # Use a structural check: count lines in the diarization block.
    block_start = prompt.index("## Diarization context")
    rest = prompt[block_start + len("## Diarization context"):]
    # The diarization block ends with "---\n\n" (the spec's standard
    # known-context separator). Searching for "Review each" or "Transcript:"
    # is wrong: both strings appear INSIDE the block's instruction text,
    # which would falsely truncate before any turn lines render. Use the
    # "---" delimiter that immediately follows the block.
    sep_idx = rest.find("---")
    block_end_rel = sep_idx if sep_idx >= 0 else len(rest)
    block = rest[:block_end_rel]
    turn_lines = [ln for ln in block.splitlines() if "SPEAKER_" in ln]
    assert len(turn_lines) == 50, (
        f"Expected 50 turn lines, got {len(turn_lines)}. Block:\n{block[:500]}"
    )


def test_analyze_returns_speaker_corrections_from_sonnet_response():
    """When Sonnet's response includes speaker_corrections, analyze() must
    pass it through unchanged."""
    svc = _make_service()
    def fake_run(prompt, schema, claude_path, timeout=120):
        return {
            "language": "en", "domain": "test", "summary": "",
            "speakers": [], "corrections": [], "uncertain_terms": [],
            "speaker_corrections": [
                {"segment_index": 12, "speaker": "Pascal",
                 "reason": "interruption mid-David turn"},
            ],
        }
    with patch("services.refinement._run_claude", side_effect=fake_run):
        result = svc.analyze(
            [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}],
            speaker_turns=[{"start": 0, "end": 1, "speaker": "SPEAKER_00"}],
        )
    assert result["speaker_corrections"] == [
        {"segment_index": 12, "speaker": "Pascal",
         "reason": "interruption mid-David turn"},
    ]


def test_apply_corrections_mutates_speaker_per_speaker_corrections():
    """speaker_corrections in the analysis dict must update segment[i].speaker
    for the specified segment_index."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello",  "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "Yes",    "speaker": "SPEAKER_00"},
        {"start": 2.0, "end": 3.0, "text": "Right",  "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [],
        "corrections": [],
        "speaker_corrections": [
            {"segment_index": 1, "speaker": "SPEAKER_01", "reason": "interjection"},
        ],
    }
    refined, _mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "SPEAKER_00"
    assert refined[1]["speaker"] == "SPEAKER_01"  # corrected
    assert refined[2]["speaker"] == "SPEAKER_00"


def test_apply_corrections_speaker_corrections_never_touches_text():
    """Hard guardrail: the speaker_corrections loop must NEVER mutate
    segment.text — even if Sonnet's response includes an unrelated text
    correction that overlaps the segment, the speaker_corrections path
    itself does not touch text. (Text corrections still flow through the
    existing corrections path.)"""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello world", "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [],
        "corrections": [],  # no text corrections
        "speaker_corrections": [
            {"segment_index": 0, "speaker": "SPEAKER_01",
             "reason": "actually the other speaker"},
        ],
    }
    refined, _mapping, count = svc.apply_corrections(segments, analysis)
    assert refined[0]["text"] == "Hello world", (
        "speaker_corrections must NEVER mutate segment.text"
    )
    assert refined[0]["speaker"] == "SPEAKER_01"
    # count is the number of TEXT corrections applied, which is 0 here.
    assert count == 0


def test_apply_corrections_skips_out_of_range_segment_index():
    """Defensive: Sonnet may hallucinate an index. Out-of-range entries
    are silently skipped (no exception, no mutation of any segment)."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [],
        "corrections": [],
        "speaker_corrections": [
            {"segment_index": 99, "speaker": "Ghost", "reason": "out of range"},
            {"segment_index": -1, "speaker": "Negative", "reason": "negative index"},
        ],
    }
    refined, _mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "SPEAKER_00"  # unchanged


def test_apply_corrections_no_op_when_speaker_corrections_absent():
    """Backward compat: analysis dicts without speaker_corrections must
    behave exactly as before — speaker_mapping still applies, but no
    additional speaker mutation happens."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hello", "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [
            {"label": "SPEAKER_00", "name": "David",
             "confidence": "high", "reasoning": "self-introduction"},
        ],
        "corrections": [],
        # speaker_corrections absent
    }
    refined, mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "David"  # speaker_mapping applied
    assert mapping == {"SPEAKER_00": "David"}


def test_apply_corrections_speaker_corrections_overrides_speaker_mapping():
    """When both apply, speaker_corrections wins because it's applied
    AFTER the speaker_mapping rename. This lets Sonnet correct a
    mis-mapped speaker on a per-segment basis."""
    svc = _make_service()
    segments = [
        {"start": 0.0, "end": 1.0, "text": "Hi",   "speaker": "SPEAKER_00"},
        {"start": 1.0, "end": 2.0, "text": "Yes",  "speaker": "SPEAKER_00"},
    ]
    analysis = {
        "speakers": [
            {"label": "SPEAKER_00", "name": "David",
             "confidence": "high", "reasoning": "..."},
        ],
        "corrections": [],
        "speaker_corrections": [
            {"segment_index": 1, "speaker": "Pascal", "reason": "interjection"},
        ],
    }
    refined, _mapping, _count = svc.apply_corrections(segments, analysis)
    assert refined[0]["speaker"] == "David"   # speaker_mapping applied
    assert refined[1]["speaker"] == "Pascal"  # speaker_corrections overrides


def test_refine_propagates_speaker_turns_to_analyze():
    """refine() must forward speaker_turns to analyze() so the
    Diarization context block gets emitted by the underlying analyze call."""
    svc = _make_service()
    turns = [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 6.0, "speaker": "SPEAKER_01"},
    ]
    with patch.object(svc, "analyze", return_value={
        "language": "en", "domain": "test", "summary": "",
        "speakers": [], "corrections": [], "uncertain_terms": [],
    }) as mock_analyze:
        svc.refine(
            [{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}],
            context_text="ctx",
            glossary_terms=["t1"],
            speaker_turns=turns,
        )
    mock_analyze.assert_called_once()
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("context_text") == "ctx"
    assert kwargs.get("glossary_terms") == ["t1"]
    assert kwargs.get("speaker_turns") == turns


def test_refine_defaults_speaker_turns_to_none():
    """Backward compat: callers that don't pass speaker_turns get the
    pre-Combo-C behavior — analyze receives speaker_turns=None."""
    svc = _make_service()
    with patch.object(svc, "analyze", return_value={
        "language": "en", "domain": "test", "summary": "",
        "speakers": [], "corrections": [], "uncertain_terms": [],
    }) as mock_analyze:
        svc.refine([{"start": 0, "end": 1, "text": "x", "speaker": "SPEAKER_00"}])
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("speaker_turns") is None


def test_run_refinement_for_job_builds_speaker_turns_from_job_speakers(monkeypatch):
    """_run_refinement_for_job must build speaker_turns from job.speakers
    (pyannote output) and pass it into refine()."""
    import state
    from routes.refinement import _run_refinement_for_job

    # Fixture job with pyannote turns in job.speakers
    class _Job:
        job_id = "j1"
        status = "completed"
        segments = [{"start": 0, "end": 1, "text": "hi", "speaker": "SPEAKER_00"}]
        speakers = [
            {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
            {"start": 5.0, "end": 6.0, "speaker": "SPEAKER_01"},
        ]
        auto_speaker_matches = None
        refinement_status = None

    job = _Job()

    # Stub job store
    class _JobStore:
        def get(self, jid): return job
        def update(self, j): pass
    monkeypatch.setattr(state, "job_store", _JobStore())
    monkeypatch.setattr(state, "jobs", _JobStore())

    # Stub refinement store
    class _RefStore:
        def update_status(self, jid, s, err=None): pass
        def save_result(self, jid, r): pass
    monkeypatch.setattr(state, "refinement_store", _RefStore())

    captured = {}
    class _RefSvc:
        def refine(self, segments, context_text=None, glossary_terms=None,
                   speaker_turns=None):
            captured["speaker_turns"] = speaker_turns
            return {
                "analysis": {"corrections": []},
                "refined_segments": segments,
                "speaker_mapping": {},
                "corrections_applied": 0,
                "speakers_identified": 0,
                "web_searches_performed": 0,
            }
    monkeypatch.setattr(state, "refinement_service", _RefSvc())

    # Stub context loaders to avoid touching disk
    import services.transcription as txn
    import services.glossary as glo
    monkeypatch.setattr(txn, "load_context_document", lambda p: "")
    monkeypatch.setattr(txn, "load_speakers_context", lambda ids: "")
    monkeypatch.setattr(txn, "merge_context_sources", lambda *a: "")
    monkeypatch.setattr(glo, "load_global_glossary", lambda: "")
    monkeypatch.setattr(glo, "load_global_glossary_terms", lambda: [])

    # Stub the B7 orchestrator — out of scope for this test
    import routes.refinement as rr
    monkeypatch.setattr(rr, "_run_post_refinement_learning", lambda **kw: None)

    _run_refinement_for_job("j1", speaker_ids=None, context_path=None, audio_path=None)

    assert captured.get("speaker_turns") is not None, (
        "_run_refinement_for_job must pass speaker_turns into refine()"
    )
    assert captured["speaker_turns"] == [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 6.0, "speaker": "SPEAKER_01"},
    ]


def test_refine_end_to_end_applies_speaker_corrections_to_refined_segments():
    """Acceptance gate for Sub-plan B: a refine() call with speaker_turns
    + a mocked Sonnet response that includes speaker_corrections must
    produce refined_segments where the targeted segment has the corrected
    speaker AND the segment text is unchanged."""
    svc = _make_service()

    segments = [
        {"start": 0.0, "end": 5.0, "text": "So what do you think of the proposal",
         "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 5.5, "text": "Yes",
         "speaker": "SPEAKER_00"},  # mis-attributed interjection
        {"start": 5.5, "end": 12.0, "text": "I think it's a good idea",
         "speaker": "SPEAKER_00"},
    ]
    speaker_turns = [
        {"start": 0.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 5.0, "end": 5.5, "speaker": "SPEAKER_01"},
        {"start": 5.5, "end": 12.0, "speaker": "SPEAKER_00"},
    ]

    # Mock Sonnet's response: it identifies the segment 1 interjection as
    # being by SPEAKER_01, and renames both labels via the speakers list.
    sonnet_response = {
        "language": "en",
        "domain": "business meeting",
        "summary": "Two speakers discuss a proposal.",
        "speakers": [
            {"label": "SPEAKER_00", "name": "David",
             "confidence": "high", "reasoning": "self-introduced"},
            {"label": "SPEAKER_01", "name": "Pascal",
             "confidence": "high", "reasoning": "self-introduced"},
        ],
        "corrections": [],
        "uncertain_terms": [],
        "speaker_corrections": [
            {"segment_index": 1, "speaker": "Pascal",
             "reason": "brief affirmation mid-David turn, matches pyannote SPEAKER_01"},
        ],
    }

    with patch("services.refinement._run_claude", return_value=sonnet_response):
        result = svc.refine(segments, speaker_turns=speaker_turns)

    refined = result["refined_segments"]
    # Segment 0: SPEAKER_00 -> David via speaker_mapping
    assert refined[0]["speaker"] == "David"
    assert refined[0]["text"] == "So what do you think of the proposal"
    # Segment 1: speaker_mapping renames SPEAKER_00 -> David, then
    # speaker_corrections overrides to Pascal
    assert refined[1]["speaker"] == "Pascal"
    assert refined[1]["text"] == "Yes", (
        "Combo C must NEVER mutate segment.text"
    )
    # Segment 2: SPEAKER_00 -> David
    assert refined[2]["speaker"] == "David"
    assert refined[2]["text"] == "I think it's a good idea"

    # Speaker mapping reflects the rename (not the per-segment correction).
    assert result["speaker_mapping"] == {
        "SPEAKER_00": "David",
        "SPEAKER_01": "Pascal",
    }
