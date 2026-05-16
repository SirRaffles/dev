"""B4 unit tests: global glossary helper."""

import importlib
from pathlib import Path


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
