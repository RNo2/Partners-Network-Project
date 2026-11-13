## Live deployment verified · November 13, 2026

Public application: https://partners-network-tool-z7hbeemtmhnnrvhuvoxpya.streamlit.app/

Verified in a fresh anonymous Chromium session, with TLS validation enabled. All ten sections loaded without application exceptions. Actual-data need maps, provider maps and SEPTA layers rendered. All three county filters updated the displayed Share-affiliated source-record counts (Delaware 16, Montgomery 0, Philadelphia 58). A zero affiliation count reflects absence of explicit Share attribution in these public sources, not proof that Share has no services there.

The first live check found that hosting had selected `app.py`, which initially opened the internal empty-data workspace. Commit `22ea497` corrected this: both `app.py` and `public_app.py` now default to the populated public, read-only asset backend. Internal SQLite workflows require the separate explicit `internal_app.py` entrypoint. A new regression test enforces the safe default. The full suite passes **30 tests** (five non-failing dependency deprecation warnings), also verified from the release checkout.

No public administrative upload controls were present. Public data and methodology were accessible without accounts. Actual hosted screenshots and the verification summary are in `docs/screenshots/live/` and `docs/live_verification.json`. Remaining analytical limitations are unchanged: source-published hours are not independently verified, some coordinates remain withheld, and travel-time routing and internal organizational assessments are not inferred.

The historical verification records below describe earlier milestones; their deployment-pending statements are superseded by this live verification.

---

# Verification record

Executed November 13, 2026 in Python 3.12 on Linux, with Streamlit 1.67.0. Exact project dependency versions are in `requirements.lock`.

## Automated tests

Command: `.venv/bin/python -m pytest -q`

**26 passed**, final run 6.46 seconds. Five non-failing warnings: one inherited pytest/AnyIO compatibility deprecation and four Shapely transform API deprecations. No test failures remain.

Coverage includes:

- CSV and XLSX parsing, identifier preservation, column mapping, type suggestions and missing columns.
- GeoJSON/GeoPackage reading, explicit layer selection and invalid polygon checks.
- Invalid dates, coordinates, ZIP codes, negative numbers, duplicate IDs, missing values and unmatched partners.
- Warning acknowledgement, append/update/replace behavior, duplicate-content prevention, retained raw files, database reopen and backup restore.
- Foreign-key protection and rollback of overlapping reporting periods, including rollback of import history.
- Public-label filtering, internal-page restrictions and assessment approval/version validation.
- Great-circle distance, explicit provider filters, actual polygon matching and spatial-index area selection.
- Compatible indicator aggregation, weighted rates, missing denominators and incompatible reporting-year refusal.
- Multiple weekly windows, unioned scheduled hours, nonweekly exclusions, missing schedules, effective dates and nearby overlap.
- Exact-interval distribution totals and missing-metric preservation.
- Configurable scoring, direction, normalization, invalid weights, approval requirement, contribution explanations, missing-data policies, repeatability and alternative configurations.
- Budget arithmetic and persisted staff scenarios.
- All ten pages under Streamlit AppTest with empty and synthetic populated temporary databases, persistent provider filters, public-mode restrictions and visibility of area-only operational constraints.

## Real Chromium browser checks

Local Playwright drove `/usr/bin/chromium`, not a simulated browser. Tests used `work/browser.sqlite`, containing explicitly synthetic browser fixtures; these are not actual Share providers, geographic units, estimates or findings.

- Navigated all ten pages with empty data and then all ten with populated fixtures; no application exception or JavaScript page error observed.
- Uploaded a synthetic CSV through the actual file picker, reviewed automatic column mappings and validation, entered import provenance, confirmed the transaction and observed the committed import.
- Opened a new browser session and confirmed the committed provider persisted.
- Downloaded the blank provider template and checked its filename.
- Rendered an offline need polygon map, the Share/external landscape, a weekly-hours heatmap, a selected-day map and populated distribution displays.
- Browser network monitoring observed **no external requests** during the application checks.
- Screenshots were inspected locally. Full upload/download automation for every format, browser-driven scenario editing and browser-driven assessment imports were not performed; parsers and the corresponding backend validation/persistence were covered by automated tests.

Intermediate browser scripts, logs and screenshots remain in ignored `work/`. They are not shipped datasets. The live/default database has **zero imported records**. Production SQLite integrity check returned `ok` with zero foreign-key violations.

## Startup and code checks

- Started the real Streamlit process on loopback port 8501; `/_stcore/health` returned `ok`.
- Python compileall completed for the app, backend and tests.
- Reviewed the modular source tree and privacy boundaries. No commit, push or deployment was performed.

## Implemented versus pending

| Capability | Status |
|---|---|
| Local persistence, provenance, raw files, transactional mapping/import workflow | Functional and tested |
| Nine blank dataset templates and comprehensive field dictionary | Available |
| Share/external/unknown landscape and active-provider polygon coverage | Functional with supplied coordinates and boundaries |
| Need comparison, rate/count separation and compatible weighted aggregation | Functional with supplied indicators |
| Weekly windows, source verification filters and nearby overlap | Functional with verified weekly schedules |
| Distribution summaries by exact interval with completeness counts | Functional with supplied Share activity |
| Partner criteria, versioned assessment records and qualitative notes | Framework functional; real criteria/ratings await Share |
| Deep/Wide/Optimization budget-and-evidence proposals | Functional comparison foundation; not impact optimization |
| Area comparisons and operational-constraint records | Functional evidence framework; no invented opportunity categories |
| Configurable area scoring | Tested backend API only; UI/approval workflow and persistent scored runs pending |
| Official external provider inventories, ACS, food insecurity and transit integration | Await verified source data/adapters; candidates documented, none imported |
| Walking/transit routing, capacity modeling, hubs and marginal-impact estimation | Not implemented; only imported measurements supported |
| Multiuser authentication, public deployment, public dataset publishing pipeline | Not implemented or authorized; public preview uses a separate database by default |

This is a functional landscape and strategic-planning foundation, not a validated organizational allocation model. All substantive strategic conclusions await real data and staff review.

# V1.0 real-data release verification · November 13, 2026

This supersedes the original empty-foundation status for the **public** release. Internal `data/network.sqlite` remains separate and empty.

- **29 tests passed**, five non-failing dependency deprecation warnings, final run 4.96 seconds. Three new asset tests validate actual county/tract identifiers, ACS MOEs, source traceability, absence of synthetic release providers, mutation-free public backend, GTFS references and regional retailer geography.
- Public AppTest executed all ten sections with actual release data, without exceptions.
- Real Chromium visited all ten public sections, verified no file-upload controls and verified that selecting Delaware County changes the Share-provider count to 16. No browser page errors or external data requests were observed.
- Browser navigation/rendering measured 0.22–8.51 seconds per section in this environment. The cold accessibility view includes provider analysis, transit infrastructure and schedules. Timing is observational, not a Community Cloud SLA.
- Public Streamlit process resident memory after browser traversal was approximately **294 MiB**. Processed asset footprint is approximately **22 MB**. Deployment-host performance is not yet measured.
- Actual-data screenshots: `docs/screenshots/overview.png`, `community-need.png`, `providers.png`, `septa.png`, and `delaware-filter.png`.
- No synthetic records, internal distribution data, unpublished assessments, passwords or account credentials are in processed public assets. Failed Census geocodes and geographic conflicts are retained as missing map coordinates. 471 directory records comprise 445 food-resource and 26 benefits-assistance entries; these are **not** asserted unique or currently active providers.
- The official Community Cloud page was reachable through the TLS-valid HTTP client. The isolated automated Chromium browser encountered the environment proxy CA trust error when opening the hosting control panel; no TLS verification was disabled. No authenticated Community Cloud hosting session or deployment tool is available to this agent. The account owner must connect the published repository and deploy `public_app.py`.

**Deployment verification remains pending. A successful GitHub push is not a public Streamlit deployment. No public app URL is claimed or guessed.**

## Supplied-export integration checks · November 2026

The full suite passes **35 tests** after this integration, with the same five non-failing dependency deprecation warnings. New checks cover meal semantic/format differences, preservation of provider categories, exclusion of benefits offices from coverage, official tract relationship coverage, unchanged primary geography/indicator counts, sentinel/quality handling, original health reporting periods, and Philadelphia-only UI scope.

Real Chromium exercised unemployment, renter housing burden, population counts and poverty controls, ZCTA comparisons without false tract mapping, non-Philadelphia filter withholding, and the source/audit documentation. No browser page errors were observed. SHA-256 comparisons confirmed that `geographic_units.parquet`, `community_indicators.parquet`, and `operating_schedules.parquet` remain byte-identical to the previous release. Supplemental reconciliation was rerun without increasing provider or observation counts. The build validates staged output before replacing release assets.
