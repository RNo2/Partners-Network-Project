Public deployment: https://partners-network-tool-z7hbeemtmhnnrvhuvoxpya.streamlit.app/

Verified anonymously on November 13, 2026. Both default entrypoints now use public assets. See verification.md for the live checks.

# Streamlit Community Cloud deployment

Target repository: https://github.com/RNo2/Partners-Network-Project

Entry point: **public_app.py**, branch **main**, Python **3.12**.

1. Sign into https://share.streamlit.io/ using the GitHub account with access to RNo2/Partners-Network-Project.
2. Authorize Streamlit's GitHub integration if prompted. Create app → select this repository, main, public_app.py.
3. In Advanced settings select Python 3.12. No secrets, APIs, paid services, or credit card are needed for this app.
4. Deploy, set app sharing to public, then open the resulting `*.streamlit.app` URL in a private/incognito browser to confirm no login is required.
5. Check Overview, all county filters, Community Need, provider map, schedules and SEPTA layers. Do not call the deployment verified until the actual generated URL has been opened.

The public entrypoint forces public mode and uses `PublicStore`, which reads only processed Parquet assets. It does not initialize SQLite or expose a mutation API. The internal entrypoint is `internal_app.py` and must never be selected for public hosting. Both `app.py` and `public_app.py` default to read-only public assets, protecting against an accidental default entrypoint selection. Do not upload internal databases, raw uploads, unpublished assessments, secrets, or test/browser databases to GitHub.

The ~22 MB processed release is prebuilt; visits do not trigger downloads or ETL. Read caches use asset revision. Geometry is simplified for display; full raw source is retained locally during refresh. GTFS stop-times are stored but are not loaded for ordinary map browsing. Initial geographic analysis can take several seconds; repeat views are cached.

## Reproduce and refresh

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/refresh_public_data.py
.venv/bin/python -m pytest -q
.venv/bin/streamlit run public_app.py
```

The refresh caches raw source responses under `public_data/raw/`. To retrieve a new vintage, archive that directory outside the repository, update explicit source/vintage configuration in the adapter and rebuild from an empty raw cache. This release is deliberately pinned; it never silently swaps ACS years or treats a new directory retrieval as verified current operation. Review the manifest and changed source schemas before committing updated processed assets. `provider_extracts.py` contains documented, reviewed factual transcription of the county's March 2026 PDF; a changed PDF must be reviewed and updated manually before claiming it is a new release.

Public hosting approval is supplied by the user's V1.0 request. Account sign-in and Community Cloud GitHub authorization still require the account owner if no authenticated session is available to the agent. No credentials should be sent through chat.
