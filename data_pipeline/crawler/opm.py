from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError

from data_pipeline.crawler.common import extract_html_candidates, request_text, split_env_list


DEFAULT_OPM_URLS = (
    "https://www.opm.gov/about-us/our-people-organization/",
    "https://www.opm.gov/about-us/our-people-organization/senior-staff/",
)


def discover_candidates(*, timeout: int = 45) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []

    for url in split_env_list("PIPELINE_OPM_URLS", DEFAULT_OPM_URLS):
        try:
            html = request_text(url, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue

        candidates.extend(
            extract_html_candidates(
                html,
                source_url=url,
                source_type="opm",
                discovery_method="leadership_directory_scan",
                default_parent="Office of Personnel Management",
                desc_prefix="Candidate discovered from OPM leadership or organizational directory data.",
            )
        )

    return {"candidates": candidates}


if __name__ == "__main__":
    print(discover_candidates())
