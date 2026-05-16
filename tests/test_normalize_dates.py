from src.preprocessing.normalize_dates import normalize_release_date


def test_normalize_release_date_handles_valid_date() -> None:
    assert normalize_release_date("2013-09-17") == ("2013-09-17", 2013, None)


def test_normalize_release_date_handles_partial_and_null_values() -> None:
    assert normalize_release_date("2013") == (None, 2013, "partial_release_date")
    assert normalize_release_date(None) == (None, None, "missing_release_date")
