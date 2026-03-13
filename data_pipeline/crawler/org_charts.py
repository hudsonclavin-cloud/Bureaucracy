from __future__ import annotations

from typing import Any
from urllib.error import HTTPError, URLError

from data_pipeline.crawler.common import extract_html_candidates, request_text, split_env_list


DEFAULT_ORG_CHART_URLS = (
    "https://www.energy.gov/organization-chart",
    "https://www.dhs.gov/organizational-chart",
    "https://www.state.gov/organization-of-the-state-department/",
    "https://www.defense.gov/Our-Story/Organization-Chart/",
)


def discover_candidates(*, timeout: int = 45) -> dict[str, list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []

    for url in split_env_list("PIPELINE_ORG_CHART_URLS", DEFAULT_ORG_CHART_URLS):
        try:
            html = request_text(url, timeout=timeout)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue

        candidates.extend(
            extract_html_candidates(
                html,
                source_url=url,
                source_type="gov_org_chart",
                discovery_method="org_chart_scan",
                desc_prefix="Candidate discovered from an official government organizational chart.",
            )
        )

    return {"candidates": candidates}


if __name__ == "__main__":
    print(discover_candidates())
