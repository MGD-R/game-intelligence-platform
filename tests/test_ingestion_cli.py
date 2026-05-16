from src.ingestion.check_sources import main as check_sources_main
from src.ingestion.cli import build_common_parser


def test_common_parser_supports_required_flags() -> None:
    parser = build_common_parser("ingestion")
    args = parser.parse_args(["--dry-run", "--limit", "2", "--force-refresh", "--source", "rawg"])

    assert args.dry_run is True
    assert args.limit == 2
    assert args.force_refresh is True
    assert args.source == "rawg"
    assert args.network is False


def test_check_sources_no_network_runs_safely() -> None:
    assert check_sources_main(["--no-network"]) == 0
