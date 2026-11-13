"""Reproducible public-only asset build. Run from root; cached raw responses never loaded by visitors."""
import sys,io,json,zipfile,hashlib,re
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests
import pandas as pd
import geopandas as gpd
from bs4 import BeautifulSoup
from partner_network.schema import SCHEMAS
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'public_data/raw'; OUT=ROOT/'public_data/processed'; RAW.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
COUNTIES={'42045':'Delaware County','42091':'Montgomery County','42101':'Philadelphia County'}
TODAY=datetime.now(timezone.utc).isoformat()
manifest=[]
def acquire(name,url,cache=None):
 p=RAW/name
 if not p.exists():
  old=ROOT/'work/acquisition'/str(cache or name)
  if old.exists(): p.write_bytes(old.read_bytes())
  else:
   r=requests.get(url,headers={'User-Agent':'PartnerNetworkIntelligence/1.0 (public regional food-access research)'},timeout=120);r.raise_for_status();p.write_bytes(r.content)
 manifest.append(dict(source=url,asset=name,retrieved_at=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size))
 return p

def save(name,df,vintage,source,limitations):
 df.to_parquet(OUT/(name+'.parquet'),index=False)
 manifest.append(dict(asset=name+'.parquet',source=source,retrieved_at=TODAY,reporting_vintage=vintage,record_count=len(df),geographic_coverage=list(COUNTIES.values()),validation_status='validated identifiers and county membership',limitations=limitations))

def base(category,**values):
 row={f:None for f in SCHEMAS[category].fields.split()};row.update(visibility='public');row.update(values);return row

GEO='https://www2.census.gov/geo/tiger/TIGER2024/TRACT/tl_2024_42_tract.zip'
geo=gpd.read_file(acquire('tracts.zip',GEO,'geo')).to_crs(4326)
geo=geo[geo.GEOID.str[:5].isin(COUNTIES)].copy(); assert geo.GEOID.is_unique and geo.geometry.is_valid.all()
geo['county']=geo.GEOID.str[:5].map(COUNTIES)
rows=[]
for _,r in geo.iterrows(): rows.append(base('geographic_units',unit_id=r.GEOID,geographic_id=r.GEOID,geographic_resolution='tract',name=r.NAMELSAD,county=r.county,geometry_json=json.dumps(r.geometry.simplify(.00005,preserve_topology=True).__geo_interface__),source=GEO,vintage='TIGER 2024 (2020 census tracts)'))
for name,group in geo.groupby('county'):
 code=next(k for k,v in COUNTIES.items() if v==name)
 rows.append(base('geographic_units',unit_id=code,geographic_id=code,geographic_resolution='county',name=name,county=name,geometry_json=json.dumps(group.geometry.union_all().simplify(.0001,preserve_topology=True).__geo_interface__),source=GEO,vintage='TIGER 2024 tract union (derived county outline)'))
save('geographic_units',pd.DataFrame(rows),'2024',GEO,'County outlines derived by union of official tracts; simplified for display.')
ACS='https://api.censusreporter.org/1.0/data/show/acs2024_5yr?table_ids=B01003,B17001,B22010,B08201,B19013,B11001&geo_ids=140|05000US42045,140|05000US42091,140|05000US42101'
a=json.loads(acquire('acs2024.json',ACS,'acsreporter').read_bytes());assert a['release']['id']=='acs2024_5yr'
rows=[]
variables=[('Population','B01003','B01003001','count',None),('People below poverty','B17001','B17001002','count',None),('Poverty rate','B17001','B17001002','percent','B17001001'),('SNAP households','B22010','B22010002','households',None),('SNAP household participation rate','B22010','B22010002','percent','B22010001'),('Households','B11001','B11001001','households',None),('Family households','B11001','B11001002','households',None),('Households without a vehicle','B08201','B08201002','households',None),('No-vehicle household rate','B08201','B08201002','percent','B08201001'),('Median household income','B19013','B19013001','dollars',None)]
for key,tables in a['data'].items():
 gid=key.split('US')[1]; assert gid[:5] in COUNTIES
 for label,t,col,unit,den in variables:
  estimate=tables[t]['estimate'];err=tables[t]['error'];value=estimate[col]
  if value is not None and value<0:value=None
  denominator=estimate[den] if den else None
  val=100*value/denominator if den and value is not None and denominator and denominator>0 else value if not den else None
  row=base('community_indicators',indicator_id=f'ACS2024:{gid}:{label}',indicator_name=label,geographic_id=gid,geographic_resolution='tract',value=val,unit=unit,numerator=value if den else None,denominator=denominator,source='Census ACS 2024 5-year via Census Reporter',reporting_year=2024,vintage='2020–2024 ACS 5-year',methodology=a['tables'][t]['title']+'; universe: '+a['tables'][t]['universe'])
  row.update(estimate=value,margin_of_error=err[col],denominator_margin_of_error=err.get(den),rate_margin_of_error=None,variable=col,source_url=ACS,county=COUNTIES[gid[:5]],retrieved_at=TODAY)
  rows.append(row)
# Retain full ACS estimate/MOE tables and variable definitions as source evidence.
(OUT/'acs_metadata.json').write_text(json.dumps({'release':a['release'],'tables':a['tables']},indent=2))
indicators=pd.DataFrame(rows)

PHILLY='https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/free_meal_sites/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson&outSR=4326'
f=json.loads(acquire('philadelphia.geojson',PHILLY,'phillydata').read_bytes());assert not f.get('exceededTransferLimit')
partners=[]; schedules=[]
from shapely.geometry import Point
for feature in f['features']:
 p=feature['properties'];pid='PHL:'+str(p['objectid']);location=feature.get('geometry');xy=location['coordinates'] if location else [None,None]
 category=p.get('category') or '';status=p.get('status');kind='public benefits' if p['category_type']=='Public Benefits' else 'community fridge' if 'Refrigerator' in category else 'free meal program' if 'Meal' in p['category_type'] else 'food pantry / distribution'
 # A non-Share directory label does not establish independent affiliation.
 membership='share' if 'SHARE FOOD PROGRAM' in category else 'unknown'
 row=base('partners',partner_id=pid,site_name=p['site_name'],street_address=p.get('address'),city='Philadelphia',state='PA',zip_code=p.get('zip_code'),county='Philadelphia County',latitude=xy[1],longitude=xy[0],partner_type=kind,active_status='active' if status=='Active' else 'inactive' if status=='Permanently Closed' else 'unknown',network_membership=membership,provider_affiliations=category,source=PHILLY,last_verified=None)
 row.update(retrieved_at=TODAY,source_status=status,seasonally_closed=p.get('seasonally_closed'),temporary_closure=p.get('temporary_closure'),geocoding_method='source coordinates',geocoding_confidence='source supplied; not independently surveyed',source_record_id=str(p['objectid']),published_schedule=json.dumps({k:v for k,v in p.items() if k.startswith('hours_') and v}),website=p.get('website'))
 if xy[0] is not None:
  match=geo[geo.geometry.covers(Point(*xy))]
  row['census_tract']=match.GEOID.iloc[0] if len(match)==1 else None
 partners.append(row)
 for abbrev,day in [('mon','Monday'),('tues','Tuesday'),('wed','Wednesday'),('thurs','Thursday'),('fri','Friday'),('sat','Saturday'),('sun','Sunday')]:
  for number in [1,2]:
   start=p.get(f'hours_{abbrev}_start{number}');end=p.get(f'hours_{abbrev}_end{number}');exception=p.get(f'hours_{abbrev}_exceptions')
   if start and end and re.fullmatch(r'\d{2}:\d{2}',start) and re.fullmatch(r'\d{2}:\d{2}',end) and start<end:
    schedules.append(base('operating_schedules',schedule_id=f'{pid}:{day}:{number}',partner_id=pid,operating_day=day,opening_time=start,closing_time=end,distribution_frequency='source exceptions: '+exception if exception else 'weekly',verification_status='unverified',source=PHILLY,source_notes=exception,retrieved_at=TODAY))
# Public directory records remain source-published, not independently verified.
save('operating_schedules',pd.DataFrame(schedules),'retrieved '+TODAY,PHILLY,'Published recurring windows; exceptions retained. Not independently verified; seasonal closures may apply.')

USDA='https://www.ers.usda.gov/media/29395/2025-snap-authorized-retailer-access-map-sram-data.zip?v=21278'
z=zipfile.ZipFile(acquire('usda_sram2025.zip',USDA,'usdadata'))
for filename in z.namelist():
 if 'Variable Lookup' in filename or 'Read Me' in filename: (OUT/filename).write_bytes(z.read(filename))
 for_table=filename.endswith('Data.csv')
 if for_table:
  pieces=[]
  for chunk in pd.read_csv(z.open(filename),dtype={'CensusTract20':str},encoding='latin1',chunksize=15000):
   chunk.CensusTract20=chunk.CensusTract20.str.zfill(11);pieces.append(chunk[chunk.CensusTract20.str[:5].isin(COUNTIES)])
  regional=pd.concat(pieces,ignore_index=True);save('usda_'+filename.split(' ')[1].lower(),regional,'2025 SRAM; July 2026 release',USDA,'Retailer access, not pantry access. Underlying demographic vintages differ; 2020 census tract geography.')
# Official published county-level Feeding America facts (no tract downscaling).
fi=[]
for code,slug in [('42045','delaware'),('42091','montgomery'),('42101','philadelphia')]:
 url=f'https://map.feedingamerica.org/county/2024/overall/pennsylvania/county/{slug}'
 page=BeautifulSoup(acquire('feeding_'+code+'.html',url).read_bytes(),'html.parser')
 props=json.loads(page.find('script',{'data-page':'app'}).string)['props']
 selected=props['selected'];assert selected['fips']==code and props['year']=='2024'
 for label,value,unit in [('Food insecurity rate',selected['insecurity']*100,'percent'),('Food-insecure population',selected['population'],'count')]:
  fi.append(base('community_indicators',indicator_id='MMG2026:'+code+label,indicator_name=label,geographic_id=code,geographic_resolution='county',value=value,unit=unit,source='Feeding America Map the Meal Gap',reporting_year=2024,vintage='2026 release / 2024 data',methodology='Official published modeled county estimate; no tract-level inference',source_url=url,retrieved_at=TODAY,county=COUNTIES[code]))
indicators=pd.concat([indicators,pd.DataFrame(fi)],ignore_index=True)
save('community_indicators',indicators,'ACS 2024 5-year (2020–2024)',ACS,'90% ACS margins of error retained. Derived rate MOE is not calculated. Census Reporter is an alternate distributor, not Census Bureau.')
# More provider sources are ingested from reviewed factual extracts; never infer fuzzy identity matches.
acquire('mahn.kml','https://www.google.com/maps/d/kml?mid=1c-au-fpFUjaSwylPB9xcY89UQnN7iWNU&forcekml=1','montcokml')
acquire('delco_march2026.pdf','https://img1.wsimg.com/blobby/go/fef8f23f-9f4c-47ac-b508-d026080ed29b/DelCo%20Pantry%20Sites%20March%202026.pdf','delcopdf')
extra=RAW/'reviewed_providers.csv'
if not extra.exists():
    import scripts.provider_extracts
if extra.exists():
 extras=pd.read_csv(extra).where(pd.notna(pd.read_csv(extra)),None).to_dict(orient='records')
 for p in extras: partners.append(base('partners',**p))
providers=pd.DataFrame(partners)
assert providers.partner_id.is_unique
# Validate source/geocoder coordinates against the expected county polygon; preserve conflicts without plotting.
county_polygons={name:group.geometry.union_all() for name,group in geo.groupby('county')}
for idx,row in providers.dropna(subset=['latitude','longitude']).iterrows():
    pt=Point(float(row.longitude),float(row.latitude))
    if not county_polygons[row.county].covers(pt):
        providers.loc[idx,'geocoding_confidence']='county mismatch: coordinate withheld pending review'
        providers.loc[idx,['latitude','longitude']]=None
    else:
        matched=geo[geo.geometry.covers(pt)]
        if len(matched)==1:providers.loc[idx,'census_tract']=matched.GEOID.iloc[0]
normalized=providers.street_address.fillna('').str.lower().str.replace(r'[^a-z0-9]','',regex=True)+'|'+providers.zip_code.fillna('').astype(str)
providers['duplicate_review']=normalized.duplicated(keep=False)&providers.street_address.notna()
save('duplicate_candidates',providers[providers.duplicate_review],'current snapshot','source addresses','Exact normalized address/ZIP matches only; retained separately, not automatically merged.')
# Exact same source record IDs are unique; cross-source near matches retained for staff review.
save('partners',providers,'source-specific dates retained',PHILLY,'Directories incomplete; source status is not confirmation of operation. Public benefits entries are separately classified. Cross-source conflicts remain separate.')

GTFS='https://www3.septa.org/developer/gtfs_public.zip'
z=zipfile.ZipFile(acquire('septa_gtfs.zip',GTFS,'gtfs')); stopframes=[];routeframes=[];shapeframes=[]; calendars=[]
region=geo.geometry.union_all()
for mode in ['bus','rail']:
 inner=zipfile.ZipFile(io.BytesIO(z.read('google_'+mode+'.zip')))
 def read(n):return pd.read_csv(inner.open(n),dtype=str)
 stops=read('stops.txt'); stops['stop_lat']=pd.to_numeric(stops.stop_lat);stops['stop_lon']=pd.to_numeric(stops.stop_lon)
 bounds=region.bounds;stops=stops[stops.stop_lon.between(bounds[0],bounds[2])&stops.stop_lat.between(bounds[1],bounds[3])]
 stops=stops[stops.apply(lambda r:region.covers(Point(r.stop_lon,r.stop_lat)),axis=1)].copy();stops['mode']=mode;stopframes.append(stops)
 times=[]
 for chunk in pd.read_csv(inner.open('stop_times.txt'),dtype=str,chunksize=150000): times.append(chunk[chunk.stop_id.isin(stops.stop_id)])
 times=pd.concat(times,ignore_index=True);times.to_parquet(OUT/f'gtfs_{mode}_stop_times.parquet',index=False)
 trips=read('trips.txt');trips=trips[trips.trip_id.isin(times.trip_id)];trips.to_parquet(OUT/f'gtfs_{mode}_trips.parquet',index=False)
 routes=read('routes.txt');routes=routes[routes.route_id.isin(trips.route_id)].copy();routes['mode']=mode;routeframes.append(routes)
 for name in ['calendar.txt','calendar_dates.txt']:
  if name in inner.namelist():
   c=read(name);c['mode']=mode;c.to_parquet(OUT/f'gtfs_{mode}_{name[:-4]}.parquet',index=False)
 if 'shapes.txt' in inner.namelist():
  shapes=read('shapes.txt');shapes=shapes[shapes.shape_id.isin(trips.shape_id)];shapes['shape_pt_lat']=pd.to_numeric(shapes.shape_pt_lat);shapes['shape_pt_lon']=pd.to_numeric(shapes.shape_pt_lon);shapes['shape_pt_sequence']=pd.to_numeric(shapes.shape_pt_sequence)
  # One actual shape per route, clipped by regional bounding box for display.
  mapping=trips.drop_duplicates('route_id')[['route_id','shape_id']]
  shapes=shapes.merge(mapping,on='shape_id');shapes=shapes[shapes.shape_pt_lon.between(bounds[0],bounds[2])&shapes.shape_pt_lat.between(bounds[1],bounds[3])];shapes['mode']=mode;shapeframes.append(shapes)
save('gtfs_stops',pd.concat(stopframes,ignore_index=True),'downloaded '+TODAY,GTFS,'Regional stop points, not computed journeys or pantry access.')
save('gtfs_routes',pd.concat(routeframes,ignore_index=True),'downloaded '+TODAY,GTFS,'Actual routes serving regional stops; service calendars stored separately.')
if shapeframes:save('gtfs_shapes',pd.concat(shapeframes,ignore_index=True),'downloaded '+TODAY,GTFS,'One representative actual GTFS shape per route; viewport clipped. Branches omitted from display, full raw feed retained.')
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Built',len(providers),'providers,',len(geo),'tracts,',len(indicators),'ACS observations')
