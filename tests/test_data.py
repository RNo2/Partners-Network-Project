import io
import json
import pandas as pd
import pytest
from conftest import frame
from partner_network.ingestion import read_upload,map_columns,validate
from partner_network.storage import Store


def test_mapping_and_leading_zero(provider):
    raw=provider.to_csv(index=False).encode()
    parsed=read_upload(raw,'test.csv')
    assert parsed.zip_code.iloc[0]=='00123'
    renamed=parsed.rename(columns={'partner_id':'ID'})
    mapped=map_columns(renamed,{'partner_id':'ID','site_name':'site_name'})
    assert mapped.partner_id.iloc[0]=='TEST-001'
    with pytest.raises(ValueError): map_columns(parsed,{'a':'partner_id','b':'partner_id'})
    clean,issues=validate('partners',mapped)
    assert 'Missing required column' in issues.message.tolist()

@pytest.mark.parametrize('field,value',[('latitude','91'),('longitude','invalid'),('zip_code','abc'),('last_verified','2026-02-30'),('active_status','yes')])
def test_invalid_partner(provider,field,value):
    provider.loc[0,field]=value
    _,issues=validate('partners',provider)
    assert (issues.severity=='error').any()

def test_duplicate_and_missing(provider):
    _,issues=validate('partners',pd.concat([provider,provider],ignore_index=True))
    assert issues.message.str.contains('Duplicate').any()
    provider.loc[0,'site_name']=''
    assert (validate('partners',provider)[1].severity=='error').any()

def test_persistence_modes_raw_and_backup(populated,provider,tmp_path):
    db=Store(populated.path)
    assert len(db.read('partners'))==1
    assert db.raw(1)==('test.csv',b'synthetic')
    with pytest.raises(ValueError,match='already'): db.import_data('partners',provider,b'other','renamed.csv','source')
    provider.loc[0,'site_name']='Changed test site'
    with pytest.raises(ValueError,match='conflict'): db.import_data('partners',provider,b'changed','x.csv','source')
    db.import_data('partners',provider,b'changed','x.csv','source','update')
    assert db.read('partners').site_name.iloc[0]=='Changed test site'
    provider.loc[0,'partner_id']='TEST-002'
    db.import_data('partners',provider,b'replacement','x.csv','source','replace')
    assert db.read('partners').partner_id.tolist()==['TEST-002']
    target=tmp_path/'backup.sqlite'; target.write_bytes(db.backup())
    assert Store(target).read('partners').partner_id.tolist()==['TEST-002']
    assert len(db.history())==3

def test_rollback_and_references(populated,provider):
    rec=frame('distribution_records',record_id='R1',partner_id='TEST-001',reporting_period_start='2026-01-01',reporting_period_end='2026-01-31',pounds_received='10',source='Synthetic',visibility='internal')
    populated.import_data('distribution_records',rec,b'r1','r.csv','test')
    rec.loc[0,'record_id']='R2'
    rec.loc[0,'reporting_period_start']='2026-01-15'
    with pytest.raises(ValueError,match='Overlapping'): populated.import_data('distribution_records',rec,b'r2','r.csv','test')
    assert len(populated.read('distribution_records'))==1
    assert len(populated.history())==2
    provider.loc[0,'partner_id']='OTHER'
    with pytest.raises(Exception): populated.import_data('partners',provider,b'new','r.csv','test','replace')
    assert populated.read('partners').partner_id.tolist()==['TEST-001']
    assert len(populated.history())==2

def test_unmatched_missing_negative(populated):
    rec=frame('distribution_records',record_id='R1',partner_id='NO-SITE',reporting_period_start='bad',reporting_period_end='2026-01-31',pounds_received='-10',source='Synthetic',visibility='internal')
    _,issues=validate('distribution_records',rec,populated.read('partners').partner_id)
    assert len(issues[issues.severity=='error'])>=3
    with pytest.raises(ValueError): populated.import_data('distribution_records',rec,b'bad','test.csv','source')
    assert populated.read('distribution_records').empty

def test_visibility_and_assessment(populated,provider):
    assert populated.read('partners',True).empty
    provider.loc[0,'visibility']='public'
    populated.import_data('partners',provider,b'public','pub.csv','source','update')
    assert len(populated.read('partners',True))==1
    assessment=frame('partner_assessments',assessment_id='A1',partner_id='TEST-001',framework_version='v1',rating='good',assessment_date='2026-01-01',review_status='draft',source='Synthetic',visibility='internal')
    with pytest.raises(ValueError): populated.import_data('partner_assessments',assessment,b'a','a.csv','test')
    assessment.loc[0,'rating']=''
    populated.import_data('partner_assessments',assessment,b'notes','a.csv','test')
    assert len(populated.read('partner_assessments'))==1
    assessment.loc[0,'visibility']='public'
    assert (validate('partner_assessments',assessment)[1].severity=='error').any()

def test_excel_and_geojson(tmp_path):
    output=io.BytesIO()
    with pd.ExcelWriter(output) as writer: pd.DataFrame({'id':['001']}).to_excel(writer,index=False,sheet_name='sites')
    assert read_upload(output.getvalue(),'data.xlsx','sites').id.iloc[0]=='001'
    raw=json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','properties':{'geographic_id':'001'},'geometry':{'type':'Polygon','coordinates':[[[-75,40],[-75,41],[-74,41],[-74,40],[-75,40]]]}}]}).encode()
    g=read_upload(raw,'data.geojson')
    assert g.geographic_id.iloc[0]=='001'
    assert json.loads(g.geometry_json.iloc[0])['type']=='Polygon'
    import geopandas as gpd
    geo=gpd.read_file(io.BytesIO(raw)); path=tmp_path/'test.gpkg';geo.to_file(path,driver='GPKG')
    from partner_network.ingestion import geographic_layers
    layers=geographic_layers(path.read_bytes())
    assert len(layers)==1
    assert len(read_upload(path.read_bytes(),'test.gpkg',layer=layers[0]))==1

def test_geography_validation():
    f=frame('geographic_units',unit_id='u',geographic_id='x',geographic_resolution='tract',name='Synthetic',geometry_json='{}',source='test',vintage='2020',visibility='public')
    assert (validate('geographic_units',f)[1].severity=='error').any()

def test_type_inference_and_warning_acknowledgement(store,provider):
    from partner_network.ingestion import infer_columns
    types=infer_columns(pd.DataFrame({'zip_code':['00123'],'amount':['12.5'],'date':['2026-01-01']})).set_index('column').likely_type
    assert types.zip_code.startswith('text identifier')
    assert types.amount=='numeric'
    assert types.date.startswith('ISO date')
    provider.loc[0,'last_verified']=''
    with pytest.raises(ValueError,match='Acknowledge'): store.import_data('partners',provider,b'test','test.csv','source')
    assert store.history().empty
    store.import_data('partners',provider,b'test','test.csv','source',allow_warnings=True)
    assert store.history().validation_status.iloc[0]=='warnings acknowledged'

def test_assessment_approved_framework(populated):
    criterion=frame('assessment_criteria',criterion_id='C1',label='Synthetic criterion',definition='Synthetic not approved Share criteria',framework_version='fixture-v1',approval_status='approved',source='Synthetic fixture',visibility='internal')
    populated.import_data('assessment_criteria',criterion,b'criterion','c.csv','source')
    assessment=frame('partner_assessments',assessment_id='A1',partner_id='TEST-001',criterion_id='C1',framework_version='fixture-v1',rating='source rating',assessment_date='2026-01-01',review_status='draft',source='Synthetic fixture',visibility='internal')
    populated.import_data('partner_assessments',assessment,b'assessment','a.csv','source')
    assessment.loc[0,'framework_version']='wrong'
    assert (validate('partner_assessments',assessment,criteria=populated.read('assessment_criteria'))[1].severity=='error').any()
