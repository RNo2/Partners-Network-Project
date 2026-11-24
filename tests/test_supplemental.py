import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from partner_network.supplemental import compare_meals,clean_health,provider_kind
from partner_network.analytics import coverage,nearby_pairs
from streamlit.testing.v1 import AppTest

ASSETS=Path('public_data/processed')

def test_meal_reconciliation_and_classification():
    summary=json.loads((ASSETS/'supplemental_audit.json').read_text())
    assert summary['new_providers']==0 and summary['substantive_provider_differences']==0
    f=pd.read_parquet(ASSETS/'partners.parquet');p=f[f.partner_id.str.startswith('PHL:')]
    assert len(p)==404 and p.partner_id.is_unique
    assert p[p.source_category_type=='Senior Meal Site'].partner_type.eq('senior meal site').all()
    assert p[p.source_category_type=='Public Benefits'].partner_type.eq('public benefits').all()
    assert len(p[p.partner_type=='public benefits'])==26
    a=pd.DataFrame([{'objectid':'1','site_name':'A','x':'-75.12345678','hours_mon_start1':'10:00'}])
    b=pd.DataFrame([{'objectid':'1','site_name':'A','x':'-75.12345678001','hours_mon_start1':'10:00:00'}])
    diff,new,removed=compare_meals(a,b);assert diff.equivalence.eq('format/precision only').all()
    b.loc[0,'site_name']='Changed name';assert compare_meals(a,b)[0].equivalence.eq('substantive difference').any()

def test_benefits_never_count_as_provider(provider):
    office=provider.copy();office.loc[0,'partner_type']='public benefits'
    assert nearby_pairs(pd.concat([provider,office],ignore_index=True),1).empty
    units=pd.read_parquet(ASSETS/'geographic_units.parquet');units=units[units.geographic_resolution=='county']
    result=coverage(units,office,1)
    assert result.share_inside.eq(0).all() and result.nearest_straight_line_km.isna().all()

def test_tract_reference_and_real_relationship():
    ref=pd.read_parquet(ASSETS/'tracts_2010_reference.parquet')
    current=pd.read_parquet(ASSETS/'geographic_units.parquet')
    assert len(ref)==384
    assert len(current[current.geographic_resolution.eq('tract')])==779
    phl=current[(current.geographic_resolution=='tract') & (current.county=='Philadelphia County')]
    assert len(phl)==408
    rel=pd.read_parquet(ASSETS/'tract_relationships_2010_2020.parquet')
    assert set(rel.GEOID_TRACT_10)==set(ref.GEOID10)
    assert set(rel.GEOID_TRACT_20)==set(phl.geographic_id)
    assert len(rel)==508
    assert not any('weight' in c.lower() for c in rel)

def test_health_sentinels_and_separate_periods():
    health=pd.read_parquet(ASSETS/'health_of_city.parquet')
    catalog=pd.read_parquet(ASSETS/'health_metric_catalog.parquet')
    assert len(health)==5005 and len(catalog)==47
    for c in ['metric_value','lower_bound','upper_bound']:assert not health[c].eq(-99999).any()
    assert health.metric_value.isna().sum()==346
    assert health.scope.eq('Philadelphia only').all()
    assert 'tract' not in set(health.geographic_resolution)
    assert health[health.metric_name=='percent_of_burdened_renters'].year.eq('2017-2021').all()
    assert health[health.geography=='ZCTA'].geographic_id.str.fullmatch('[0-9]{5}').all()
    unsafe=health.quality_flag.str.contains('Suppressed|Unreliable')
    assert health.loc[unsafe,'metric_value'].isna().all()
    regional=pd.read_parquet(ASSETS/'community_indicators.parquet')
    assert len(regional)==7796 and not regional.indicator_id.str.startswith('HOTC').any()

def test_health_widgets_and_county_scope(monkeypatch):
    monkeypatch.delenv('SHARE_INTERNAL_MODE',raising=False)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'public_app.py'),default_timeout=90).run()
    app.radio(key='public_section').set_value('Research tools').run()
    app.sidebar.radio[0].set_value('Community Need').run()
    assert not app.exception
    assert app.selectbox(key='need_health_metric').value=='percent_below_poverty'
    app.selectbox(key='need_health_metric').set_value('percent_unemployed').run()
    assert not app.exception
    app.selectbox(key='need_health_metric').set_value('percent_of_burdened_renters').run()
    assert not app.exception
    app.selectbox(key='need_health_metric').set_value('age_distribution').run()
    assert not app.exception
    app.sidebar.multiselect(key='filter_county').set_value(['Montgomery County']).run()
    assert not app.exception
    assert any('does not cover' in info.value for info in app.info)
