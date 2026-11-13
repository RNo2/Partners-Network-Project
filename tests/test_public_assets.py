"""Validation of actual acquired public assets; no synthetic public release records."""
from pathlib import Path
import json
import pandas as pd
from partner_network.public_store import PublicStore

ROOT=Path('public_data/processed')
def test_release_counties_and_identifiers():
    g=pd.read_parquet(ROOT/'geographic_units.parquet')
    tracts=g[g.geographic_resolution=='tract']
    assert tracts.geographic_id.is_unique
    assert set(tracts.geographic_id.str[:5])=={'42045','42091','42101'}
    a=pd.read_parquet(ROOT/'community_indicators.parquet')
    acs=a[a.geographic_resolution=='tract']
    assert set(acs.geographic_id)<=set(tracts.geographic_id)
    assert acs.margin_of_error.notna().any()
    assert a[a.indicator_name=='Food insecurity rate'].geographic_resolution.eq('county').all()
    assert a.indicator_id.is_unique

def test_release_privacy_and_source_traceability():
    s=PublicStore();p=s.read('partners')
    assert p.partner_id.is_unique and p.source.notna().all()
    assert not p.site_name.str.contains('SYNTHETIC',case=False).any()
    assert set(p.network_membership)<= {'share','external','unknown'}
    for private in ['distribution_records','partner_assessments','operational_constraints']:
        assert s.read(private).empty
    assert not hasattr(s,'import_data') and not hasattr(s,'save_scenario')
    manifest=json.loads((ROOT/'manifest.json').read_text())
    assert manifest and all('source' in record for record in manifest)

def test_gtfs_and_retail_assets():
    stops=pd.read_parquet(ROOT/'gtfs_stops.parquet')
    assert stops.stop_lat.between(39,41).all() and stops.stop_lon.between(-77,-74).all()
    assert set(stops['mode'])=={'bus','rail'}
    for mode in ['bus','rail']:
        times=pd.read_parquet(ROOT/f'gtfs_{mode}_stop_times.parquet')
        trips=pd.read_parquet(ROOT/f'gtfs_{mode}_trips.parquet')
        assert set(times.trip_id)<=set(trips.trip_id)
        assert set(times.stop_id)<=set(stops[stops['mode']==mode].stop_id)
    retail=pd.read_parquet(ROOT/'usda_general.parquet')
    assert retail.CensusTract20.str.len().eq(11).all()
    assert set(retail.CensusTract20.str[:5])=={'42045','42091','42101'}
