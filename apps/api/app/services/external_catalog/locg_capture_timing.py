from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class IssueCaptureTiming:
    issue_title: str = ""
    issue_url: str = ""
    browser_launch_seconds: float = 0.0
    page_goto_seconds: float = 0.0
    dom_content_loaded_seconds: float = 0.0
    additional_wait_seconds: float = 0.0
    pre_goto_sleep_seconds: float = 0.0
    post_load_wait_timeout_seconds: float = 0.0
    selector_wait_seconds: float = 0.0
    html_extraction_seconds: float = 0.0
    parser_seconds: float = 0.0
    variant_parse_seconds: float = 0.0
    creator_parse_seconds: float = 0.0
    character_parse_seconds: float = 0.0
    image_parse_seconds: float = 0.0
    db_upsert_seconds: float = 0.0
    raw_save_seconds: float = 0.0
    crosswalk_seconds: float = 0.0
    total_issue_seconds: float = 0.0
    skipped: bool = False
    ready_detected: bool = False
    readiness_method: str = "none"
    readiness_warning: str | None = None

    def finalize(self) -> None:
        self.total_issue_seconds = round(
            self.browser_launch_seconds
            + self.page_goto_seconds
            + self.dom_content_loaded_seconds
            + self.additional_wait_seconds
            + self.html_extraction_seconds
            + self.parser_seconds
            + self.variant_parse_seconds
            + self.creator_parse_seconds
            + self.character_parse_seconds
            + self.image_parse_seconds
            + self.db_upsert_seconds
            + self.raw_save_seconds
            + self.crosswalk_seconds,
            3,
        )

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return asdict(self)


@dataclass
class CaptureTimingAudit:
    list_page_goto_seconds: float = 0.0
    list_page_wait_seconds: float = 0.0
    list_selector_wait_seconds: float = 0.0
    list_html_extraction_seconds: float = 0.0
    list_parser_seconds: float = 0.0
    list_raw_save_seconds: float = 0.0
    browser_launch_seconds: float = 0.0
    browser_teardown_seconds: float = 0.0
    crosswalk_end_seconds: float = 0.0
    issue_timings: list[IssueCaptureTiming] = field(default_factory=list)
    total_runtime_seconds: float = 0.0
    cloudflare_wait_count: int = 0
    cloudflare_total_wait_seconds: float = 0.0
    adaptive_throttle: dict[str, Any] = field(default_factory=dict)

    def _sum_issues(self, attr: str) -> float:
        return sum(getattr(row, attr, 0.0) for row in self.issue_timings if not row.skipped)

    def build_summary(self, *, include_per_issue_timings: bool = False) -> dict[str, Any]:
        issues = [row for row in self.issue_timings if not row.skipped]
        for row in issues:
            row.finalize()
        totals = [r.total_issue_seconds for r in issues]
        issue_count = len(issues)
        avg_issue = round(statistics.mean(totals), 3) if totals else 0.0
        median_issue = round(statistics.median(totals), 3) if totals else 0.0
        slowest = max(issues, key=lambda r: r.total_issue_seconds, default=None)

        page_load = (
            self._sum_issues("page_goto_seconds")
            + self._sum_issues("dom_content_loaded_seconds")
            + self.list_page_goto_seconds
            + self.list_page_wait_seconds
        )
        waiting = (
            self._sum_issues("additional_wait_seconds")
            + self.list_selector_wait_seconds
        )
        parsing = (
            self._sum_issues("parser_seconds")
            + self._sum_issues("image_parse_seconds")
            + self.list_parser_seconds
        )
        # variant/creator/character_* are upsert wall-clock (not separate parse paths).
        db_save = self._sum_issues("db_upsert_seconds") + (
            self._sum_issues("variant_parse_seconds")
            + self._sum_issues("creator_parse_seconds")
            + self._sum_issues("character_parse_seconds")
        )
        crosswalk = self.crosswalk_end_seconds + self._sum_issues("crosswalk_seconds")
        raw_save = self._sum_issues("raw_save_seconds") + self.list_raw_save_seconds
        html_extract = self._sum_issues("html_extraction_seconds") + self.list_html_extraction_seconds
        browser_launch = self.browser_launch_seconds + self._sum_issues("browser_launch_seconds")

        buckets = [
            ("page_load", page_load),
            ("page_wait", waiting),
            ("html_extraction", html_extract),
            ("parsing", parsing),
            ("db_save", db_save),
            ("raw_save", raw_save),
            ("crosswalk", crosswalk),
            ("browser_launch", browser_launch),
        ]
        denom = sum(v for _, v in buckets) or 1.0
        top_consumers = [
            {
                "category": name,
                "seconds": round(seconds, 3),
                "pct": round(100.0 * seconds / denom, 1),
            }
            for name, seconds in sorted(buckets, key=lambda item: item[1], reverse=True)
            if seconds > 0
        ]

        breakdown_lines = _format_breakdown_pct(buckets, denom)

        sub_ops: list[tuple[str, float]] = []
        for row in issues:
            sub_ops.append((f"goto:{row.issue_title[:40]}", row.page_goto_seconds))
            sub_ops.append((f"wait:{row.issue_title[:40]}", row.additional_wait_seconds))
            sub_ops.append((f"parse:{row.issue_title[:40]}", row.parser_seconds))
            sub_ops.append((f"db:{row.issue_title[:40]}", row.db_upsert_seconds))
        sub_ops.append(("list_goto", self.list_page_goto_seconds))
        sub_ops.append(("list_wait", self.list_page_wait_seconds + self.list_selector_wait_seconds))
        sub_ops.append(("crosswalk_end", self.crosswalk_end_seconds))
        slowest_ops = [
            {"operation": name, "seconds": round(sec, 3)}
            for name, sec in sorted(sub_ops, key=lambda x: x[1], reverse=True)[:10]
        ]

        summary: dict[str, Any] = {
            "issues_processed": issue_count,
            "total_runtime_seconds": round(self.total_runtime_seconds, 3),
            "issue_count": issue_count,
            "avg_issue_seconds": avg_issue,
            "median_issue_seconds": median_issue,
            "slowest_issue": slowest.issue_title if slowest else None,
            "slowest_issue_seconds": slowest.total_issue_seconds if slowest else 0.0,
            "timing_breakdown_percentages": breakdown_lines,
            "top_runtime_consumers": top_consumers[:10],
            "slowest_10_operations": slowest_ops,
            "total_browser_wait_seconds": round(
                waiting + self.list_page_wait_seconds, 3
            ),
            "total_db_seconds": round(db_save, 3),
            "total_parse_seconds": round(parsing, 3),
            "cloudflare_wait_count": self.cloudflare_wait_count,
            "cloudflare_total_wait_seconds": round(self.cloudflare_total_wait_seconds, 3),
            "adaptive_throttle": self.adaptive_throttle,
        }
        if include_per_issue_timings:
            summary["per_issue_timings"] = [row.to_dict() for row in self.issue_timings]
        else:
            summary["per_issue_timings_count"] = len(self.issue_timings)
        return summary


def _format_breakdown_pct(buckets: list[tuple[str, float]], denom: float) -> list[str]:
    labels = {
        "page_load": "Page Load",
        "page_wait": "Waiting",
        "html_extraction": "HTML Extract",
        "parsing": "Parsing",
        "db_save": "DB Save",
        "raw_save": "Raw Save",
        "crosswalk": "Crosswalk",
        "browser_launch": "Browser Launch",
    }
    lines: list[str] = []
    for key, seconds in sorted(buckets, key=lambda item: item[1], reverse=True):
        if seconds <= 0:
            continue
        pct = 100.0 * seconds / denom
        label = labels.get(key, key)
        lines.append(f"{label} {'.' * max(1, 18 - len(label))} {pct:.1f}%")
    return lines


def log_issue_timing(row: IssueCaptureTiming) -> None:
    row.finalize()
    print(row.issue_title or row.issue_url)
    print(f"goto={row.page_goto_seconds:.1f}s")
    print(f"wait={row.additional_wait_seconds:.1f}s")
    print(f"parse={row.parser_seconds:.1f}s")
    print(f"db={row.db_upsert_seconds:.1f}s")
    print(f"crosswalk={row.crosswalk_seconds:.1f}s")
    ready = "yes" if row.ready_detected else "no"
    print(f"ready={ready} method={row.readiness_method}")
    print(f"total={row.total_issue_seconds:.1f}s")
    print()
