"""Pure calculations; missing evidence remains missing."""
import json
import numpy as np
import pandas as pd
from .schema import ENUMS

DAYS = ENUMS['operating_day']

def filter_partners(frame, filters):
    result = frame.copy()
    for field, values in filters.items():
        if values: result = result[result[field].isin(values)]
    return result

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km; never a walking or transit estimate."""
    lat1,lon1,lat2,lon2 = [np.radians(np.asarray(x,dtype=float)) for x in (lat1,lon1,lat2,lon2)]
    a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a,0,1)))

def nearby_pairs(partners, radius_km):
    if radius_km <= 0: raise ValueError('Radius must exceed zero')
    sites = partners[partners.partner_type.ne('public benefits')].dropna(subset=['latitude','longitude']).reset_index(drop=True)
    rows=[]
    # Pairwise computation bounded in memory; actual network routes require supplied measurements.
    for i, a in sites.iterrows():
        rest=sites.iloc[i+1:]
        if rest.empty: continue
        distances=haversine(a.latitude,a.longitude,rest.latitude,rest.longitude)
        for (_,b),d in zip(rest.iterrows(),distances):
            if d <= radius_km:
                rows.append(dict(partner_a=a.partner_id,site_a=a.site_name,network_a=a.network_membership,partner_b=b.partner_id,site_b=b.site_name,network_b=b.network_membership,straight_line_km=float(d)))
    return pd.DataFrame(rows,columns=['partner_a','site_a','network_a','partner_b','site_b','network_b','straight_line_km'])

def coverage(units, partners, radius_km, include_unknown=False):
    """Exact polygon membership plus representative-point proximity proxy, not population access."""
    from shapely.geometry import shape, Point
    rows=[]
    active = partners[partners.active_status.ne('inactive') if include_unknown else partners.active_status.eq('active')].dropna(subset=['latitude','longitude'])
    active=active[active.partner_type.ne('public benefits')]
    from shapely.strtree import STRtree
    points=[Point(float(r.longitude),float(r.latitude)) for _,r in active.iterrows()]
    tree=STRtree(points)
    for _, unit in units.iterrows():
        geom = shape(json.loads(unit.geometry_json))
        origin = geom.representative_point()
        contained=np.zeros(len(active),dtype=bool)
        contained[tree.query(geom,predicate='covers')]=True
        inside=pd.Series(contained,index=active.index)
        distance = pd.Series(haversine(origin.y,origin.x,active.latitude,active.longitude), index=active.index)
        row = {k: unit[k] for k in ['geographic_id','geographic_resolution','name','county','vintage']}
        for membership in ['share','external','unknown']:
            member=active.network_membership == membership
            row[membership+'_inside'] = int((inside & member).sum())
            row[membership+'_near_point'] = int((distance.le(radius_km) & member).sum())
        row['nearest_straight_line_km'] = float(distance.min()) if len(distance) else np.nan
        row['providers_with_coordinates'] = len(active)
        rows.append(row)
    return pd.DataFrame(rows)

def indicator_values(frame):
    result=frame.copy()
    for col in ['value','numerator','denominator']: result[col]=pd.to_numeric(result[col],errors='coerce')
    rate = result.unit.isin(['percent','fraction']) & result.numerator.notna() & result.denominator.gt(0)
    result['display_value']=result.value
    result.loc[rate,'display_value']=(result.loc[rate,'numerator']/result.loc[rate,'denominator'])*np.where(result.loc[rate,'unit'].eq('percent'),100,1)
    result['calculation']=np.where(rate,'Calculated from numerator / denominator','Source value; denominator limitations retained')
    return result

def aggregate_indicator(frame):
    """User-selected non-overlapping units only; refuses incompatible contexts or unweighted rates."""
    if frame.empty: return np.nan
    context=['indicator_name','unit','reporting_year','source','vintage','geographic_resolution']
    if len(frame[context].drop_duplicates()) != 1: raise ValueError('Select one compatible indicator, unit, year, source, vintage and resolution')
    if frame.geographic_id.duplicated().any(): raise ValueError('Duplicate geographic observations')
    frame=indicator_values(frame)
    if frame.unit.iloc[0] in ('percent','fraction'):
        if frame[['numerator','denominator']].isna().any().any() or (frame.denominator <= 0).any(): return np.nan
        return frame.numerator.sum()/frame.denominator.sum()*(100 if frame.unit.iloc[0]=='percent' else 1)
    if frame.unit.iloc[0] not in ('count','households'): raise ValueError('This unit cannot be summed across geographies')
    return frame.display_value.sum(min_count=len(frame))

def eligible_schedules(schedules, as_of, verified_only=True):
    date=str(as_of)
    frame=schedules.copy()
    for field in ['effective_start_date','effective_end_date']:
        frame[field]=frame[field].fillna('')
    frame=frame[(frame.effective_start_date.eq('') | frame.effective_start_date.le(date)) & (frame.effective_end_date.eq('') | frame.effective_end_date.ge(date))]
    if verified_only: frame=frame[frame.verification_status=='verified']
    return frame

def weekly_hours(schedules):
    """Union windows per site/day. Non-weekly frequencies excluded, with explicit UI disclosure."""
    frame=schedules[schedules.distribution_frequency.str.lower().eq('weekly')]
    rows=[]
    for (site,day), group in frame.groupby(['partner_id','operating_day']):
        intervals=sorted((int(r.opening_time[:2])*60+int(r.opening_time[3:]),int(r.closing_time[:2])*60+int(r.closing_time[3:])) for _,r in group.iterrows())
        merged=[]
        for start,end in intervals:
            if merged and start <= merged[-1][1]: merged[-1][1]=max(end,merged[-1][1])
            else: merged.append([start,end])
        rows.append(dict(partner_id=site,operating_day=day,scheduled_hours=sum(b-a for a,b in merged)/60))
    return pd.DataFrame(rows,columns=['partner_id','operating_day','scheduled_hours'])

def schedule_overlap(pairs, schedules):
    """Shared scheduled hours of nearby sites; no inference of duplicative utilization."""
    frame=schedules[schedules.distribution_frequency.str.lower().eq('weekly')]
    rows=[]
    for _,pair in pairs.iterrows():
        for day in DAYS:
            a=frame[(frame.partner_id==pair.partner_a)&(frame.operating_day==day)]
            b=frame[(frame.partner_id==pair.partner_b)&(frame.operating_day==day)]
            intersections=[]
            def minutes(t): return int(t[:2])*60+int(t[3:])
            for _,x in a.iterrows():
                for _,y in b.iterrows():
                    start=max(minutes(x.opening_time),minutes(y.opening_time)); end=min(minutes(x.closing_time),minutes(y.closing_time))
                    if end>start: intersections.append((start,end))
            union=[]
            for start,end in sorted(intersections):
                if union and start<=union[-1][1]: union[-1][1]=max(end,union[-1][1])
                else: union.append([start,end])
            if union: rows.append(dict(site_a=pair.site_a,site_b=pair.site_b,operating_day=day,overlap_hours=sum(e-s for s,e in union)/60,straight_line_km=pair.straight_line_km))
    return pd.DataFrame(rows)

METRICS=['pounds_sent','pounds_received','pounds_distributed','households_served','individuals_served','distribution_events']
def distribution_summary(records):
    if records.empty: return pd.DataFrame()
    frame=records.copy()
    for c in METRICS: frame[c]=pd.to_numeric(frame[c],errors='coerce')
    # Exact interval, not a guessed month/quarter/year conversion.
    group=frame.groupby(['reporting_period_start','reporting_period_end'],dropna=False)
    result=group[METRICS].sum(min_count=1).reset_index()
    counts=group[METRICS].count().reset_index().rename(columns={c:c+'_reported_sites' for c in METRICS})
    return result.merge(counts,on=['reporting_period_start','reporting_period_end'])

def scenario_budget(proposal, budget):
    if proposal.empty: return dict(proposed_pounds=0,remaining_pounds=budget,within_budget=True)
    amounts=pd.to_numeric(proposal.additional_pounds,errors='raise')
    if not np.isfinite(amounts).all() or (amounts<0).any() or budget<0: raise ValueError('Budget and allocations must be finite nonnegative numbers')
    total=float(amounts.sum())
    return dict(proposed_pounds=total,remaining_pounds=float(budget-total),within_budget=bool(total<=budget))

def providers_near_units(partners, units, radius_km):
    """Select sites within a regional polygon buffer using a projected spatial index.

    EPSG:26918 (NAD83 / UTM 18N) is appropriate for the three-county study area.
    This screening buffer is not a walking service area.
    """
    from pyproj import Transformer
    from shapely.geometry import Point, shape
    from shapely.ops import transform, unary_union
    from shapely.strtree import STRtree
    if radius_km < 0: raise ValueError('Radius cannot be negative')
    if units.empty: return partners.iloc[:0].copy()
    projection=Transformer.from_crs(4326,26918,always_xy=True).transform
    area=unary_union([transform(projection,shape(json.loads(g))) for g in units.geometry_json]).buffer(radius_km*1000)
    sites=partners.dropna(subset=['latitude','longitude'])
    points=[transform(projection,Point(float(r.longitude),float(r.latitude))) for _,r in sites.iterrows()]
    if not points: return sites.copy()
    selected=STRtree(points).query(area,predicate='covers')
    return sites.iloc[sorted(selected)].copy()
