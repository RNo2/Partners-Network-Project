"""Explicit local-only internal entrypoint. Never select for public hosting."""
import os
import runpy
os.environ['SHARE_INTERNAL_MODE']='1'
os.environ['SHARE_PUBLIC_MODE']='0'
os.environ['SHARE_RELEASE_ASSETS']='0'
runpy.run_path('app.py',run_name='__main__')
