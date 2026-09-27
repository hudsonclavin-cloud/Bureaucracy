# DFAS and DoD military basic-pay tables — refused, recorded (2026-09-27)

The third research pack (CURATION.md §19) named the Defense Finance and
Accounting Service's basic-pay tables as the document that would price the
uniformed principals this graph carries — the Chairman and Vice Chairman of
the Joint Chiefs, the five service chiefs, the Chief of the National Guard
Bureau, the Commandant of the Coast Guard and the six senior enlisted
advisers — at the O-10 rate (capped by 37 U.S.C. 203(a)(2) at the monthly
equivalent of Executive Schedule level II) and the senior-enlisted rate.

Nothing here was served. Every host that publishes the table answers
`robots.txt` **403** from this sandbox with an Akamai "Access Denied" body
(`errors.edgesuite.net`), and the pay-table pages themselves answer 403 the
same way, so this is the host refusing the crawler, not the proxy and not a
robots rule:

| Host | robots.txt | page |
|---|---|---|
| `www.dfas.mil` (`/militarymembers/payentitlements/Pay-Tables/Basic-Pay/CO/`, `/EM/`) | 403 | 403 |
| `militarypay.defense.gov` (`/Pay/Basic-Pay/Active-Duty-Pay/`) | 403 | 403 |
| `comptroller.defense.gov`, `www.dcms.uscg.mil`, `www.uscg.mil` | 403 | — |
| `www.jcs.mil`, `www.army.mil`, `www.navy.mil`, `www.af.mil`, `www.marines.mil`, `www.spaceforce.mil` | 403 | — |

Each `.meta.json` beside this file is `scripts/fetch_fixture.py`'s own record
of the attempt. The 4xx-robots policy `politeness.STANDARD_4XX_HOSTS` grants
would not help here — that policy covers a host whose robots.txt is
unavailable but whose pages answer, and these pages do not.

What IS committed is the law the table rests on: `tests/fixtures/uscode/
military_pay_37_usc_203.html` (rates; the O-7–O-10 ceiling at the monthly
equivalent of level II) and `military_pay_37_usc_1009.html` (the annual
adjustment). Neither prints a rate. A ceiling is not a rate, and this
repository does not publish a figure it computed from a cap, so no module
reads them yet. If a DoD-published table becomes reachable, the module's
shape is `derived_pay.py`'s: Title 10 says the post carries grade O-10, the
table prices O-10, neither document alone states the figure, and the panel
says so.
