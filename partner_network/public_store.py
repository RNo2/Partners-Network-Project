"""Read-only release assets. No SQLite initialization or mutation methods."""
from pathlib import Path
import pandas as pd
import streamlit as st
from .schema import SCHEMAS

@st.cache_data(show_spinner=False)
def read_asset(path, revision):
    return pd.read_parquet(path)

class PublicStore:
    def __init__(self,path='public_data/processed'):
        self.path=Path(path)
    def read(self,category,public=True):
        if category in ('distribution_records','partner_assessments','assessment_criteria','operational_constraints'):
            return pd.DataFrame(columns=SCHEMAS[category].fields.split())
        path=self.path/(category+'.parquet')
        if not path.exists():return pd.DataFrame(columns=SCHEMAS[category].fields.split()) if category in SCHEMAS else pd.DataFrame()
        frame=read_asset(str(path),path.stat().st_mtime_ns)
        if 'visibility' in frame:frame=frame[frame.visibility=='public']
        return frame.copy()
