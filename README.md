# Regional Food Access · Partner Network Intelligence V1.0

**[Open the public application](https://partners-network-tool-z7hbeemtmhnnrvhuvoxpya.streamlit.app/)** · anonymous access and live workflows verified November 13, 2026.


Public, read-only Streamlit application for Philadelphia, Montgomery and Delaware counties, Pennsylvania. This is an independent exploratory prototype, not an official Share Food Program assessment. No Share logo or implied endorsement.

## Public release

The app opens on **Find food**. Choose a county or enter a ZIP code, site name,
or street address. Listings show directions and available source hours. Check
with the provider before traveling. **County snapshot** shows county-level food
insecurity and directory counts. **Research tools** holds the detailed maps,
comparisons, and source documentation.


```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run public_app.py
```

Use **public_app.py** as the Streamlit Community Cloud entrypoint. It forces the read-only public asset backend. `internal_app.py` exposes the separate internal SQLite import/assessment/scenario workflows. Visitors can browse without an account, API key, or subscription. Public evidence exports are available in Research tools.

Real versioned public assets include 779 TIGER census tracts, 7,790 ACS 2024 five-year observations with source MOEs, six official Feeding America county observations, 471 directory source records (445 food-resource records plus 26 separately classified benefits-assistance offices), regional USDA 2025 SRAM measures, and SEPTA bus/rail GTFS infrastructure and schedules. Source records are not deduplicated unique active organizations. Coordinates with failed geocodes or county conflicts are withheld, not invented.

Research tools provides source-attributed maps, tract indicators, provider inventories, published schedules, nearby pairs, SEPTA infrastructure, and strategy evidence comparisons. The internal workspace has ten sections, including staff-only assessments and data management. No internal volumes or assessments are present. Those sections explain the missing organizational inputs. No opportunity scores, capacity estimates or optimization results are fabricated.

See [source status](docs/public_data_status.md), [methodology](docs/methodology.md), [deployment instructions](docs/deployment.md), and [verification record](docs/verification.md). Actual application screenshots are in [docs/screenshots](docs/screenshots). The machine-readable manifest and selected ACS table definitions are in `public_data/processed/`.

## Refresh and test

```bash
.venv/bin/python scripts/refresh_public_data.py
.venv/bin/python -m pytest -q
```

Refresh uses cached raw public sources and explicit vintage adapters. To fetch a new snapshot, archive the raw cache and rebuild after reviewing upstream schema/vintage changes. Source-published facts in Delaware County's PDF are explicitly transcribed in `provider_extracts.py`; review a newer PDF before changing its vintage. Unparsed or irregular schedules remain source text. Do not silently interpret them as weekly windows.

Production reads cached ~22 MB processed public assets, never internal SQLite. There is no import or scenario-save mutation API on `PublicStore`. Raw downloads, internal databases, credentials and test fixtures are excluded from deployment. Community Cloud account sign-in and GitHub authorization are external account-owner steps when no authenticated session is available; a GitHub push alone is not a deployed app.

## Internal workspace reference

## Install and launch

Python 3.11+ recommended. From the project root:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run internal_app.py
```

Open http://127.0.0.1:8501. The default database is `data/network.sqlite`; set `SHARE_DB` to a controlled local path to select another database. Core analysis requires no internet after dependency installation. Keep loopback binding for this unauthenticated local release.

## Data workflow

1. In Data Management select a category and download its blank CSV and dictionary. All blank templates also live in `templates/`.
2. Upload CSV/XLSX or geographic GeoJSON/GeoPackage (25 MiB maximum). Excel worksheets and GeoPackage layers can be selected. Geographic uploads become geographic-unit records after mapping their identifiers, names, source and vintage; CRS is required.
3. Map source columns; identifiers are read as text to retain leading zeros. Supply required source and visibility fields in your file. See the field dictionary and schema enums.
4. Download and fix validation errors. Acknowledge warnings, specify source and choose append, update or replace; explicitly confirm before import.
5. Append new IDs; update existing IDs only. Replace synchronizes a category but cannot remove referenced partners. Repeat content is blocked. All imports are atomic; a failure rolls back the entire upload. Analyses reread current data on every interaction, so no stale cache remains.
6. Import partners before schedules, distributions, routes or assessments. Import approved criteria before source-provided assessment ratings. Unknown membership/status is permitted but never treated as Share/active.

Each table retains current records, import provenance and original uploaded bytes in the database. Earlier imports can be downloaded internally. Import history covers accepted commits; failed validation reports are downloadable before commit. Affiliation strings are retained as supplied; entity reconciliation and a separate affiliation crosswalk are future work.

## Interpretation and safeguards

Ten navigation sections expose need, landscape, accessibility, Share activity, assessments, opportunity comparisons, scenarios, imports and methods. Sidebar filters persist across pages and apply to all provider-linked calculations; geographic filters separately select actual supplied boundaries. Provider types are free text. There are no approved default thresholds or weights. User-selected radii are screening assumptions. No map estimates walking/transit time. Missing indicators remain missing, not zero. Full definitions and limitations: `docs/methodology.md`.

Weekly schedule calculations require verified, effective, weekly records and merge overlapping windows. Nonweekly windows remain visible. Distribution intervals are preserved exactly, and reporting completeness accompanies totals. Scenario budgets are arithmetic checks of staff proposals, not optimized recommendations. Partner reviews remain separate from need and cannot produce generated scores.

## Backups and privacy

Use Data Management → Download consistent SQLite backup. It uses SQLite's backup API and includes raw uploads, scenarios and current tables. Store backups securely. To restore, stop Streamlit, retain an existing backup of the current database, copy the reviewed backup to the configured path, and restart. Do not copy a live WAL database file alone.

Use `public_app.py` for the read-only public release. It reads only reviewed public Parquet assets, never internal databases or their raw imports. The internal workspace requires `internal_app.py`; do not deploy that entrypoint.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Tests use temporary databases and explicitly synthetic fixtures, never actual Share findings. See `docs/verification.md` for executed checks and scope.

## Structure and extension

- `app.py`: navigation and UI only; application services live in `partner_network/`.
- `schema.py`: import contracts, identifier fields and validation enumerations.
- `ingestion.py`: parsing, column mapping and validation.
- `storage.py`: normalized category tables, foreign keys, transactional upserts, raw versions, backups and migration ledger.
- `analytics.py`: distances, polygon coverage, need, weekly windows, overlap, interval-level distributions and scenario budgets.
- `prioritization.py`: opt-in approved area scoring and sensitivity API; no default weights and no UI ranking.
- `visualization.py`: offline interactive maps and weekly heatmap.
- `docs/`: source status, methodology, implementation boundaries and verification.

To introduce a new dataset, add a schema contract, validation rules and a migration, then pure analytical functions and tests before UI exposure. Source-specific public adapters are intentionally pending verification; no candidate source is claimed as already integrated. Dependencies use supported version ranges; a tested environment freeze is supplied for reproduction.

## Needed next

Share's partner IDs, addresses/coordinates, affiliation/status, verified schedules, exact-period activity and approved disclosure policy. Public providers need source, permission to reuse and last verification. Need estimates require geographic IDs, unit, denominator where available, year, methodology and compatible boundaries. Assessments require finalized criteria and approval governance; scenario feasibility requires food/warehouse/transport/staff/relationship constraints.

Next milestone: reconcile one verified public provider export with the Share inventory, load a compatible boundary/ACS release, and validate the area and schedule comparisons with staff. Authenticated governance, source adapters, routing, capacity optimization, hub scenarios and approved scoring UI are not complete.

## Supplementary public exports

See [supplied-data reconciliation](docs/supplied_data_review.md). The new Health of the City panel is separate Philadelphia-only context in Community Need and Opportunity Explorer. It preserves source years, subgroup definitions, uncertainty, quality flags and missing values. Current three-county ACS/geography are unchanged.

To reproduce the supplemental reconciliation after a base refresh, supply the three original CSV paths:

```bash
.venv/bin/python scripts/integrate_supplied_data.py --tracts /path/Census_Tracts_2010.csv --meals '/path/free_meal_sites (3).csv' --health /path/health_of_the_city.csv
```

The script caches originals in ignored `public_data/raw/`; subsequent runs can omit the arguments. It downloads the paginated official health source and Census tract relationship table for verification. It refuses unmatched or substantively different meal records rather than silently appending/overwriting them. New source versions require review; provider names alone are never merge keys. Run the complete test suite and review the supplemental audit before publishing changed assets.
