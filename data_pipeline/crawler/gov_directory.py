from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError

from data_pipeline.crawler.common import extract_html_candidates, request_text, split_env_list


DEFAULT_DIRECTORY_URLS = (
    "https://www.usa.gov/agency-index",
    "https://www.commerce.gov/bureaus-and-offices",
    "https://www.dhs.gov/organizational-chart",
    "https://www.state.gov/biographies-list/",
)


def discover_candidates(*, timeout: int = 45) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []

    for url in split_env_list("PIPELINE_GOV_DIRECTORY_URLS", DEFAULT_DIRECTORY_URLS):
        try:
            html = request_text(url, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue

        candidates.extend(
            extract_html_candidates(
                html,
                source_url=url,
                source_type="gov_directory",
                discovery_method="html_directory_scan",
                desc_prefix="Candidate discovered from an official government organization directory.",
            )
        )

    return {"candidates": candidates}


if __name__ == "__main__":
    print(discover_candidates())
