"""Streamlit Community Cloud entrypoint: public asset reader only."""
import os
import runpy
os.environ['SHARE_PUBLIC_MODE']='1'
os.environ['SHARE_RELEASE_ASSETS']='1'
runpy.run_path('app.py',run_name='__main__')
