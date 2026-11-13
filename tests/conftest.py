"""Synthetic fixtures only; not actual Share provider data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from partner_network.schema import SCHEMAS
from partner_network.storage import Store

@pytest.fixture
def store(tmp_path): return Store(tmp_path/'network.sqlite')

def frame(category, **overrides):
    row={f:'' for f in SCHEMAS[category].fields.split()}
    row.update(overrides)
    return pd.DataFrame([row])

@pytest.fixture
def provider():
    return frame('partners',partner_id='TEST-001',site_name='SYNTHETIC TEST SITE',latitude='40',longitude='-75',zip_code='00123',county='Philadelphia County',network_membership='share',active_status='active',source='Synthetic test fixture',last_verified='2026-01-01',visibility='internal')

@pytest.fixture
def populated(store,provider):
    store.import_data('partners',provider,b'synthetic','test.csv','Synthetic test fixture')
    return store
