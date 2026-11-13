"""Pure, conservative reconciliation of supplementary public exports."""
import math
import re
import pandas as pd

PRIORITY=['percent_below_poverty','percent_unemployed','percent_of_burdened_renters','age_distribution','percent_of_population']
LABELS={'percent_below_poverty':'Poverty rate','percent_unemployed':'Unemployment rate','percent_of_burdened_renters':'Housing cost burden · renters','age_distribution':'Population counts by age','percent_of_population':'Population composition (%)'}

def normalize_time(value):
    value='' if value is None else str(value)
    if re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d(:00)?',value): return value[:5]
    return value

def provider_kind(category_type,category):
    if category_type=='Public Benefits':return 'public benefits'
    if 'Refrigerator' in category:return 'community fridge'
    return {'Food Site':'food site','General Meal Site':'meal site','Senior Meal Site':'senior meal site'}.get(category_type,'other food distribution')

def compare_meals(existing,supplied):
    a=existing.fillna('').astype(str).set_index('objectid');b=supplied.fillna('').astype(str).set_index('objectid')
    if not a.index.is_unique or not b.index.is_unique:raise ValueError('Duplicate source object IDs require review')
    differences=[]
    for oid in sorted(set(a.index)&set(b.index),key=int):
        for col in b.columns:
            x=a.at[oid,col] if col in a else '';y=b.at[oid,col]
            if x==y:continue
            equal=False
            if col in ('x','y') and x and y:equal=math.isclose(float(x),float(y),rel_tol=0,abs_tol=1e-7)
            elif col.startswith('hours_'):equal=normalize_time(x)==normalize_time(y)
            differences.append(dict(objectid=oid,field=col,existing=x,supplied=y,equivalence='format/precision only' if equal else 'substantive difference'))
    return pd.DataFrame(differences,columns=['objectid','field','existing','supplied','equivalence']),sorted(set(b.index)-set(a.index)),sorted(set(a.index)-set(b.index))

def clean_health(frame):
    result=frame.copy()
    if not result.objectid.is_unique:raise ValueError('Duplicate Health of City observation IDs')
    sentinel=pd.DataFrame({c:pd.to_numeric(result[c],errors='coerce').eq(-99999) for c in ['metric_value','lower_bound','upper_bound']})
    for col in sentinel:
        result[col]=pd.to_numeric(result[col],errors='coerce').mask(sentinel[col])
    unsafe=result.quality_flag.str.contains('Suppressed|Unreliable',case=False,na=False)
    result['missing_reason']=''
    result.loc[sentinel.metric_value,'missing_reason']='Source sentinel -99999'
    result.loc[unsafe,'missing_reason']='Source quality flag: '+result.loc[unsafe,'quality_flag']
    result.loc[unsafe,['metric_value','lower_bound','upper_bound']]=float('nan')
    result['geographic_resolution']=result.geography.map({'County':'county','ZCTA':'zcta','Planning district':'planning_district'})
    if result.geographic_resolution.isna().any():raise ValueError('Unknown Health of City geography')
    result['geographic_id']=result.geography_name
    result.loc[result.geography.eq('County') & result.geography_name.eq('Philadelphia'),'geographic_id']='42101'
    result['scope']='Philadelphia only'
    result['unit']=result.metric_name.map(lambda m:'percent' if m.startswith('percent_') else 'count' if m.startswith('count_') or m in ('age_distribution','live_births') else 'years' if m=='life_expectancy_at_birth' else 'source-defined measure')
    result['priority_context']=result.metric_name.isin(PRIORITY)
    return result

def metric_catalog(health):
    rows=[]
    for metric,f in health.groupby('metric_name'):
        rows.append(dict(metric_name=metric,label=LABELS.get(metric,metric.replace('_',' ')),use='Priority community context' if metric in PRIORITY else 'Other health context; no opportunity scoring',unit=f.unit.iloc[0],rows=len(f),missing_values=int(f.metric_value.isna().sum()),reporting_periods=' | '.join(sorted(f.year.unique())),geographic_resolutions=' | '.join(sorted(f.geographic_resolution.unique())),sources=' | '.join(sorted(f.source.unique()))))
    return pd.DataFrame(rows)
