import json
import numpy as np
import pandas as pd
import pytest
from conftest import frame
from partner_network.analytics import *
from partner_network.prioritization import score,sensitivity
from partner_network.visualization import landscape_map


def test_distance_filter_pairs(provider):
    assert haversine(40,-75,40,-75)==0
    assert float(haversine(0,0,0,1))==pytest.approx(111.195,rel=0.001)
    other=provider.copy();other.loc[0,'partner_id']='TEST-002';other.loc[0,'longitude']='-75.001';other.loc[0,'network_membership']='external'
    partners=pd.concat([provider,other],ignore_index=True)
    assert len(nearby_pairs(partners,1))==1
    assert len(filter_partners(partners,{'network_membership':['share']}))==1

def test_coverage_actual_polygon(provider):
    geom={'type':'Polygon','coordinates':[[[-76,39],[-74,39],[-74,41],[-76,41],[-76,39]]]}
    units=frame('geographic_units',unit_id='u',geographic_id='real-id-in-fixture',geographic_resolution='tract',name='SYNTHETIC AREA',county='Philadelphia County',geometry_json=json.dumps(geom),source='Synthetic',vintage='2020',visibility='public')
    result=coverage(units,provider,1)
    assert result.share_inside.iloc[0]==1
    assert result.external_inside.iloc[0]==0
    result=coverage(units,provider.iloc[:0],1)
    assert pd.isna(result.nearest_straight_line_km.iloc[0])
    fig=landscape_map(provider,units)
    assert len(fig.data)==2
    assert all(trace.type=='scatter' for trace in fig.data) # no remote map tiles/topology

def need():
    return pd.DataFrame([dict(indicator_name='poverty',geographic_id='A',geographic_resolution='tract',value=10,unit='percent',numerator=10,denominator=100,source='synthetic',reporting_year=2025,vintage='v1'),dict(indicator_name='poverty',geographic_id='B',geographic_resolution='tract',value=20,unit='percent',numerator=40,denominator=200,source='synthetic',reporting_year=2025,vintage='v1')])

def test_weighted_rates_missing_and_context():
    f=need()
    assert aggregate_indicator(f)==pytest.approx(100*50/300)
    f.loc[1,'denominator']=np.nan
    assert pd.isna(aggregate_indicator(f))
    assert indicator_values(f).display_value.iloc[1]==20
    f.loc[1,'reporting_year']=2024
    with pytest.raises(ValueError): aggregate_indicator(f)

def schedules():
    return pd.DataFrame([dict(partner_id=s,operating_day=d,opening_time=a,closing_time=b,distribution_frequency=f,effective_start_date='',effective_end_date='',verification_status='verified') for s,d,a,b,f in [('A','Monday','09:00','11:00','weekly'),('A','Monday','10:00','12:00','weekly'),('A','Tuesday','09:00','10:00','monthly'),('B','Monday','10:30','13:00','weekly')]])

def test_windows_union_and_overlap():
    f=schedules();hours=weekly_hours(f)
    assert hours[hours.partner_id=='A'].scheduled_hours.iloc[0]==3
    assert 'Tuesday' not in hours.operating_day.tolist()
    pairs=pd.DataFrame([dict(partner_a='A',partner_b='B',site_a='Synthetic A',site_b='Synthetic B',straight_line_km=0.1)])
    overlap=schedule_overlap(pairs,f)
    assert overlap.overlap_hours.iloc[0]==1.5
    f.loc[0,'verification_status']='unverified';f.loc[1,'effective_end_date']='2020-01-01'
    assert len(eligible_schedules(f,'2026-01-01'))==2
    assert weekly_hours(f.iloc[:0]).empty

def test_exact_periods_and_missing():
    f=pd.DataFrame([dict(reporting_period_start=s,reporting_period_end=e,pounds_sent=None,pounds_received=10,pounds_distributed=None,households_served=None,individuals_served=None,distribution_events=None) for s,e in [('2026-01-01','2026-01-31'),('2026-01-01','2026-03-31')]])
    r=distribution_summary(f)
    assert len(r)==2
    assert r.pounds_distributed.isna().all()
    assert r.pounds_received_reported_sites.tolist()==[1,1]

def config():
    return dict(version='synthetic-v1',approved=True,resolution='tract',missing_policy='withhold',minimum_coverage=0.5,indicators=[dict(name='need',weight=0.5,direction='higher',normalization='minmax'),dict(name='access',weight=0.5,direction='lower',normalization='minmax')])

def test_scoring_explanation_and_missing():
    f=pd.DataFrame({'need':[0,10,5],'access':[10,0,np.nan]})
    c=config();r,contrib=score(f,c)
    assert r.score.iloc[0]==0
    assert r.score.iloc[1]==1
    assert pd.isna(r.score.iloc[2])
    assert np.allclose(contrib.sum(axis=1).iloc[:2],r.score.iloc[:2])
    c['missing_policy']='renormalize'
    r2,_=score(f,c);assert r2.score.iloc[2]==0.5
    assert r2.coverage.iloc[2]==0.5
    assert len(sensitivity(f,[c]))==1
    assert score(f,c)[0].equals(score(f,c)[0])
    c['approved']=False
    with pytest.raises(ValueError): score(f,c)
    c['approved']=True;c['indicators'][0]['weight']=2
    with pytest.raises(ValueError): score(f,c)

def test_scenario_budget_and_storage(populated):
    p=pd.DataFrame({'additional_pounds':[40,60]})
    assert scenario_budget(p,100)['within_budget']
    assert not scenario_budget(p,99)['within_budget']
    p.loc[0,'additional_pounds']=-1
    with pytest.raises(ValueError): scenario_budget(p,100)
    populated.save_scenario('Synthetic','Go deep',{'budget':100})
    assert len(populated.scenarios())==1

def test_projected_area_scope(provider):
    units=pd.DataFrame({'geometry_json':[json.dumps({'type':'Polygon','coordinates':[[[-75.01,39.99],[-74.99,39.99],[-74.99,40.01],[-75.01,40.01],[-75.01,39.99]]]})]})
    assert len(providers_near_units(provider,units,0))==1
    moved=provider.copy();moved.loc[0,'longitude']='-74'
    assert providers_near_units(moved,units,1).empty
