"""Reconcile supplied public exports without replacing primary regional data.

Run after base refresh. Original files stay local; only verified public facts and audit tables ship.
"""
import sys,json,hashlib,argparse,shutil,tempfile
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import requests
from partner_network.supplemental import compare_meals,clean_health,metric_catalog,provider_kind
RAW=Path('public_data/raw');OUT=Path('public_data/processed')
HEALTH_URL='https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/health_of_the_city/FeatureServer/0/query'
REL_URL='https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_st42.txt'

def load_official_health():
    path=RAW/'health_official.json'
    if not path.exists():
        rows=[];offset=0
        while True:
            response=requests.get(HEALTH_URL,params={'where':'1=1','outFields':'*','returnGeometry':'false','f':'json','orderByFields':'objectid','resultOffset':offset,'resultRecordCount':2000},timeout=60);response.raise_for_status();data=response.json()
            if 'error' in data:raise ValueError(data['error'])
            batch=[f['attributes'] for f in data['features']];rows.extend(batch)
            if not data.get('exceededTransferLimit'):break
            if not batch:raise ValueError('Empty truncated official response')
            offset+=len(batch)
        path.write_text(json.dumps(rows))
    return pd.DataFrame(json.loads(path.read_text()))

def build(args):
    manifest=json.loads((OUT/'manifest.json').read_text());manifest=[x for x in manifest if x.get('integration_batch')!='supplemental-2026-11']
    frames={};now=datetime.now(timezone.utc).isoformat()
    for name in ['tracts','meals','health']:
        path=getattr(args,name);data=path.read_bytes();destination=RAW/('supplied_'+name+'.csv')
        if path.resolve()!=destination.resolve():destination.write_bytes(data)
        frames[name]=pd.read_csv(destination,dtype=str,keep_default_na=False)
        manifest.append(dict(integration_batch='supplemental-2026-11',source='Supplied public export, reconciled against official source',asset=destination.name,retrieved_at=now,sha256=hashlib.sha256(data).hexdigest(),record_count=len(frames[name]),validation_status='See reconciliation audit'))
    # Provider reconciliation uses the public source snapshot already integrated.
    original=json.loads((RAW/'philadelphia.geojson').read_text())
    existing=pd.DataFrame([f['properties'] for f in original['features']])
    diff,new,removed=compare_meals(existing,frames['meals'])
    if new or removed or (diff.equivalence=='substantive difference').any():raise ValueError('Provider differences require explicit source/version review; nothing appended')
    diff.to_parquet(OUT/'meal_reconciliation.parquet',index=False)
    partners=pd.read_parquet(OUT/'partners.parquet')
    indexed=frames['meals'].set_index('objectid')
    for idx,row in partners[partners.partner_id.str.startswith('PHL:')].iterrows():
        p=indexed.loc[row.partner_id.split(':')[1]]
        partners.loc[idx,'source_category_type']=p.category_type;partners.loc[idx,'source_category']=p.category
        partners.loc[idx,'partner_type']=provider_kind(p.category_type,p.category)
        partners.loc[idx,'export_reconciliation']='Matched supplied export to official snapshot; no new provider'
    partners.to_parquet(OUT/'partners.parquet',index=False)
    for item in manifest:
        if item.get('asset')=='partners.parquet':
            item['sha256']=hashlib.sha256((OUT/'partners.parquet').read_bytes()).hexdigest()
            item['validation_status']='404 Philadelphia source records reconciled; original categories preserved; no duplicate providers appended'
    partners[partners.duplicate_review.fillna(False)].to_parquet(OUT/'duplicate_candidates.parquet',index=False)
    # Preserve original geography as reference attributes, never substitute for polygons.
    old=frames['tracts'];assert old.GEOID10.is_unique and old.GEOID10.str.fullmatch('42101[0-9]{6}').all()
    current=pd.read_parquet(OUT/'geographic_units.parquet');current_ids=set(current[(current.county=='Philadelphia County')&current.geographic_resolution.eq('tract')].geographic_id)
    relation=RAW/'tract_relationships_2010_2020_pa.txt'
    if not relation.exists():
        response=requests.get(REL_URL,timeout=60);response.raise_for_status();relation.write_bytes(response.content)
    rel=pd.read_csv(relation,sep='|',dtype=str,encoding='utf-8-sig');rel=rel[rel.GEOID_TRACT_10.str.startswith('42101') & rel.GEOID_TRACT_20.str.startswith('42101')]
    assert set(rel.GEOID_TRACT_10)==set(old.GEOID10) and set(rel.GEOID_TRACT_20)==current_ids
    rel.to_parquet(OUT/'tract_relationships_2010_2020.parquet',index=False)
    old.assign(scope='Philadelphia only',vintage='2010 census reference attributes; no polygon geometry').to_parquet(OUT/'tracts_2010_reference.parquet',index=False)
    audit=pd.DataFrame([dict(geographic_id=g,in_2010=g in set(old.GEOID10),in_current_tiger=g in current_ids) for g in sorted(set(old.GEOID10)|current_ids)])
    audit.to_parquet(OUT/'tract_vintage_audit.parquet',index=False)
    # Verify supplied health records are the official public observations, not internal information.
    h=frames['health'];official=load_official_health()
    def canonical(frame):
        f=frame.copy().fillna('').astype(str)
        for col in ['metric_value','lower_bound','upper_bound']:f[col]=pd.to_numeric(f[col],errors='coerce')
        for col in set(f.columns)-{'metric_value','lower_bound','upper_bound'}:f[col]=f[col].replace({'NA':'','null':''})
        return f.sort_values('objectid').reset_index(drop=True)
    a=canonical(h);b=canonical(official)[a.columns]
    pd.testing.assert_frame_equal(a,b,check_dtype=False)
    health=clean_health(h);health['dataset_source_url']='https://opendataphilly.org/datasets/health-of-the-city/';health['retrieved_at']=now
    health.to_parquet(OUT/'health_of_city.parquet',index=False)
    catalog=metric_catalog(health);catalog.to_parquet(OUT/'health_metric_catalog.parquet',index=False)
    summary=dict(meal_source_records=len(indexed),new_providers=0,substantive_provider_differences=0,format_precision_differences=len(diff),source_category_counts=frames['meals'].category_type.value_counts().to_dict(),tracts_2010=len(old),tracts_current=len(current_ids),shared_tract_ids=len(set(old.GEOID10)&current_ids),old_only_ids=len(set(old.GEOID10)-current_ids),current_only_ids=len(current_ids-set(old.GEOID10)),official_relationship_rows=len(rel),health_rows=len(health),health_metrics=len(catalog),sentinel_values={c:int(pd.to_numeric(h[c],errors='coerce').eq(-99999).sum()) for c in ['metric_value','lower_bound','upper_bound']},geographic_resolutions=health.geographic_resolution.value_counts().to_dict())
    (OUT/'supplemental_audit.json').write_text(json.dumps(summary,indent=2))
    for name,source,vintage,limitation in [('health_of_city',HEALTH_URL,'Source reporting periods retained; predominantly 2017–2021 context','Philadelphia only, not tract data; sentinel and unsafe observations missing; no pooling across strata.'),('health_metric_catalog',HEALTH_URL,'47 source indicators','Catalog of all indicators; no scoring framework.'),('tract_relationships_2010_2020',REL_URL,'2010-to-2020 official tract relationships','Land/water overlap is not a population allocation weight; no estimates converted.'),('tracts_2010_reference','Supplied Census_Tracts_2010.csv','2010','Attribute reference only. Does not replace current boundaries.'),('tract_vintage_audit',REL_URL,'2010 vs TIGER2024 identifiers','Matching IDs alone do not establish unchanged geometry.'),('meal_reconciliation','https://opendataphilly.org/datasets/free-food-and-meal-sites/','Existing snapshot vs supplied export','No new providers; formatting differences are not operational updates.')]:
        asset=OUT/(name+'.parquet');manifest.append(dict(integration_batch='supplemental-2026-11',source=source,asset=asset.name,retrieved_at=now,reporting_vintage=vintage,record_count=len(pd.read_parquet(asset)),geographic_coverage='Philadelphia only',validation_status='reconciled against official public data',sha256=hashlib.sha256(asset.read_bytes()).hexdigest(),limitations=limitation))
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(summary,indent=2))
def main():
    global OUT
    parser=argparse.ArgumentParser()
    for name in ['tracts','meals','health']:parser.add_argument('--'+name,type=Path,default=RAW/('supplied_'+name+'.csv'))
    args=parser.parse_args();target=OUT
    Path('work').mkdir(exist_ok=True)
    # Validate the entire batch in staging before touching any release asset.
    with tempfile.TemporaryDirectory(prefix='supplement-stage-',dir='work') as directory:
        stage=Path(directory);shutil.copytree(target,stage,dirs_exist_ok=True);OUT=stage
        try:
            build(args)
            for asset in sorted(stage.iterdir(),key=lambda p:p.name=='manifest.json'):
                destination=target/asset.name
                if not destination.exists() or asset.read_bytes()!=destination.read_bytes():
                    asset.replace(destination)
        finally:OUT=target
if __name__=='__main__':main()
