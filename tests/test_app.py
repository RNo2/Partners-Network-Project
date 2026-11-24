"""Streamlit executes real scripts against isolated synthetic/empty databases."""
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from conftest import frame

PAGES=['Executive Overview','Community Need','Food Access Landscape','Geographic and Temporal Accessibility','Share Network Analysis','Partner Assessment','Strategic Opportunity Explorer','Resource Allocation Scenarios','Data Management','Methodology and Data Sources']

def test_all_empty_pages(tmp_path,monkeypatch):
    monkeypatch.setenv('SHARE_INTERNAL_MODE','1')
    monkeypatch.setenv('SHARE_DB',str(tmp_path/'app.sqlite'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, f'{page}: {app.exception}'


def test_loaded_navigation_and_filters(populated,provider,monkeypatch):
    monkeypatch.setenv('SHARE_INTERNAL_MODE','1')
    monkeypatch.setenv('SHARE_DB',str(populated.path))
    # Synthetic schedules and exact-period records, never actual Share data.
    sched=frame('operating_schedules',schedule_id='S1',partner_id='TEST-001',operating_day='Monday',opening_time='09:00',closing_time='12:00',distribution_frequency='weekly',verification_status='verified',source='Synthetic',last_verified='2026-01-01',visibility='internal')
    populated.import_data('operating_schedules',sched,b'sched','s.csv','Synthetic')
    rec=frame('distribution_records',record_id='D1',partner_id='TEST-001',reporting_period_start='2026-01-01',reporting_period_end='2026-01-31',pounds_sent='10',source='Synthetic',visibility='internal')
    populated.import_data('distribution_records',rec,b'd','d.csv','Synthetic')
    constraint=frame('operational_constraints',constraint_id='O1',geographic_id='SYNTHETIC-AREA',dimension='staff',qualitative_notes='Synthetic area constraint',reporting_date='2026-01-01',source='Synthetic',visibility='internal')
    populated.import_data('operational_constraints',constraint,b'o','o.csv','Synthetic')
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception,f'{page}: {app.exception}'
    app.sidebar.multiselect(key='filter_county').set_value(['Philadelphia County']).run()
    app.sidebar.radio[0].set_value('Executive Overview').run()
    assert app.sidebar.multiselect(key='filter_county').value==['Philadelphia County']
    assert app.metric[0].value=='1'
    app.sidebar.radio[0].set_value('Strategic Opportunity Explorer').run()
    assert any('constraint_id' in d.value and len(d.value)==1 for d in app.dataframe)


def test_public_mode_hides_internal(populated,monkeypatch):
    monkeypatch.setenv('SHARE_INTERNAL_MODE','1')
    monkeypatch.setenv('SHARE_DB',str(populated.path));monkeypatch.setenv('SHARE_PUBLIC_MODE','1');monkeypatch.setenv('SHARE_PUBLIC_DB',str(populated.path))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run()
    assert app.metric[0].value=='0'
    for page in ['Data Management','Share Network Analysis','Partner Assessment','Resource Allocation Scenarios']:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception
        assert not app.get('file_uploader')
        assert not app.get('download_button')

def test_default_entrypoint_is_public(monkeypatch):
    for key in ['SHARE_INTERNAL_MODE','SHARE_PUBLIC_MODE','SHARE_RELEASE_ASSETS']:
        monkeypatch.delenv(key,raising=False)
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
    assert not app.exception
    assert app.radio(key='public_section').value == 'Find food'
    assert any('official Share Food Program assessments' in item.value for item in app.info)
    assert any('438 matching' in item.value for item in app.caption)
    assert not app.get('file_uploader')
    app.text_input[0].set_value('19104').run()
    assert not app.exception
    assert 0 < len(app.get('link_button')) < 25
    assert any('19104' in item.value for item in app.text)
    app.radio(key='public_section').set_value('County snapshot').run()
    app.selectbox[0].set_value('Delaware County').run()
    assert [metric.value for metric in app.metric] == ['10.6%', '61,500', '16']
    assert any('official Share Food Program assessments' in item.value for item in app.info)
    app.radio(key='public_section').set_value('Research tools').run()
    assert app.metric[0].value=='74'
    assert any('official Share Food Program assessments' in item.value for item in app.info)
    assert 'Data Management' not in app.sidebar.radio[0].options
    assert not app.get('file_uploader')


def test_public_research_does_not_expand_unsupported_geography(monkeypatch):
    monkeypatch.delenv('SHARE_INTERNAL_MODE', raising=False)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=60).run()
    app.radio(key='public_section').set_value('Research tools').run()
    app.sidebar.radio[0].set_value('Community Need').run()
    app.sidebar.multiselect(key='filter_zip_code').set_value(['19104']).run()
    assert not app.exception
    assert not app.metric
    assert any('unavailable for these geographic filters' in item.value for item in app.info)
    assert not any(len(item.value) == 779 for item in app.dataframe)
