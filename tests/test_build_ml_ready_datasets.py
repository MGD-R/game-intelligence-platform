from src.preprocessing.build_ml_ready_datasets import main


def test_ml_ready_builder_supports_dry_run(capsys) -> None:
    exit_code = main(["--dry-run", "--allow-empty"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "refresh candidate pairs" in captured
    assert "generate manifest" in captured
