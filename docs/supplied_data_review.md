## Supplementary dataset review · November 2026

### Census_Tracts_2010.csv

384 unique Philadelphia 2010 tract identifiers and reference attributes, **not polygon geometry**. The existing 2024 TIGER layer (2020 tract geography) has 408 Philadelphia tracts; the three-county total remains 779. There are 363 common IDs, 21 2010-only IDs and 45 current-only IDs. Equal identifiers do not establish unchanged boundaries.

The official Census Bureau [2010–2020 tract relationship table for Pennsylvania](https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_st42.txt) supplies 508 Philadelphia relationships covering all 384 old and 408 current IDs. It is included as a reference with land/water overlap areas; **these are not population weights**. No counts or rates have been interpolated, and no newer boundary has been replaced.

A documented crosswalk/allocation method would be needed to compare actual 2010 tract observations on current boundaries. The supplied health observations have no tract-level geography, so they require no such conversion. The tract CSV adds a legacy-ID reference and audit, not new current community estimates.

### free_meal_sites (3).csv

All **404** source object IDs match the already integrated official Philadelphia feed. Field-by-field comparison found **zero substantive differences** and **1,106 formatting/precision differences**, confined to HH:MM versus HH:MM:00 and coordinate floating-point precision (tolerance 0.0000001 degrees). Names, addresses, affiliations, status, exception text and schedule semantics match. No provider or schedule records were appended or replaced.

Original publisher categories are now retained explicitly: **300 Food Sites, 51 General Meal Sites, 27 Senior Meal Sites, 26 Public Benefits locations**. Community fridges remain distinct within Food Sites. No non-Share source label is treated as proof of independence. Benefits-assistance locations can be displayed as context but are excluded from provider coverage, nearby-provider pairs, scheduled food-access calculations and provider summary counts, even when enabled on the map. Exact shared-address candidates remain separate for review.

### health_of_the_city.csv

The supplied **5,005 observations across 47 indicators** were reconciled against the complete, paginated [official public API](https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/health_of_the_city/FeatureServer/0/query?where=1%3D1&outFields=*&f=json). The public-source schema and all observations match after numeric/null formatting normalization. This is a new, separate Philadelphia-only dataset, not a replacement for ACS 2024.

All 47 indicators are cataloged with source, periods, unit interpretation, resolution, row count, missingness and analytical role. Five priority measures are available in Community Need and as separate historical context in Opportunity Explorer:

- Poverty: county historical observations and ZCTA 2017–2021 estimates, with subgroup definitions retained.
- Unemployment: county, 2017–2021 ACS five-year estimates; source age universe >15 retained.
- Housing cost burden: the publisher's **burdened-renter** measure, county, 2017–2021 ACS public-use microdata; it is not an all-household measure.
- Population counts by age: county, 2021 resident population estimates; includes a source total and age/sex/race subgroups.
- Population composition: county and ZCTA, 2017–2021 ACS, expressed as percentages, not counts.

The 706 observations across these five indicators are historical context. The remaining indicators are accessible as health context, without invented need weights or opportunity scores. No clinical/health outcome is treated as evidence of food insecurity by itself.

Geographic coverage is **4,353 county, 360 planning-district and 292 ZCTA observations**, all Philadelphia scope. These are not census tract observations and ZCTAs are not postal ZIP codes. The UI maps county observations only to Philadelphia's county outline. ZCTA/planning-district comparisons use charts and tables; matching-vintage subcounty polygons are not yet supplied or verified. No district or ZCTA value is spread across current tracts.

**Missingness:** 336 metric-value sentinels and 4,834 sentinels in each uncertainty-bound column are converted to missing. Suppressed/unreliable source quality flags also withhold numeric observations, yielding 346 missing metric values overall. Zero is retained when it is a genuine source observation. Bounds, uncertainty types, reporting-period strings, quality flags and all source strata remain available. No pooled rates, subgroup sums, cross-period averages or fabricated denominators are calculated.

The 7,796 existing regional ACS/Feeding America observations, 779 tract polygons, county outlines, original food-provider identities and 585 structured schedule windows remain intact. The machine-readable supplemental audit, 47-indicator catalog and provenance manifest are shipped with the release. Original supplied files and full official responses remain in local raw storage and are excluded from Git.
