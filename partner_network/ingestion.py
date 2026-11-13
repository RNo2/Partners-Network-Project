"""File parsing, explicit column mapping, and row-level validation."""
import io
import json
import re
import pandas as pd
from shapely.geometry import shape
from .schema import SCHEMAS, ENUMS

MAX_BYTES = 25 * 1024 * 1024

def read_upload(data, filename, sheet=0, layer=None):
    if len(data) > MAX_BYTES:
        raise ValueError('Upload exceeds 25 MiB limit.')
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext == 'csv':
        return pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)
    if ext == 'xlsx':
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet, dtype=str, keep_default_na=False)
    if ext in ('geojson', 'gpkg'):
        import geopandas as gpd
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ('upload.' + ext)
            path.write_bytes(data)
            frame = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
        if frame.crs is None:
            raise ValueError('Geographic file needs a declared CRS.')
        frame = frame.to_crs(4326)
        result = pd.DataFrame(frame.drop(columns=frame.geometry.name))
        result['geometry_json'] = frame.geometry.map(lambda x: json.dumps(x.__geo_interface__) if x else '')
        return result.fillna('').astype(str)
    raise ValueError('Supported formats: CSV, XLSX, GeoJSON, GeoPackage. Convert legacy Excel files to XLSX.')

def map_columns(frame, mapping):
    selected = [v for v in mapping.values() if v]
    if len(selected) != len(set(selected)):
        raise ValueError('Each source column may be mapped only once.')
    return pd.DataFrame({field: frame[column] for field, column in mapping.items() if column})

def validate(category, frame, partners=None, criteria=None):
    spec = SCHEMAS[category]
    issues = []
    def issue(row, field, message, severity='error'):
        issues.append(dict(row=row, field=field, severity=severity, message=message))
    for field in spec.required.split():
        if field not in frame:
            issue(0, field, 'Missing required column')
    clean = frame.reindex(columns=spec.fields.split()).copy().fillna('')
    for field in clean:
        clean[field] = clean[field].astype(str).str.strip()
    for i, row in clean.iterrows():
        n = i + 2
        for field in spec.required.split():
            if not row[field]: issue(n, field, 'Required value missing')
        for field in spec.numeric.split():
            if row[field]:
                try:
                    val = float(row[field])
                    if not pd.notna(val) or abs(val) == float('inf'): raise ValueError()
                    if field not in ('latitude', 'longitude') and val < 0: raise ValueError()
                    clean.at[i, field] = val
                except (ValueError, TypeError): issue(n, field, 'Expected finite nonnegative number (coordinates may be signed)')
        for field in spec.dates.split():
            if row[field]:
                try:
                    from datetime import date
                    date.fromisoformat(row[field])
                except ValueError: issue(n, field, 'Expected valid ISO date YYYY-MM-DD')
        for field, choices in ENUMS.items():
            if field in clean and row[field] and row[field] not in choices:
                issue(n, field, 'Allowed: ' + ', '.join(choices))
        if category == 'partners':
            if bool(row.latitude) != bool(row.longitude): issue(n, 'latitude', 'Supply both coordinates or neither')
            for field, limit in [('latitude',90),('longitude',180)]:
                if row[field]:
                    try:
                        if not -limit <= float(row[field]) <= limit: issue(n, field, 'Coordinate out of range')
                    except ValueError: pass
            if row.zip_code and not re.fullmatch(r'\d{5}(-\d{4})?', row.zip_code): issue(n, 'zip_code', 'Expected US ZIP code')
            if not row.latitude: issue(n, 'latitude', 'Coordinates missing; site cannot be mapped', 'warning')
            if not row.last_verified: issue(n, 'last_verified', 'Verification date unknown', 'warning')
        if category in ('distribution_records','partner_assessments','operating_schedules'):
            if partners is not None and row.partner_id not in set(partners): issue(n, 'partner_id', 'Unmatched partner identifier')
        if category == 'accessibility_measurements':
            if partners is not None and row.destination_partner_id not in set(partners): issue(n, 'destination_partner_id', 'Unmatched destination')
            if not row.travel_minutes and not row.distance_km: issue(n, 'travel_minutes', 'A time or distance is required')
            if row.measurement_type == 'straight_line' and (row.travel_mode != 'straight_line' or row.travel_minutes): issue(n, 'measurement_type', 'Straight-line measurements require straight_line mode and no travel time')
        if category == 'operational_constraints' and row.partner_id and partners is not None and row.partner_id not in set(partners): issue(n, 'partner_id', 'Unmatched partner identifier')
        if category == 'operating_schedules':
            if row.verification_status == 'verified' and not row.last_verified: issue(n,'last_verified','Verified status has no verification date','warning')
            if not all(re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',row[f]) for f in ('opening_time','closing_time')):
                issue(n, 'opening_time', 'Times must be HH:MM; split overnight windows at midnight')
            elif row.opening_time >= row.closing_time: issue(n, 'closing_time', 'Closing must follow opening; split overnight windows')
        for start, end in [('reporting_period_start','reporting_period_end'),('effective_start_date','effective_end_date')]:
            if start in clean and row[start] and row[end] and row[start] > row[end]: issue(n,end,'End precedes start')
        if category == 'community_indicators':
            if row.unit not in ('count','percent','fraction','people_per_km2','households','other'): issue(n,'unit','Expected documented unit: count, percent, fraction, people_per_km2, households, other')
            try:
                if row.denominator and float(row.denominator) == 0: issue(n,'denominator','Denominator must exceed zero')
                if row.unit in ('percent','fraction') and float(row.value) > (100 if row.unit == 'percent' else 1): issue(n,'value','Rate exceeds unit range')
                if row.numerator and row.denominator and float(row.numerator)>float(row.denominator) and row.unit in ('percent','fraction'): issue(n,'numerator','Numerator exceeds denominator for a bounded rate')
                if not row.denominator and row.unit in ('percent','fraction'): issue(n,'denominator','Rate cannot be weighted without denominator','warning')
                if float(row.reporting_year) != int(float(row.reporting_year)) or not 1900 <= float(row.reporting_year) <= 2200: issue(n,'reporting_year','Expected four-digit year')
            except ValueError: pass
        if category == 'geographic_units':
            try:
                geom = shape(json.loads(row.geometry_json))
                if geom.geom_type not in ('Polygon','MultiPolygon') or not geom.is_valid or geom.is_empty: raise ValueError()
                a,b,c,d = geom.bounds
                if a < -180 or c > 180 or b < -90 or d > 90: raise ValueError()
            except Exception: issue(n,'geometry_json','Expected valid WGS84 polygon geometry')
        if category in ('distribution_records','partner_assessments','assessment_criteria','operational_constraints') and row.visibility != 'internal':
            issue(n,'visibility','This category is restricted to internal use')
        if category == 'partner_assessments' and row.rating:
            match = criteria[(criteria.criterion_id == row.criterion_id) & (criteria.framework_version == row.framework_version) & (criteria.approval_status == 'approved')] if criteria is not None and not criteria.empty else pd.DataFrame()
            if match.empty: issue(n,'rating','A rating requires a matching approved criterion and framework')
    duplicates = clean[spec.key].duplicated(keep=False)
    for i in clean.index[duplicates]: issue(i+2,spec.key,'Duplicate identifier in upload')
    return clean, pd.DataFrame(issues, columns=['row','field','severity','message'])

def infer_columns(frame):
    """Suggest types without coercing identifiers or changing source values."""
    rows=[]
    for column in frame:
        vals=frame[column].astype(str).str.strip()
        vals=vals[vals.ne('')]
        name=str(column).lower()
        if vals.empty: likely='empty / unknown'
        elif any(term in name for term in ('_id','zip','tract','geoid')): likely='text identifier (preserve zeros)'
        elif vals.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all(): likely='ISO date (validate calendar)'
        elif vals.str.fullmatch(r'\d{2}:\d{2}').all(): likely='time (HH:MM)'
        elif pd.to_numeric(vals,errors='coerce').notna().all(): likely='numeric'
        else: likely='text'
        rows.append({'column':column,'source_dtype':str(frame[column].dtype),'likely_type':likely,'missing_values':int(frame[column].astype(str).str.strip().eq('').sum())})
    return pd.DataFrame(rows)


def geographic_layers(data):
    """List GeoPackage layers so staff choose explicitly rather than importing a hidden default."""
    import geopandas as gpd
    import tempfile
    from pathlib import Path
    if len(data)>MAX_BYTES: raise ValueError('Upload exceeds 25 MiB limit.')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'upload.gpkg';path.write_bytes(data)
        return gpd.list_layers(path)['name'].tolist()
