from pathlib import Path

from mission_hub.research_wiki import lint, page_metadata


ROOT = Path(__file__).resolve().parents[1]


def test_commissioned_research_wiki_lints_cleanly() -> None:
    result = lint(ROOT)
    assert result["errors"] == []
    assert result["ok"] is True
    assert result["source_count"] == 5
    assert result["page_count"] == 9
    assert result["planning_step_count"] == 10


def test_wiki_metadata_is_machine_readable() -> None:
    metadata = page_metadata(ROOT / "mission_hub" / "wiki" / "index.md")
    assert metadata["page_id"] == "wiki-index"
    assert metadata["page_type"] == "index"
