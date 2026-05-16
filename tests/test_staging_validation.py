from src.preprocessing.validate_staging_state import (
    StagingStateValidation,
    validation_error_message,
)


def test_validation_error_message_mentions_prerequisites() -> None:
    validation = StagingStateValidation(
        missing_schemas=[],
        missing_tables=["stg.source_games"],
        empty_tables=["stg.source_games (rawg)"],
    )
    message = validation_error_message(validation)
    assert "stg.source_games" in message
    assert "make rawg-demo" in message
    assert "make entity-data-base" in message
