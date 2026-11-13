"""Source-published factual extraction; retains unparsed schedules and geocoder evidence."""
import sys,json,re,concurrent.futures
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import requests,pandas as pd
from bs4 import BeautifulSoup
RAW=Path('public_data/raw');RAW.mkdir(exist_ok=True,parents=True)
# Copy the verified publisher-linked KML, not unrelated Maryland data.
kmlpath=RAW/'mahn.kml'
if not kmlpath.exists():
    response=requests.get('https://www.google.com/maps/d/kml?mid=1c-au-fpFUjaSwylPB9xcY89UQnN7iWNU&forcekml=1',timeout=60);response.raise_for_status();kmlpath.write_bytes(response.content)
kml=kmlpath.read_bytes()
rows=[]
for i,p in enumerate(BeautifulSoup(kml,'xml').find_all('Placemark')):
 fields={d['name']:d.find('value').text if d.find('value') else '' for d in p.find_all('Data')}
 rows.append(dict(partner_id=f'MAHN:{i+1}',site_name=p.find('name').text,street_address=fields.get('Address'),city=fields.get('City'),zip_code=fields.get('ZIP'),county='Montgomery County',network_membership='unknown',provider_affiliations='MontCo Anti-Hunger Network member',source='https://www.montcoantihunger.org/do-you-need-food.html',published_schedule=fields.get('Hours'),source_vintage='undated public member map'))
# Transcribed facts from county PDF, March 2026. No individual contact details included.
delco=[('AFA Agency','708 Pembroke Ave.','East Lansdowne','19050','Wednesday & Friday, 4:00 PM to 6:00 PM'),('Bernardine Center','2625 W. 9th St.','Chester','19013','2nd & 4th Tuesdays 4–5 PM; first four Wednesdays 9–11 AM'),('Chester Eastside, Inc.','301 East 9th St.','Chester','19013','Monday & Wednesday, 11:00 AM to 12:45 PM'),('Delco Food Project','535 Lamp Post Lane','Aston','19014','Thursday 12:00 PM to 5:00 PM'),('HEALTH Food Pantry','800 Chester Pike, 6A','Sharon Hill','19079','Monday to Friday, 10:00 AM to 2:00 PM'),('Lifewerks','28 Walnut Road','Wallingford','19086','Tuesdays, 6:00 PM to 8:00 PM'),('Loaves and Fishes Food Pantry','703 Lincoln Ave.','Prospect Park','19076','Tuesday 11 AM–2 PM and 5–7 PM; Thursday 1–4 PM'),('Media Food Bank','350 W State St.','Media','19063','Thursday 6–8 PM; Sunday 1–2 PM'),('Mt. Zion CME Church','701 Felton Ave.','Sharon Hill','19079','Wednesday 1:30–2:30 PM; Thursday noon–1:30 PM; Saturday 10 AM–noon'),('Multicultural Community Family Services','7016 Terminal Square','Upper Darby','19082','1st & 3rd Tuesdays 11:30 AM–3:30 PM; 2nd, 4th, 5th Tuesday outdoor only until food runs out'),("Murphy’s Giving Market",'7408 West Chester Pike','Upper Darby','19082','Monday seniors: registration 8–10 AM, distribution 9–11 AM; Tuesday non-seniors: registration 8–11 AM, distribution 10 AM–1 PM; every other Saturday 10 AM–noon with pre-registration'),('Neighbor to Neighbor','814 Clifton Ave.','Sharon Hill','19079','Thursday 6–8 PM'),('Salvation Army Chester Corps','151 W. 15th St.','Chester','19013','3rd Wednesday 10 AM–1 PM'),("St. Mary’s Episcopal Church",'703 Edwards St.','Chester','19013','Thursday 12:30–2:30 PM'),('St. Paul CME Church Food Ministry','1009 W. 3rd St.','Chester','19013','Tuesday 11 AM–2 PM; Friday noon–2 PM'),('True Vine Missionary Church','701 Morton Ave.','Chester','19013','Tuesday 10:30–11:30 AM; Thursday emergency appointments only 10:30 AM–1 PM; every fourth Sunday except holidays')]
source='https://delcohomelessservices.org/food-pantries'
for i,(name,street,city,zipc,hours) in enumerate(delco): rows.append(dict(partner_id=f'DELCO:{i+1}',site_name=name,street_address=street,city=city,zip_code=zipc,county='Delaware County',network_membership='share',provider_affiliations='County state-assisted pantry network coordinated by Share Food Program (PDF introduction)',source=source,published_schedule=hours,source_vintage='March 2026 county PDF'))

def geocode(row):
 row.update(state='PA',partner_type='food pantry',active_status='unknown',latitude=None,longitude=None,geocoding_method='Census onelineaddress',geocoding_confidence='unmatched',visibility='public')
 address=f"{row['street_address']}, {row['city']}, PA {row['zip_code']}"
 path=RAW/(row['partner_id'].replace(':','_')+'_geocode.json')
 try:
  if not path.exists():
   r=requests.get('https://geocoding.geo.census.gov/geocoder/locations/onelineaddress',params={'address':address,'benchmark':'Public_AR_Current','format':'json'},timeout=35);r.raise_for_status();path.write_text(r.text)
  data=json.loads(path.read_text());matches=data['result']['addressMatches']
  if len(matches)==1:
   match=matches[0];row.update(latitude=match['coordinates']['y'],longitude=match['coordinates']['x'],geocoding_confidence='single Census address match; street interpolation, not rooftop',matched_address=match['matchedAddress'])
 except Exception as e: row['geocoding_confidence']='unavailable: '+type(e).__name__
 return row
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 result=list(pool.map(geocode,rows))
pd.DataFrame(result).to_csv(RAW/'reviewed_providers.csv',index=False)
print(len(result),'source records;',sum(r['latitude'] is not None for r in result),'Census geocodes')
