# GAO pay tables — refused, recorded (2026-10-08)

The thirteenth research batch named GAO's own pay tables
(`https://www.gao.gov/assets/2023-02/2023_PAY_TABLES.pdf`, a 2023 file) and
GAO's careers pages as the documents that would band GAO's Managing Directors,
Assistant Directors, Senior Analysts and Analysts across its mission teams.

Nothing here was served. `www.gao.gov` answers `robots.txt` **403** to this
project's User-Agent, and a HEAD request for the pay-table PDF itself answered
403 the same day, so this is the host refusing the crawler, not a robots rule
and not the proxy (`docs/NETWORK_ACCESS.md` §2 and §16 already record the same
403 on `www.gao.gov/about`). Each `.meta.json` beside this file is
`scripts/fetch_fixture.py`'s own record of the attempt:

| File | URL |
|---|---|
| `2023_PAY_TABLES.pdf.meta.json` | `https://www.gao.gov/assets/2023-02/2023_PAY_TABLES.pdf` |
| `benefits.meta.json` | `https://www.gao.gov/about/careers/benefits` |
| `careers.meta.json` | `https://www.gao.gov/about/careers` |

Because the host refused, no current (2026) GAO pay table could be found or
read, and none was guessed at.

What WAS read is the law GAO's personnel system rests on, from the Government
Publishing Office's 2024 edition of the Code through govinfo's link service:
`tests/fixtures/uscode/gao_31_usc_732_govinfo2024.html` and
`gao_31_usc_733_govinfo2024.html`. Section 732(c)(1) says "the Comptroller
General shall publish a schedule of basic pay rates for officers and employees
of the Office", and 732(c)(2) caps the highest rate at level III of the
Executive Schedule; section 733(a)(3)(A) bounds the GAO Senior Executive
Service's basic pay to "not more than the maximum rate or less than the minimum
rate for the Senior Executive Service under section 5382 of title 5". Neither
section names a Managing Director, an Assistant Director, an Analyst or a band,
so neither says which pay structure any of this graph's GAO posts sits in. A
ceiling is not a rate, a statutory bound on a pay system is not a document
placing a post in it, and nothing is published from either section.

**Retried 2026-10-21, after this session's proxy began admitting `.gov`
hosts generally (`docs/NETWORK_ACCESS.md`).** The wider access changed
nothing about GAO specifically: `www.gao.gov/about/careers` and the real 2026
pay table this session located
(`www.gao.gov/assets/2026-04/2026%20Pay%20Tables%20-%20All%20Localities.pdf`,
confirmed to exist by a web search quoting its own effective date of January
11, 2026 and a locality table beginning with Washington, DC) both still
answer `robots.txt` **403** to this project's User-Agent
(`careers_retry_2026-10-21.html.meta.json`,
`2026_pay_tables_all_localities.pdf.meta.json`). `www.gao.gov` is not on
`politeness.STANDARD_4XX_HOSTS`, so under this project's own policy the 403
refuses the fetch rather than being read as "Unavailable, permitted" under RFC
9309 §2.3.1.3. Nothing new is published; this is the second recorded refusal
of this host, and the 2026 table's existence is confirmed without this
project having read it.
