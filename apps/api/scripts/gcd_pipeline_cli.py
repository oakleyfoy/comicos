"""Shared CLI flags for P102/P103 GCD pipeline scripts."""

from __future__ import annotations

import argparse
from pathlib import Path


def add_output_argument(
    parser: argparse.ArgumentParser,
    *,
    default: str | None = None,
    help_text: str = "Report or audit JSON output path",
) -> None:
    parser.add_argument(
        "-o",
        "--output",
        "--out",
        dest="output",
        default=default,
        help=help_text,
    )


def add_gcd_cache_arguments(
    parser: argparse.ArgumentParser,
    *,
    gcd_default: str | None = None,
    cache_default: str | None = None,
) -> None:
    if gcd_default is not None:
        parser.add_argument("--gcd-db", default=gcd_default, help="GCD SQLite database path")
    else:
        parser.add_argument("--gcd-db", default=None, help="GCD SQLite database path (default: settings)")
    if cache_default is not None:
        parser.add_argument("--cache", default=cache_default, help="ComicOS catalog cache SQLite path")
    else:
        parser.add_argument("--cache", default=None, help="ComicOS catalog cache SQLite path (default: p101 cache)")


def add_refresh_cache_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Rebuild catalog cache from Postgres before run",
    )


def add_json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")


def add_all_catalog_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--all",
        action="store_true",
        help="Whole-catalog mode: enrich existing catalog_issue rows (ignore --publisher; year optional)",
    )


def add_publisher_year_scope_arguments(parser: argparse.ArgumentParser, *, publisher_required: bool = False) -> None:
    if publisher_required:
        parser.add_argument("--publisher", required=True)
    else:
        parser.add_argument("--publisher", default=None)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--year-from", type=int, default=None)
    parser.add_argument("--year-to", type=int, default=None)


def add_confirm_write_argument(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    kwargs: dict = {
        "default": None,
        "help": "Must be YES for write-batch scripts",
    }
    if required:
        kwargs["required"] = True
    parser.add_argument("--confirm-write", **kwargs)


def add_report_source_arguments(parser: argparse.ArgumentParser, *, default_report: str) -> None:
    parser.add_argument("--report", default=default_report, help="Write-batch report JSON path")
    parser.add_argument("--job-id", type=int, default=None, help="Load report from catalog_import_job id")


def add_audit_mode_arguments(parser: argparse.ArgumentParser, *, default_sample_size: int = 50) -> None:
    parser.add_argument(
        "--sample-size",
        "--barcode-samples",
        dest="sample_size",
        type=int,
        default=default_sample_size,
        help="Number of barcode rows to sample for lookup tests",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Scoped audit: report counts, batch-local DB checks, barcode samples (faster)",
    )
    add_json_argument(parser)


def resolve_output_path(args: argparse.Namespace, default: Path) -> Path:
    raw = getattr(args, "output", None)
    if raw is None or str(raw).strip() == "":
        return default
    return Path(raw)
