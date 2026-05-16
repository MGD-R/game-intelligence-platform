"""Shared CLI argument helpers for ingestion commands."""

from __future__ import annotations

import argparse


def build_common_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the request without calling APIs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Limit the number of items or checks.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass response cache and refresh from the network.",
    )
    parser.add_argument(
        "--from-cache-only",
        action="store_true",
        help="Use cached responses only and fail if they are missing.",
    )
    parser.add_argument("--source", help="Optional single-source filter.")
    parser.add_argument(
        "--network",
        action="store_true",
        help="Allow tiny network checks for enabled sources.",
    )
    parser.add_argument(
        "--no-network",
        action="store_false",
        dest="network",
        help="Force safe local-only checks without network calls.",
    )
    parser.set_defaults(network=False)
    return parser
