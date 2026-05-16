from src.preprocessing.normalize_text import normalize_title_text


def test_normalize_title_text_removes_selected_symbols() -> None:
    assert normalize_title_text("The Witcher® 3: Wild Hunt") == "the witcher 3 wild hunt"
    assert normalize_title_text("Dark Souls™ II") == "dark souls ii"


def test_normalize_title_text_trims_and_collapses_whitespace() -> None:
    assert normalize_title_text("  DOOM  ") == "doom"
