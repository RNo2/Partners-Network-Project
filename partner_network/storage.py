"""Versioned SQLite storage; raw uploads and records commit in one transaction."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import pandas as pd
from .schema import SCHEMAS
from .ingestion import validate

class Store:
    def __init__(self, path='data/network.sqlite'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            con.execute('PRAGMA journal_mode=WAL')
            con.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
            con.execute('CREATE TABLE IF NOT EXISTS dataset_imports (import_id INTEGER PRIMARY KEY, category TEXT NOT NULL, filename TEXT NOT NULL, imported_at TEXT NOT NULL, source TEXT NOT NULL, reporting_period TEXT, mode TEXT NOT NULL, record_count INTEGER NOT NULL, accepted_count INTEGER NOT NULL, rejected_count INTEGER NOT NULL, validation_status TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL, raw_data BLOB NOT NULL, validation_report TEXT NOT NULL)')
            for name, spec in SCHEMAS.items():
                columns = []
                for field in spec.fields.split():
                    kind = 'REAL' if field in spec.numeric.split() else 'TEXT'
                    columns.append(f'"{field}" {kind}' + (' PRIMARY KEY' if field == spec.key else ''))
                columns.append('import_id INTEGER NOT NULL REFERENCES dataset_imports(import_id)')
                if 'partner_id' in spec.fields.split() and name != 'partners':
                    columns.append('FOREIGN KEY(partner_id) REFERENCES partners(partner_id)')
                if name == 'accessibility_measurements': columns.append('FOREIGN KEY(destination_partner_id) REFERENCES partners(partner_id)')
                con.execute(f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(columns)})')
            con.execute('CREATE TABLE IF NOT EXISTS scenarios (scenario_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, name TEXT NOT NULL, strategy TEXT NOT NULL, payload TEXT NOT NULL)')
            con.execute('CREATE TABLE IF NOT EXISTS analysis_configurations (version TEXT PRIMARY KEY, config TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0)')
            con.execute('CREATE TABLE IF NOT EXISTS analysis_runs (run_id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, methodology_version TEXT NOT NULL REFERENCES analysis_configurations(version), input_revision INTEGER NOT NULL, output_json TEXT NOT NULL)')
            con.execute('INSERT OR IGNORE INTO schema_migrations VALUES (1, ?)', (self.now(),))

    @staticmethod
    def now(): return datetime.now(timezone.utc).isoformat()

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.path)
        con.execute('PRAGMA foreign_keys=ON')
        try:
            with con: yield con
        finally: con.close()

    def read(self, category, public=False):
        if category not in SCHEMAS: raise ValueError('Unknown dataset')
        with self.connection() as con:
            frame = pd.read_sql_query(f'SELECT * FROM "{category}"' + (' WHERE visibility = ?' if public else ''), con, params=['public'] if public else [])
        return frame

    def history(self):
        with self.connection() as con:
            return pd.read_sql_query('SELECT import_id,category,filename,imported_at,source,reporting_period,mode,record_count,accepted_count,rejected_count,validation_status FROM dataset_imports ORDER BY import_id DESC', con)

    def import_data(self, category, frame, raw, filename, source, mode='append', allow_warnings=False):
        if mode not in ('append','update','replace'): raise ValueError('Invalid import mode')
        if not source.strip(): raise ValueError('Import source is required')
        frame = frame.reset_index(drop=True)
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            partners = pd.read_sql_query('SELECT partner_id FROM partners',con).partner_id
            criteria = pd.read_sql_query('SELECT * FROM assessment_criteria',con)
            clean, issues = validate(category, frame, partners=partners, criteria=criteria)
            if (issues.severity == 'error').any(): raise ValueError('Validation errors must be resolved; nothing imported')
            if not issues.empty and not allow_warnings: raise ValueError('Acknowledge validation warnings before import')
            if clean.empty: raise ValueError('No records to import')
            spec = SCHEMAS[category]
            # Semantic fingerprint blocks repeat uploads regardless of filename, order, or mode.
            canonical = clean.sort_values(spec.key).to_json(orient='records')
            fingerprint = hashlib.sha256((category + canonical).encode()).hexdigest()
            if con.execute('SELECT 1 FROM dataset_imports WHERE fingerprint=?',(fingerprint,)).fetchone(): raise ValueError('This dataset has already been imported')
            old = {r[0] for r in con.execute(f'SELECT "{spec.key}" FROM "{category}"')}
            new = set(clean[spec.key])
            if mode == 'append' and old & new: raise ValueError('Existing identifiers conflict; choose update explicitly')
            if mode == 'update' and new - old: raise ValueError('Update requires existing identifiers; append new records separately')
            if mode == 'replace':
                # Keep retained parent IDs in place so referenced children remain valid.
                removed = old - new
                for key in removed: con.execute(f'DELETE FROM "{category}" WHERE "{spec.key}"=?',(key,))
            periods = sorted(set(clean.get('reporting_period_start',pd.Series(dtype=str)).astype(str) + '/' + clean.get('reporting_period_end',pd.Series(dtype=str)).astype(str)))
            cursor = con.execute('INSERT INTO dataset_imports (category,filename,imported_at,source,reporting_period,mode,record_count,accepted_count,rejected_count,validation_status,fingerprint,raw_data,validation_report) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (category,Path(filename.replace('\\','/')).name,self.now(),source,json.dumps(periods),mode,len(frame),len(clean),0,'warnings acknowledged' if not issues.empty else 'valid',fingerprint,raw,issues.to_json(orient='records')))
            import_id = cursor.lastrowid
            fields = spec.fields.split() + ['import_id']
            marks = ','.join('?' for _ in fields)
            names = ','.join('"'+f+'"' for f in fields)
            updates = ','.join(f'"{f}"=excluded."{f}"' for f in fields if f != spec.key)
            sql = f'INSERT INTO "{category}" ({names}) VALUES ({marks})'
            if mode in ('update','replace'): sql += f' ON CONFLICT("{spec.key}") DO UPDATE SET {updates}'
            for record in clean.to_dict(orient='records'):
                vals = [None if record[f] == '' else record[f] for f in spec.fields.split()]
                con.execute(sql, vals + [import_id])
            self._check_distribution(con)
            self._check_geographies(con)
            return import_id

    @staticmethod
    def _check_distribution(con):
        rows = con.execute('SELECT partner_id,reporting_period_start,reporting_period_end FROM distribution_records ORDER BY partner_id,reporting_period_start').fetchall()
        previous = {}
        for partner, start, end in rows:
            if partner in previous and start <= previous[partner]: raise ValueError('Overlapping reporting periods for a partner; import rolled back')
            previous[partner] = end

    @staticmethod
    def _check_geographies(con):
        if con.execute('SELECT 1 FROM geographic_units GROUP BY geographic_id,geographic_resolution,vintage HAVING COUNT(*)>1').fetchone(): raise ValueError('Duplicate geography/resolution/vintage; import rolled back')
        if con.execute('SELECT 1 FROM community_indicators GROUP BY indicator_name,geographic_id,geographic_resolution,reporting_year,unit,source,vintage HAVING COUNT(*)>1').fetchone(): raise ValueError('Duplicate indicator observation; import rolled back')

    def raw(self, import_id):
        with self.connection() as con: return con.execute('SELECT filename,raw_data FROM dataset_imports WHERE import_id=?',(int(import_id),)).fetchone()

    def save_scenario(self, name, strategy, payload):
        if strategy not in ('Go deep','Go wide','Network optimization'): raise ValueError('Unknown strategy')
        with self.connection() as con:
            con.execute('INSERT INTO scenarios(created_at,name,strategy,payload) VALUES (?,?,?,?)',(self.now(),name,strategy,json.dumps(payload,allow_nan=False)))

    def scenarios(self):
        with self.connection() as con: return pd.read_sql_query('SELECT * FROM scenarios ORDER BY scenario_id DESC',con)

    def backup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'backup.sqlite'
            dest = sqlite3.connect(path)
            with self.connection() as source: source.backup(dest)
            dest.close()
            return path.read_bytes()
