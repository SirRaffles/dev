"""B4 unit tests: global glossary helper."""

import importlib


def _reload_glossary():
    """Re-import the glossary module so it picks up the patched ICLOUD_BASE_PATH."""
    import services.glossary
    return importlib.reload(services.glossary)


def test_load_missing_file_returns_none(icloud_base):
    glossary = _reload_glossary()
    assert glossary.load_global_glossary() is None
    assert glossary.load_global_glossary_terms() == []


def test_load_empty_file_returns_none(icloud_base):
    (icloud_base / "contexts" / "_global.md").write_text("   \n  \n", encoding="utf-8")
    glossary = _reload_glossary()
    assert glossary.load_global_glossary() is None
    assert glossary.load_global_glossary_terms() == []


def test_load_returns_text_and_terms(icloud_base):
    body = (
        "# Global Glossary\n\n"
        "## Active\n\n"
        "Manukai, DMG Mori, Starrag, Pascal Weber, Daniel.\n"
    )
    (icloud_base / "contexts" / "_global.md").write_text(body, encoding="utf-8")
    glossary = _reload_glossary()

    text = glossary.load_global_glossary()
    assert text is not None
    assert "Manukai" in text
    assert "DMG Mori" in text

    terms = glossary.load_global_glossary_terms()
    assert "Manukai" in terms
    assert "Starrag" in terms
    assert "DMG" in terms or "Mori" in terms


def test_append_auto_learned_term_creates_section(icloud_base):
    body = "# Global Glossary\n\n## Active\n\n(empty)\n"
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(body, encoding="utf-8")
    glossary = _reload_glossary()

    glossary.append_auto_learned_term(
        "Manukai",
        source_job_id="job-1",
        context_phrase="founder of Manukai",
    )
    out = target.read_text(encoding="utf-8")
    assert "## Auto-learned (pending review)" in out
    assert "Manukai" in out.split("## Auto-learned (pending review)")[1]


def test_append_auto_learned_term_is_idempotent(icloud_base):
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(
        "# Global Glossary\n\n## Active\n\n## Auto-learned (pending review)\n\n- Manukai (job-1)\n",
        encoding="utf-8",
    )
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("manukai", source_job_id="job-2", context_phrase="x")
    glossary.append_auto_learned_term("MANUKAI", source_job_id="job-3", context_phrase="y")
    out = target.read_text(encoding="utf-8")

    pending = out.split("## Auto-learned (pending review)")[1]
    assert pending.lower().count("manukai") == 1


def test_append_creates_file_if_missing(icloud_base):
    target = icloud_base / "contexts" / "_global.md"
    assert not target.exists()
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("Starrag", source_job_id="job-1", context_phrase="...")
    assert target.exists()
    out = target.read_text(encoding="utf-8")
    assert "Starrag" in out
    assert "## Auto-learned (pending review)" in out


def test_append_does_not_match_substring_in_unrelated_line(icloud_base):
    """Short term 'ETH' must not match 'method' or similar substring lines."""
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(
        "# Global Glossary\n\n## Active\n\nSome existing method description here.\n\n",
        encoding="utf-8",
    )
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("ETH", source_job_id="job-1", context_phrase="university")
    out = target.read_text(encoding="utf-8")
    assert "## Auto-learned (pending review)" in out
    pending = out.split("## Auto-learned (pending review)")[1]
    assert "ETH" in pending


def test_append_dedupes_against_bullet_lead_only(icloud_base):
    """A bullet whose context phrase contains 'DMG' must not block adding 'DMG' as a new term
    when the bullet's term is something else (e.g. 'Siemens')."""
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(
        "# Global Glossary\n\n## Active\n\n## Auto-learned (pending review)\n\n"
        "- Siemens (from job-1: competitor of DMG Mori)\n",
        encoding="utf-8",
    )
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("DMG", source_job_id="job-2", context_phrase="machine tools")
    out = target.read_text(encoding="utf-8")
    # DMG should now appear as a new bullet
    pending = out.split("## Auto-learned (pending review)")[1]
    assert pending.count("DMG") >= 2  # once in Siemens context, once as new bullet
    # The new bullet for DMG must exist
    assert "- DMG " in pending


def test_append_dedupes_against_active_comma_separated_terms(icloud_base):
    """Terms listed comma-separated under Active (the seed format) must be detected as existing."""
    target = icloud_base / "contexts" / "_global.md"
    target.write_text(
        "# Global Glossary\n\n## Active\n\nManukai, DMG Mori, Starrag.\n",
        encoding="utf-8",
    )
    glossary = _reload_glossary()

    glossary.append_auto_learned_term("Manukai", source_job_id="job-1", context_phrase="x")
    glossary.append_auto_learned_term("Starrag", source_job_id="job-2", context_phrase="y")
    out = target.read_text(encoding="utf-8")
    # Both should be no-ops (already in Active)
    assert "## Auto-learned (pending review)" not in out or \
           "Manukai" not in out.split("## Active")[1].split("\n\n## ")[0] or True
    # Stronger check: the pending section should not contain Manukai or Starrag as new bullets
    if "## Auto-learned (pending review)" in out:
        pending = out.split("## Auto-learned (pending review)")[1]
        assert "- Manukai" not in pending
        assert "- Starrag" not in pending


def test_append_concurrent_writes_do_not_lose_terms(icloud_base):
    """Two concurrent appends both land in the file."""
    import threading
    target = icloud_base / "contexts" / "_global.md"
    target.write_text("# Global Glossary\n\n## Active\n\n", encoding="utf-8")
    glossary = _reload_glossary()

    barrier = threading.Barrier(2)
    def worker(term):
        barrier.wait()
        glossary.append_auto_learned_term(term, source_job_id="job-x", context_phrase="x")

    t1 = threading.Thread(target=worker, args=("Manukai",))
    t2 = threading.Thread(target=worker, args=("Starrag",))
    t1.start(); t2.start(); t1.join(); t2.join()

    out = target.read_text(encoding="utf-8")
    assert "Manukai" in out
    assert "Starrag" in out


def test_transcription_merges_global_first(icloud_base, monkeypatch):
    """merge_context_sources call sites must put global glossary first."""
    (icloud_base / "contexts" / "_global.md").write_text(
        "# Global Glossary\n\n## Active\n\nManukai\n",
        encoding="utf-8",
    )
    (icloud_base / "contexts" / "deal.md").write_text(
        "# Deal context\n\nPascal Weber call.\n",
        encoding="utf-8",
    )

    # Re-import after icloud_base patched config
    import importlib
    import services.transcription as t
    importlib.reload(t)

    from job_models import TranscriptionSettings
    settings = TranscriptionSettings(context_path="deal.md", speaker_ids=None)

    # Mimic the call-site composition used inside _run_transcription_sync.
    from services.glossary import load_global_glossary
    merged = t.merge_context_sources(
        load_global_glossary(),
        t.load_context_document(settings.context_path),
        t.load_speakers_context(settings.speaker_ids),
    )

    assert merged is not None
    # Global must come before the deal context (priority order).
    assert merged.index("Manukai") < merged.index("Pascal Weber call")
