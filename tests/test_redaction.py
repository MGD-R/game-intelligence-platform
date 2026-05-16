from urllib.parse import unquote

from src.ingestion.redaction import REDACTED, redact_dsn, redact_headers, redact_mapping, redact_url


def test_redaction_hides_header_and_mapping_secrets() -> None:
    headers = redact_headers({"Authorization": "Bearer secret-token", "User-Agent": "gip"})
    payload = redact_mapping({"api_key": "secret", "nested": {"client_secret": "hidden"}})

    assert headers["Authorization"] == REDACTED
    assert payload["api_key"] == REDACTED
    assert payload["nested"]["client_secret"] == REDACTED


def test_redaction_hides_url_and_dsn_secrets() -> None:
    redacted_url = redact_url("https://example.com/path?api_key=secret&query=doom")
    redacted_dsn = redact_dsn("postgresql://user:password@localhost:5432/gip")

    assert "secret" not in redacted_url
    assert "password" not in redacted_dsn
    assert REDACTED in unquote(redacted_url)
    assert REDACTED in redacted_dsn
