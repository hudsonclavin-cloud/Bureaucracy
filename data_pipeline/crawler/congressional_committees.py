from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError

from data_pipeline.crawler.common import extract_html_candidates, request_text, split_env_list


DEFAULT_COMMITTEE_URLS = (
    "https://www.house.gov/committees",
    "https://www.senate.gov/committees/index.htm",
)


def discover_candidates(*, timeout: int = 45) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []

    for url in split_env_list("PIPELINE_COMMITTEE_URLS", DEFAULT_COMMITTEE_URLS):
        default_parent = "Legislative Branch"
        if "senate" in url.lower():
            default_parent = "Legislative Branch"

        try:
            html = request_text(url, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue

        candidates.extend(
            extract_html_candidates(
                html,
                source_url=url,
                source_type="congressional_committee",
                discovery_method="committee_listing_scan",
                default_parent=default_parent,
                desc_prefix="Candidate discovered from official congressional committee listings.",
            )
        )

    return {"candidates": candidates}


if __name__ == "__main__":
    print(discover_candidates())
