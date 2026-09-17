# USAspending fixtures: the agency and bureau lists File A is keyed on

USAspending's own reference lists of the agencies and bureaus that report under
the DATA Act, committed exactly as the API served them, so the phase-2 cost
crosswalk (`docs/COST_NOMINATION_RUNBOOK.md`, `docs/EXACT_NODE_COSTS.md` §1)
can name a stable identifier for a curated organisation and a reviewer can
check the nomination against the bytes it was read from. Nothing here is
interpreted. Each file is **verbatim; refreshed only by re-fetching, never
edited by hand**.

Fetched between 2026-09-17T16:12:34Z and 2026-09-17T16:23:45Z with `scripts/fetch_fixture.py`, the project
User-Agent (`bureaucracy-data-pipeline/1.0
(+https://github.com/hudsonclavin-cloud/Bureaucracy)`), TLS verification on and
`HTTPS_PROXY` as the environment set it. `api.usaspending.gov/robots.txt`
answers 404, so every fetch is recorded as `no readable robots.txt (HTTP 404); failing open`:
RFC 9309 §2.3.1.3 treats an unavailable robots.txt as permission to fetch, and
that is the one case `fetch_fixture.py` fails open on. Each raw file has a
sibling `<file>.meta.json` recording `fetched_at`, `url`, `final_url`, HTTP
`status`, `content_type`, `user_agent`, the robots verdict, `bytes`, the
`sha256` of the served body and any `error`.

## What each family is, and what it is not

- **`toptier_agencies.json`** — `GET /api/v2/references/toptier_agencies/`:
  the 111 agencies that submit File A, each with its
  `toptier_code` (the CGAC agency code), name, abbreviation and FY-to-date
  `outlay_amount`, `obligated_amount` and `budget_authority_amount`. **This is
  the list of DATA Act reporters, not of the government**: no committee of
  Congress, no court beyond the Court of Appeals for Veterans Claims, the DC
  Courts and CSOSA, no Library of Congress, GPO, Architect of the Capitol,
  Capitol Police or CBO, no CIA, Postal Service, Smithsonian or Federal
  Reserve. Absence from it means the entity does not report here, and nothing
  more.
- **`sub_components/<toptier>.json`** — `GET /api/v2/agency/<toptier>/sub_components/?fiscal_year=2026`:
  the bureaus Treasury groups that agency's accounts into in GTAS, each with a
  stable `id` slug, `name`, and FY-to-date `total_obligations`, `total_outlays`
  and `total_budgetary_resources`. This is the grouping the crosswalk keys on
  (`<toptier_code>/<id>`), because it is Treasury's own and its accounts are
  complete and non-overlapping for the bureau by construction. Two agencies
  return an empty list (`sub_components/029.json`, `sub_components/1125.json`); the nomination for each
  uses the toptier code instead.
- **`bureau_accounts/<toptier>/<id>.json`** — `GET /api/v2/agency/<toptier>/sub_components/<id>/?fiscal_year=2026`:
  the federal accounts inside each bureau the crosswalk nominated, with the
  same three figures per account. Fetched so a reviewer can see what a bureau
  key covers before accepting it.
- **`sub_agency/<toptier>.json`** — `GET /api/v2/agency/<toptier>/sub_agency/?fiscal_year=2026`:
  the *awarding* subtiers and offices, keyed by award data (File C/D), not by
  account. Fetched first, and superseded by `sub_components` for the
  crosswalk because it exposes no code at the subtier level; kept because the
  office codes beneath (`1234HK`, `19XNEA`) are the only place USAspending
  names sub-bureau offices at all, which a later pass may want.

- **`data_dictionary_crosswalk.xlsx`** — `https://files.usaspending.gov/docs/Data_Dictionary_Crosswalk.xlsx`:
  the publisher's own Data Dictionary, a workbook whose "Public" sheet maps
  every USAspending field to the DATA Act (DAIMS) element it carries, with
  the element's definition. It is here for one row: `GrossOutlayAmountByTAS_CPE`
  → `gross_outlay_amount`, the API's `total_outlays`/`outlay_amount`. The API
  states no unit in words anywhere on a `.gov` host — the endpoint docs are
  a client-side shell loaded from GitHub — so this row is what the scale of
  every figure above rests on (`financial_evidence.DICTIONARY_SCALED_SOURCE_TYPES`),
  quoted verbatim in each record's `unitsEvidence` with this file's digest,
  and re-read by the derive step and the release gate.

**Outlays here are File A gross outlays**, the per-account field
`gross_outlay_amount`, and are not the net figure the Monthly Treasury
Statement prints for the same agency; the two must never be merged, which is
why every nomination read from these files carries the metric `gross_outlays`.
Figures are FY2026 to date at the fetch time and change on every refresh.

## Files

### `toptier_agencies.json`
| File | URL | Fetched (UTC) | HTTP | Bytes | sha256 |
|---|---|---|---|---|---|
| `toptier_agencies.json` | https://api.usaspending.gov/api/v2/references/toptier_agencies/ | 2026-09-17T16:12:34Z | 200 | 52613 | `a6d73e48293fa247861b94cd4d548a307adb32fd7bf8669349d2f573aef181a8` |

### `data_dictionary_crosswalk.xlsx`
| File | URL | Fetched (UTC) | HTTP | Bytes | sha256 |
|---|---|---|---|---|---|
| `data_dictionary_crosswalk.xlsx` | https://files.usaspending.gov/docs/Data_Dictionary_Crosswalk.xlsx | 2026-09-17T16:41:51Z | 200 | 110540 | `d9d9b42747d1e8ac74de1a955847aafda5a3da0ca9ee00f07da9ddf582d40c23` |

### `sub_components/` (52 files)
| File | URL | Fetched (UTC) | HTTP | Bytes | sha256 |
|---|---|---|---|---|---|
| `sub_components/005.json` | https://api.usaspending.gov/api/v2/agency/005/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:49Z | 200 | 366 | `a60dc544624074a52410c05129d51ac8c8035773d0d5a495779e656ca9329811` |
| `sub_components/012.json` | https://api.usaspending.gov/api/v2/agency/012/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:53Z | 200 | 4156 | `e7a80ab91f75e1efaf78ddd0ff775ade234b0eb2d9cd88f72e0a3c1a52e1468c` |
| `sub_components/013.json` | https://api.usaspending.gov/api/v2/agency/013/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:55Z | 200 | 2514 | `cb3dc098e3c982856cd0e0c04d697441fbf9c78636db1815ec27c19376054950` |
| `sub_components/014.json` | https://api.usaspending.gov/api/v2/agency/014/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:22Z | 200 | 3578 | `315d1bb87918223ace16ecdf3127b25c5b7201b752fd026ce524661528dd137f` |
| `sub_components/015.json` | https://api.usaspending.gov/api/v2/agency/015/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:11Z | 200 | 2298 | `254ee44491a1cd065c39bd768b526f5f9881700951d803b3fa5f364c5dc97389` |
| `sub_components/019.json` | https://api.usaspending.gov/api/v2/agency/019/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:15Z | 200 | 1242 | `f9ecd44ea0207a0ec5e5c2942294f04a62fa40b32fb1b91cfbcb057742dbea63` |
| `sub_components/020.json` | https://api.usaspending.gov/api/v2/agency/020/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:24Z | 200 | 3220 | `72f7dd63a903f0c048a86193a92b5a0c7b7d83189768b801eed22347a52bcbc5` |
| `sub_components/024.json` | https://api.usaspending.gov/api/v2/agency/024/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:14Z | 200 | 372 | `3836a5804ca420a1c119fe53d92b4aae01f21f466366eb8714c59315c14c13fe` |
| `sub_components/025.json` | https://api.usaspending.gov/api/v2/agency/025/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:59Z | 200 | 369 | `cd83a94822d1ff0b9fd150a3445f50b5cdb0c10a059d8fc1e46244c90f59df4a` |
| `sub_components/027.json` | https://api.usaspending.gov/api/v2/agency/027/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:37Z | 200 | 373 | `b05bc4b6054bb5311cb5e4551369cdc3f8b018c30963171db78b483c1ffc6ff2` |
| `sub_components/028.json` | https://api.usaspending.gov/api/v2/agency/028/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:30Z | 200 | 375 | `f9db776a352572e6e18b4195938206e6d92bdf8a1d12e3d50e291dcfe6feb76b` |
| `sub_components/029.json` | https://api.usaspending.gov/api/v2/agency/029/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:47Z | 200 | 181 | `b4cba3465a2018580e6b93d2d37b96b670fe65e8710642ab95e34041134e8223` |
| `sub_components/031.json` | https://api.usaspending.gov/api/v2/agency/031/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:12Z | 200 | 362 | `2fd2eb40bae22d6fb662ba10759ea359bd257ba69f2581eaf020cd8ece1e7790` |
| `sub_components/036.json` | https://api.usaspending.gov/api/v2/agency/036/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:20Z | 200 | 719 | `2d985589aaf54a010427818bf83d771aa24d5d53424c282bd703aa68f984ce25` |
| `sub_components/045.json` | https://api.usaspending.gov/api/v2/agency/045/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:31Z | 200 | 381 | `262dbccefef28c124db3c6a460ad065485f3e8d9da98a4a031c9ee7b03263acf` |
| `sub_components/049.json` | https://api.usaspending.gov/api/v2/agency/049/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:08Z | 200 | 360 | `3580ea3a7ee756bdd211b2e4c395394345b3fd2c280858a67e95e10302cb1b67` |
| `sub_components/050.json` | https://api.usaspending.gov/api/v2/agency/050/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:24Z | 200 | 374 | `884132b940263d755e25f0256a2dcde555c87e0c0bbeee63095ec14f7f0c5c42` |
| `sub_components/051.json` | https://api.usaspending.gov/api/v2/agency/051/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:39Z | 200 | 492 | `2b1f3b035d39a0e32c132800280c073d3d1fbde7f5707843089bf1173442538f` |
| `sub_components/054.json` | https://api.usaspending.gov/api/v2/agency/054/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:43Z | 200 | 366 | `bef54d47ad2755e1d3c97a93f722b4dcd503e1a7c2a5eca9760f8f76c8db6048` |
| `sub_components/061.json` | https://api.usaspending.gov/api/v2/agency/061/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:50Z | 200 | 371 | `1fcf55b86eee47bd7ce9a9af2e0199bbc16714519f7227c64c9a28a185352bd0` |
| `sub_components/062.json` | https://api.usaspending.gov/api/v2/agency/062/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:16Z | 200 | 350 | `6ab16bd7a92016fe294d4d36663e06043bf16e03f74adbf8061c97fd4b8eefeb` |
| `sub_components/065.json` | https://api.usaspending.gov/api/v2/agency/065/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:45Z | 200 | 353 | `beede39513a2e2855001166cd8e21c0fd2ecc69331869b3d1b908b39dbf63473` |
| `sub_components/068.json` | https://api.usaspending.gov/api/v2/agency/068/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:29Z | 200 | 370 | `b26b1791db71e404e92952f4ac95687d6d7f6cfe8765805823a8edc444efa199` |
| `sub_components/069.json` | https://api.usaspending.gov/api/v2/agency/069/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:17Z | 200 | 2347 | `b08ee061819f6c57cea48fbb178ff6a8b336588f218c56215f9a1cab673f7f5a` |
| `sub_components/070.json` | https://api.usaspending.gov/api/v2/agency/070/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:06Z | 200 | 3306 | `37119d8f40530fe4371afbb090a240b7967c53d76b8a139f6e570eda074fdf36` |
| `sub_components/073.json` | https://api.usaspending.gov/api/v2/agency/073/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:28Z | 200 | 367 | `f5c481a790534291d8fe3f5b2b071e2d365ee63a12185c7916ff8e52974d3d7d` |
| `sub_components/074.json` | https://api.usaspending.gov/api/v2/agency/074/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:43Z | 200 | 374 | `f31595fab1b3c5583114175de1c4e04df9077c6f14bcf9ae610df54143d8a861` |
| `sub_components/075.json` | https://api.usaspending.gov/api/v2/agency/075/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:03Z | 200 | 2973 | `85239e91e510cc8312a6046eb9bbb9210ee8fc75c2539b71dd37f1ed5e82d989` |
| `sub_components/080.json` | https://api.usaspending.gov/api/v2/agency/080/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:53Z | 200 | 399 | `384e554c71452d44ffa933ebc9c90f977b8ec45177d32275f9ad4af2f4cdcaa1` |
| `sub_components/083.json` | https://api.usaspending.gov/api/v2/agency/083/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:35Z | 200 | 381 | `fee902533d7b312c503bc217477bb94b4081ce646b2066ca32a00648e8d5036d` |
| `sub_components/086.json` | https://api.usaspending.gov/api/v2/agency/086/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:08Z | 200 | 1705 | `d1dc5235cb01cb07a6e4e12a44ee0a3737b485769dfc0483a99d9a04e3f17159` |
| `sub_components/088.json` | https://api.usaspending.gov/api/v2/agency/088/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:55Z | 200 | 391 | `9dd04a57de3616477663bd8239c5923a8e9ea3bf4658c3d57c27d81bd673c81b` |
| `sub_components/089.json` | https://api.usaspending.gov/api/v2/agency/089/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:01Z | 200 | 1122 | `a68ee47620595dfde8b2efbe69f56d843e56485c8995a46648b6fba8e79dd127` |
| `sub_components/090.json` | https://api.usaspending.gov/api/v2/agency/090/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:26Z | 200 | 348 | `c2b4f4c2fd159d83b4282049e307a72a698ef58caea8d97326a5ee60080aa8f3` |
| `sub_components/091.json` | https://api.usaspending.gov/api/v2/agency/091/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:59Z | 200 | 1175 | `836637acc6f0343337509cf6bdb7744a12c5bea7b9a262bf046f92bc2151c4cc` |
| `sub_components/097.json` | https://api.usaspending.gov/api/v2/agency/097/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:57Z | 200 | 1133 | `c319fa64f9ccfee38b950c3788e7290e15ef9ad41eb4edef5fb5cded0434bf64` |
| `sub_components/1100.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:33Z | 200 | 3112 | `e66f91a10349e8c16743c0be80ee912815ea56641426bfd09326601db110e0b5` |
| `sub_components/1125.json` | https://api.usaspending.gov/api/v2/agency/1125/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:18Z | 200 | 182 | `e5149d1c6e13b8c0d0c648529e5bbb9ff511f0081b120ca97a048b529ba7838c` |
| `sub_components/1601.json` | https://api.usaspending.gov/api/v2/agency/1601/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:13Z | 200 | 2695 | `e6d23939da78ea1301e2bdd11b969165ceba8a1e15f36774c09493ad8180a355` |
| `sub_components/1602.json` | https://api.usaspending.gov/api/v2/agency/1602/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:20Z | 200 | 380 | `a54ee46816dfd11d8c9c06ec284e034d5c9b327808eb2a2731050a2068f2cca3` |
| `sub_components/309.json` | https://api.usaspending.gov/api/v2/agency/309/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:45Z | 200 | 361 | `4f959f10c4cd61ab85c7453a4e8c6d4bb94dd4eb62bfb1c66fa9b49d128e8f05` |
| `sub_components/339.json` | https://api.usaspending.gov/api/v2/agency/339/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:17:48Z | 200 | 376 | `b4237f5c801280da4af5c6ab467b30513838fdd9d312e184fe611d84c29e301d` |
| `sub_components/360.json` | https://api.usaspending.gov/api/v2/agency/360/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:41Z | 200 | 354 | `6cb096ddbcbb41b71d5cb497f3ba8f096f4b4dec87a9e1935a72c768144de2fd` |
| `sub_components/389.json` | https://api.usaspending.gov/api/v2/agency/389/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:51Z | 200 | 359 | `0ecf0709bbbe1e15573818696c4d52ac75881027229f0264cb954215887430e0` |
| `sub_components/394.json` | https://api.usaspending.gov/api/v2/agency/394/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:57Z | 200 | 371 | `b4e63f8614e805445e269626c490a8485eeaab116d28538c2398ce6234f39605` |
| `sub_components/417.json` | https://api.usaspending.gov/api/v2/agency/417/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:01Z | 200 | 365 | `ce6f157a27d159af886e9b288a1100ea80b6268a6f8254a361458c3e706fc9da` |
| `sub_components/418.json` | https://api.usaspending.gov/api/v2/agency/418/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:03Z | 200 | 375 | `c5250b7bc186121bcda9d2c6ace8e150b3473451b8c690ca4cf492313786e1fc` |
| `sub_components/420.json` | https://api.usaspending.gov/api/v2/agency/420/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:05Z | 200 | 362 | `0e2ea6456ce3e0f8b8c66c8aae2f873ecc67b3dbd1f01e1c0614df71fbdee6db` |
| `sub_components/421.json` | https://api.usaspending.gov/api/v2/agency/421/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:07Z | 200 | 348 | `7cf9c64256f05b4ccbaa01afa71d15d57a7ff47409b29e01da39b9d040ab6add` |
| `sub_components/424.json` | https://api.usaspending.gov/api/v2/agency/424/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:10Z | 200 | 375 | `a4bd9f628e995882bd5c212edab335a340d6390daa6df3bcff23a8ac80a419e4` |
| `sub_components/525.json` | https://api.usaspending.gov/api/v2/agency/525/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:18:27Z | 200 | 359 | `2463c04c38c44258fa5867ad3c88f53860015fbd087508bd5f1bdf9b5a34deb6` |
| `sub_components/535.json` | https://api.usaspending.gov/api/v2/agency/535/sub_components/?fiscal_year=2026&limit=100 | 2026-09-17T16:19:22Z | 200 | 386 | `5774aecfbc16fb15d0dbdab26bc3b1f364be2338017dcd3517826a63f61ac53d` |

### `bureau_accounts/` (25 files)
| File | URL | Fetched (UTC) | HTTP | Bytes | sha256 |
|---|---|---|---|---|---|
| `bureau_accounts/012/natural-resources-conservation-service.json` | https://api.usaspending.gov/api/v2/agency/012/sub_components/natural-resources-conservation-service/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:00Z | 200 | 2844 | `bc2c927b859132902eb2ce34ca90c4a63d6f622706326fd135afe17912ec0660` |
| `bureau_accounts/013/bureau-of-economic-analysis.json` | https://api.usaspending.gov/api/v2/agency/013/sub_components/bureau-of-economic-analysis/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:04Z | 200 | 531 | `6adfb6081419ac177dd1d5f543acc6e7e4aa81baa1376c9883e9b435ec614884` |
| `bureau_accounts/013/us-patent-and-trademark-office.json` | https://api.usaspending.gov/api/v2/agency/013/sub_components/us-patent-and-trademark-office/?fiscal_year=2026&limit=100 | 2026-09-17T16:23:38Z | 200 | 746 | `d75bcc8772473c6d0ed25186bd76de38495a27f1f65aae4e0461db76391ecfbd` |
| `bureau_accounts/014/bureau-of-land-management.json` | https://api.usaspending.gov/api/v2/agency/014/sub_components/bureau-of-land-management/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:53Z | 200 | 8056 | `93f0231641cbfce4282cd5e09aeacaefa8d5d8175062a0eb1afb3fd5167d0453` |
| `bureau_accounts/014/bureau-of-reclamation.json` | https://api.usaspending.gov/api/v2/agency/014/sub_components/bureau-of-reclamation/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:55Z | 200 | 4718 | `8e9723f5f23cf0f2538ff2a07405e32592ab18057d2e025bca5e2bbccbd9860a` |
| `bureau_accounts/014/bureau-of-safety-and-environmental-enforcement.json` | https://api.usaspending.gov/api/v2/agency/014/sub_components/bureau-of-safety-and-environmental-enforcement/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:58Z | 200 | 793 | `3afd32eb9c89a006ca621686d4da6c3570e08c2a2030cd35a8fea9791758be62` |
| `bureau_accounts/020/alcohol-and-tobacco-tax-and-trade-bureau.json` | https://api.usaspending.gov/api/v2/agency/020/sub_components/alcohol-and-tobacco-tax-and-trade-bureau/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:47Z | 200 | 740 | `bec04fe3566840ca4664af1a06a8fd92988cffd371250338c000926e3c2dc5ea` |
| `bureau_accounts/020/financial-crimes-enforcement-network.json` | https://api.usaspending.gov/api/v2/agency/020/sub_components/financial-crimes-enforcement-network/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:45Z | 200 | 723 | `ee053124b8c383d864d5cd1ce288dd0788b8bdd6a31d347de7d22f3a56e986ea` |
| `bureau_accounts/036/benefits-programs.json` | https://api.usaspending.gov/api/v2/agency/036/sub_components/benefits-programs/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:26Z | 200 | 3774 | `a0be4ec35eb8fb813025ea0f9c3c4a808f929f3cecf431f47a03cc0dd0a0834d` |
| `bureau_accounts/036/veterans-health-administration.json` | https://api.usaspending.gov/api/v2/agency/036/sub_components/veterans-health-administration/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:13Z | 200 | 2978 | `62e4cb0a8f0e3a15c965b0919b41d4a960bb9c8be80427fd31691d61dbb917a4` |
| `bureau_accounts/069/pipeline-and-hazardous-materials-safety-administration.json` | https://api.usaspending.gov/api/v2/agency/069/sub_components/pipeline-and-hazardous-materials-safety-administration/?fiscal_year=2026&limit=100 | 2026-09-17T16:23:42Z | 200 | 1972 | `f854912a2e271999de0c22ce095d4916d4abc72bc1e795febde0132544a37038` |
| `bureau_accounts/070/cybersecurity-and-infrastructure-security-agency.json` | https://api.usaspending.gov/api/v2/agency/070/sub_components/cybersecurity-and-infrastructure-security-agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:19Z | 200 | 1686 | `56c2d1ae6d962ca1ecece02e31e612b0b89744b650cbb7a43ee0c5eb71218cfe` |
| `bureau_accounts/070/federal-law-enforcement-training-centers.json` | https://api.usaspending.gov/api/v2/agency/070/sub_components/federal-law-enforcement-training-centers/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:23Z | 200 | 800 | `9671d373c8d3318fc948210bb048bd1fbe178f9d1ab0dc82329b8de10dddabce` |
| `bureau_accounts/086/fair-housing-and-equal-opportunity.json` | https://api.usaspending.gov/api/v2/agency/086/sub_components/fair-housing-and-equal-opportunity/?fiscal_year=2026&limit=100 | 2026-09-17T16:23:40Z | 200 | 550 | `ff08afa60409c38e495697d5d00903a98b5bed8977e45ae04e09137b50591065` |
| `bureau_accounts/089/national-nuclear-security-administration.json` | https://api.usaspending.gov/api/v2/agency/089/sub_components/national-nuclear-security-administration/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:10Z | 200 | 1185 | `c04807290c227145ff92f7f56dffd495e54f70f9d095a199703b1b823d014213` |
| `bureau_accounts/097/air-force.json` | https://api.usaspending.gov/api/v2/agency/097/sub_components/air-force/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:51Z | 200 | 5580 | `6334f646a59541a6bf2be3a6a7859adeb6700b0e224b93615de653f86e9050c3` |
| `bureau_accounts/097/army.json` | https://api.usaspending.gov/api/v2/agency/097/sub_components/army/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:49Z | 200 | 6698 | `dd45ced5a9cf369ff799eee29eef38ebc0205611e8fb7fc7de77f1c71fc910e8` |
| `bureau_accounts/1100/council-of-economic-advisers.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/council-of-economic-advisers/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:41Z | 200 | 545 | `4a6d89d4c425d8f92632155fda9371a94a40133aa91bf64dbfe64ba405194f66` |
| `bureau_accounts/1100/national-security-council-and-homeland-security-council.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/national-security-council-and-homeland-security-council/?fiscal_year=2026&limit=100 | 2026-09-17T16:23:45Z | 200 | 573 | `a2bfad79cc1890a3f5d99409dafae120c76df1ad05791896c5e32601e0867221` |
| `bureau_accounts/1100/office-of-administration.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/office-of-administration/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:43Z | 200 | 725 | `d2d2f39649696720f9cf94d152f11fcde1a795d869fecc7c3fce19e0e4c683db` |
| `bureau_accounts/1100/office-of-national-drug-control-policy.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/office-of-national-drug-control-policy/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:39Z | 200 | 793 | `321ce46e2433bfc34249e71eed1af403a36269e748e608462ba31e458358c424` |
| `bureau_accounts/1100/office-of-science-and-technology-policy.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/office-of-science-and-technology-policy/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:36Z | 200 | 546 | `bcd7738687e0c247cdfab8f893038d25f0843b611bc718dc330ffa1ceba3105b` |
| `bureau_accounts/1100/office-of-the-united-states-trade-representative.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_components/office-of-the-united-states-trade-representative/?fiscal_year=2026&limit=100 | 2026-09-17T16:21:34Z | 200 | 1067 | `b12a58620cb5dde89782e3383173abf3c2d2a58ef0162db77d0c9635993d948d` |
| `bureau_accounts/1601/employee-benefits-security-administration.json` | https://api.usaspending.gov/api/v2/agency/1601/sub_components/employee-benefits-security-administration/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:06Z | 200 | 555 | `5145d911b41d65f816c470e1f085e042261cf2fec922ab7293988d5b08c9da25` |
| `bureau_accounts/1601/office-of-federal-contract-compliance-programs.json` | https://api.usaspending.gov/api/v2/agency/1601/sub_components/office-of-federal-contract-compliance-programs/?fiscal_year=2026&limit=100 | 2026-09-17T16:22:08Z | 200 | 563 | `87f433bb5494de17ffddbca3d85e4a139f5e8f6e1e398a3911e7cd64fe019b2c` |

### `sub_agency/` (52 files)
| File | URL | Fetched (UTC) | HTTP | Bytes | sha256 |
|---|---|---|---|---|---|
| `sub_agency/005.json` | https://api.usaspending.gov/api/v2/agency/005/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:24Z | 200 | 590 | `6c8b04cf923770a45ecfd149bf640e015ca2e92f28994ae665bcef759ccc50e9` |
| `sub_agency/012.json` | https://api.usaspending.gov/api/v2/agency/012/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:11Z | 200 | 44529 | `e99e5fcd7f4b46a30ac4a12fbd6e6d701d477fa9c74d87c4de6692d64cd9b639` |
| `sub_agency/013.json` | https://api.usaspending.gov/api/v2/agency/013/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:13Z | 200 | 6187 | `ad346ec6b7f5926ea4e9dbd16b1aac81d35e8356ad9a64dddc1983ebf938bf2f` |
| `sub_agency/014.json` | https://api.usaspending.gov/api/v2/agency/014/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:55Z | 200 | 17795 | `d0c7b421c606e2a88f3010e9926d4de95e72ec2369b3a84ea22b9e8c8948242b` |
| `sub_agency/015.json` | https://api.usaspending.gov/api/v2/agency/015/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:41Z | 200 | 47229 | `8ae919d001cacb06d033ecc949bdd77298519a41e8f569825f9e3e15cb41a8d6` |
| `sub_agency/019.json` | https://api.usaspending.gov/api/v2/agency/019/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:45Z | 200 | 33844 | `c6202db3e087e411636dbdbe5d060712438279feb3d1dcfb7e4394dde66f123e` |
| `sub_agency/020.json` | https://api.usaspending.gov/api/v2/agency/020/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:58Z | 200 | 7904 | `7c30756250cb5f2e0f4e133447fdfa7d2aaffa734a79ba299bb18b6b946e9b31` |
| `sub_agency/024.json` | https://api.usaspending.gov/api/v2/agency/024/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:53Z | 200 | 608 | `acce3f366c1e22481bdb599f5468f785a6c75a4e8b439861b1b90f61318a5656` |
| `sub_agency/025.json` | https://api.usaspending.gov/api/v2/agency/025/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:37Z | 200 | 486 | `072d1006f236854a921aba864f70e5d6bba7162b4fee700596316afdc0925e3a` |
| `sub_agency/027.json` | https://api.usaspending.gov/api/v2/agency/027/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:10Z | 200 | 460 | `6738024a5e6ba5cd856f303e25927c412869ea3fd9aebda61d8e7eb3bc0ec15f` |
| `sub_agency/028.json` | https://api.usaspending.gov/api/v2/agency/028/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:15:09Z | 200 | 631 | `75d660daf114eef85ab4560c3528339d29e217d25d90cb5d4461a68413f2c23a` |
| `sub_agency/029.json` | https://api.usaspending.gov/api/v2/agency/029/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:22Z | 200 | 455 | `f2c2554ab588eb3086395fa28333905bf7bb4ed2e8ec1e787531633aadfd5047` |
| `sub_agency/031.json` | https://api.usaspending.gov/api/v2/agency/031/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:51Z | 200 | 993 | `ed44185b8ffe657fb7686a2376415f98c777e82e001f7d41da03679ca763ddc8` |
| `sub_agency/036.json` | https://api.usaspending.gov/api/v2/agency/036/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:51Z | 200 | 13450 | `71eb365f32ccb2a15a350a0f40c0ac7f25e6e7b5103d13f5d18f57aee9f36d6b` |
| `sub_agency/045.json` | https://api.usaspending.gov/api/v2/agency/045/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:04Z | 200 | 746 | `d3b193b2c1921acb116e54b7ae546a16a21b25c91ff4adb840fcb9058463dd97` |
| `sub_agency/049.json` | https://api.usaspending.gov/api/v2/agency/049/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:46Z | 200 | 5754 | `b8d564a5a5dbf27f3e0769ec07ef14d4928e746088523170ec903019d37e5f7f` |
| `sub_agency/050.json` | https://api.usaspending.gov/api/v2/agency/050/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:15:03Z | 200 | 482 | `2fd7de2117bf4f3db1588ac079c760029a2db91d709b2d701810cfb30fec9c09` |
| `sub_agency/051.json` | https://api.usaspending.gov/api/v2/agency/051/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:12Z | 200 | 181 | `cccdf6c1534e9ab6462508225565371c77a08e42e948b866a0d7bf3986e091e3` |
| `sub_agency/054.json` | https://api.usaspending.gov/api/v2/agency/054/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:16Z | 200 | 442 | `ba61ed25af9d571b146448d41e5e63ca61f90a905823a29cda4622b3467bfd73` |
| `sub_agency/061.json` | https://api.usaspending.gov/api/v2/agency/061/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:09Z | 200 | 602 | `b62c25d8ea62274af3d53253afb3f2f451f58d6a995b85b9c034dc242127c588` |
| `sub_agency/062.json` | https://api.usaspending.gov/api/v2/agency/062/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:55Z | 200 | 181 | `16b3541450ae9b4a106dbbd08644db7a1fffc65b3894c6d128ddbc8556e326d1` |
| `sub_agency/065.json` | https://api.usaspending.gov/api/v2/agency/065/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:18Z | 200 | 456 | `87884e97d2e4e37b082772d8d16bfbc00681ec04711ddf2fcb3914b0b642f0b4` |
| `sub_agency/068.json` | https://api.usaspending.gov/api/v2/agency/068/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:02Z | 200 | 4533 | `bccc478bdec78ceb3b526ba3be7bfa72d89513c544e083bc02c76e1563f9260b` |
| `sub_agency/069.json` | https://api.usaspending.gov/api/v2/agency/069/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:48Z | 200 | 12321 | `2d339bb457eb8771a0111702ee566358c177d68c8f9a97829d5620e4dc3b61d4` |
| `sub_agency/070.json` | https://api.usaspending.gov/api/v2/agency/070/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:34Z | 200 | 17314 | `1fd6ea62a6d370e5fb148815f100cc45c7e77bed2ec6b857f65f312ec33ccfd7` |
| `sub_agency/073.json` | https://api.usaspending.gov/api/v2/agency/073/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:15:07Z | 200 | 1136 | `14f31971d7cc15c489d094cbd6dd3117db05305e24b753fb1cd55c2fae5e4059` |
| `sub_agency/074.json` | https://api.usaspending.gov/api/v2/agency/074/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:03Z | 200 | 439 | `a82022944ab9567a70028f93fe54649aa09a5ec29bd9d4f1d0ce7d8e8711cb3b` |
| `sub_agency/075.json` | https://api.usaspending.gov/api/v2/agency/075/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:31Z | 200 | 20564 | `adb15f662488ed348cddd96e808937f32358533f1ba0b9ab6e5e6e99b6daf07b` |
| `sub_agency/080.json` | https://api.usaspending.gov/api/v2/agency/080/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:29Z | 200 | 2106 | `501b018224a8cbd2334a11065aca52f2edf578caf03f6fb2b7421af6ddac9fc7` |
| `sub_agency/083.json` | https://api.usaspending.gov/api/v2/agency/083/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:08Z | 200 | 608 | `7389ea5e5de854dc457d903b2ba36dbeb95953dddd9677061d1c0249eff91350` |
| `sub_agency/086.json` | https://api.usaspending.gov/api/v2/agency/086/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:36Z | 200 | 23177 | `122312ddbf57561f05254c9349a3fb34d8fe76b6ad42bb23bc012385e67de52d` |
| `sub_agency/088.json` | https://api.usaspending.gov/api/v2/agency/088/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:33Z | 200 | 772 | `bc97c30bf304740645181b403860a435990ab3fc58f42c7762c5733d509c2160` |
| `sub_agency/089.json` | https://api.usaspending.gov/api/v2/agency/089/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:29Z | 200 | 4335 | `589fcba82edb26c451cf364f19886a404ddbd0943321394a6f8e6798ca5773a5` |
| `sub_agency/090.json` | https://api.usaspending.gov/api/v2/agency/090/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:15:05Z | 200 | 458 | `26cc4ff4f8cdf26ca387242699d59d7b5218882d633dce94b7b130dd47039647` |
| `sub_agency/091.json` | https://api.usaspending.gov/api/v2/agency/091/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:27Z | 200 | 2245 | `328387d4d8d804b7d94ed090a1cd90b599363c70d75dee5b9d6d6d6f07630c71` |
| `sub_agency/097.json` | https://api.usaspending.gov/api/v2/agency/097/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:15Z | 200 | 143911 | `fd40f7c280ee1f355c4abb93254de18617ba2e58c6eaa8c3bf927608857a8f90` |
| `sub_agency/1100.json` | https://api.usaspending.gov/api/v2/agency/1100/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:06Z | 200 | 785 | `8f9363d9e2b5e1ac6152d4bc72e999e5b38a3cdbff506e72ecd0dd4e80d4772b` |
| `sub_agency/1125.json` | https://api.usaspending.gov/api/v2/agency/1125/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:57Z | 200 | 435 | `c8d234c9d71bd4414fcb6ab10cb8f83b8e1b72096d62ec5a694102170114aee4` |
| `sub_agency/1601.json` | https://api.usaspending.gov/api/v2/agency/1601/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:43Z | 200 | 4727 | `16bb58f61498358a0a53dfb0e1d43d93ce86c038925b386a9edd739b89011cd7` |
| `sub_agency/1602.json` | https://api.usaspending.gov/api/v2/agency/1602/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:59Z | 200 | 483 | `b1a10c1706e33762fa3e0a42bebea67b37a785fbd0b3a7cc65697fc2c5a249ea` |
| `sub_agency/309.json` | https://api.usaspending.gov/api/v2/agency/309/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:05Z | 200 | 466 | `2818e74d7142ce1449e79d3c9d8fffd2a62716721d0f81a30222d669eb81305b` |
| `sub_agency/339.json` | https://api.usaspending.gov/api/v2/agency/339/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:13:07Z | 200 | 475 | `b0c9c3e67e151c93757377b599adf28cb999b360951dd04ff26e9b2b7600beb5` |
| `sub_agency/360.json` | https://api.usaspending.gov/api/v2/agency/360/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:14Z | 200 | 458 | `283466efedc01cf235da4575d5a19de75e6f78f39767f42d19b70e4186db1a25` |
| `sub_agency/389.json` | https://api.usaspending.gov/api/v2/agency/389/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:26Z | 200 | 474 | `186c74f3257705cd69d3d38aa98c65c7ee85c430f63e1db51b1a514ea86d1cfc` |
| `sub_agency/394.json` | https://api.usaspending.gov/api/v2/agency/394/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:35Z | 200 | 181 | `f3f957067a91461a9ba50cfb14853769f0dbc1c3f5464fd99a365de88418cb71` |
| `sub_agency/417.json` | https://api.usaspending.gov/api/v2/agency/417/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:39Z | 200 | 478 | `6fe9b36c112af0d251087b1346692240a6de6f200cc5fab30d0dd57da60bedf2` |
| `sub_agency/418.json` | https://api.usaspending.gov/api/v2/agency/418/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:41Z | 200 | 762 | `382340266f04c24ee0f1e64b33a6dfb64d1df0861c6fa512dfd0d5e7d179db07` |
| `sub_agency/420.json` | https://api.usaspending.gov/api/v2/agency/420/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:43Z | 200 | 469 | `24c05702f3cfd44c9a02229ddbb8f7b013ee689f4569b101725730f4759fd613` |
| `sub_agency/421.json` | https://api.usaspending.gov/api/v2/agency/421/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:45Z | 200 | 181 | `25f19ef789b1aa42da8b2c4cbfce54e1df2aa8b3f77aa6992be5ec2a8b66feb0` |
| `sub_agency/424.json` | https://api.usaspending.gov/api/v2/agency/424/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:48Z | 200 | 472 | `8e9f73f34b0c922ce9d63739dbc6b72b95df6c49fd8ce276c8e3dd5cc4ebeef4` |
| `sub_agency/525.json` | https://api.usaspending.gov/api/v2/agency/525/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:14:00Z | 200 | 471 | `5dd6c7c1b11142ff2a70a4405d4e9baa2707d2bf0e40b5cdd84a17cd52d05329` |
| `sub_agency/535.json` | https://api.usaspending.gov/api/v2/agency/535/sub_agency/?fiscal_year=2026&limit=100 | 2026-09-17T16:15:01Z | 200 | 181 | `81e66c28e58cccc0c97dbb27d67f13b5540c590f27038cc13942c6085b952e02` |
