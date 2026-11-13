"""Opt-in area-level scoring. No default weights or implied organizational approval."""
import numpy as np
import pandas as pd

def score(frame, config):
    required=['version','approved','missing_policy','minimum_coverage','indicators','resolution']
    if any(k not in config for k in required): raise ValueError('Incomplete methodology configuration')
    if config['approved'] is not True: raise ValueError('An approved framework is required')
    if config['missing_policy'] not in ('withhold','renormalize'): raise ValueError('Documented missing-data policy required')
    if not 0 < config['minimum_coverage'] <= 1: raise ValueError('Coverage must be in (0,1]')
    items=config['indicators']
    if not items or len({i['name'] for i in items}) != len(items): raise ValueError('Indicators must be nonempty and unique')
    weights=np.array([float(i['weight']) for i in items])
    if not np.isfinite(weights).all() or (weights<0).any() or not np.isclose(weights.sum(),1): raise ValueError('Nonnegative weights must sum to 1')
    result=pd.DataFrame(index=frame.index); contributions=pd.DataFrame(index=frame.index)
    for i in items:
        if i['direction'] not in ('higher','lower') or i['normalization'] != 'minmax': raise ValueError('Supported: higher/lower direction and minmax normalization')
        x=pd.to_numeric(frame[i['name']],errors='coerce').replace([np.inf,-np.inf],np.nan)
        spread=x.max()-x.min()
        # Constant columns contain no evidence for ranking: neutral, documented 0.5.
        normalized=(x-x.min())/spread if spread>0 else x.where(x.isna(),0.5)
        if i['direction']=='lower': normalized=1-normalized
        contributions[i['name']]=normalized*i['weight']
    available=contributions.notna().mul(weights,axis=1).sum(axis=1)
    result['coverage']=available
    result['score']=contributions.sum(axis=1,min_count=1)
    if config['missing_policy']=='renormalize':
        result['score']=result['score']/available.replace(0,np.nan)
        contributions=contributions.div(available.replace(0,np.nan),axis=0)
    valid=available >= config['minimum_coverage']
    if config['missing_policy']=='withhold': valid &= contributions.notna().all(axis=1)
    result.loc[~valid,'score']=np.nan
    contributions.loc[~valid]=np.nan
    result['methodology_version']=config['version']
    return result,contributions

def sensitivity(frame, configurations):
    return {c['version']:score(frame,c) for c in configurations}
