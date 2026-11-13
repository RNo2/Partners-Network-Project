"""Local Share Food Program strategic intelligence workspace."""
import io
import json
import os
from datetime import date
from pathlib import Path
import pandas as pd
import streamlit as st
from partner_network.schema import SCHEMAS, DESCRIPTIONS
from partner_network.storage import Store
from partner_network.ingestion import read_upload, map_columns, validate, infer_columns, geographic_layers
from partner_network.analytics import (filter_partners, coverage, nearby_pairs, indicator_values,
    aggregate_indicator, providers_near_units, eligible_schedules, weekly_hours, schedule_overlap, distribution_summary, scenario_budget)
from partner_network.visualization import landscape_map, weekly_chart

st.set_page_config(page_title='Regional Food Access | Partner Network Intelligence',layout='wide')
st.markdown('''<style>.stApp{background:#f6f7f9}h1,h2,h3{color:#172b43}section[data-testid="stSidebar"]{background:#e8edf1}.stMetric{border-top:2px solid #20806a;padding-top:12px}div[data-testid="stCaptionContainer"]{color:#425466}</style>''',unsafe_allow_html=True)
# Public is the safe default even if hosting selects app.py directly.
INTERNAL = os.environ.get('SHARE_INTERNAL_MODE','0') == '1'
PUBLIC = not INTERNAL or os.environ.get('SHARE_PUBLIC_MODE','0') == '1'
RELEASE = PUBLIC and (not INTERNAL or os.environ.get('SHARE_RELEASE_ASSETS','0') == '1')
if RELEASE:
    from partner_network.public_store import PublicStore
    store=PublicStore()
    coverage=st.cache_data(show_spinner=False)(coverage)
    nearby_pairs=st.cache_data(show_spinner=False)(nearby_pairs)
else:
    store=Store(os.environ.get('SHARE_PUBLIC_DB','data/public.sqlite') if PUBLIC else os.environ.get('SHARE_DB','data/network.sqlite'))
PAGES=['Executive Overview','Community Need','Food Access Landscape','Geographic and Temporal Accessibility','Share Network Analysis','Partner Assessment','Strategic Opportunity Explorer','Resource Allocation Scenarios','Data Management','Methodology and Data Sources']
st.sidebar.title('FOOD ACCESS')
st.sidebar.caption('PARTNER NETWORK INTELLIGENCE')
st.sidebar.info('Regional public observatory · V1.0' if PUBLIC else 'Internal workspace · local storage')
page=st.sidebar.radio('Workspace',PAGES)
all_partners=store.read('partners',PUBLIC)
if RELEASE and not st.sidebar.checkbox('Include benefits-assistance offices',value=False):
    all_partners=all_partners[all_partners.partner_type.ne('public benefits')]
filters={}
with st.sidebar.expander('Provider filters',expanded=True):
    for field,label in [('county','County'),('zip_code','ZIP code'),('neighborhood','Neighborhood'),('census_tract','Census tract'),('partner_type','Provider type'),('active_status','Status'),('network_membership','Network'),('source','Provider source')]:
        options=sorted(all_partners[field].dropna().unique().tolist())
        # Keep selections in session state across pages.
        filters[field]=st.multiselect(label,options,key='filter_'+field)
partners=filter_partners(all_partners,filters)
if RELEASE:
    parsed_day=st.sidebar.selectbox('Published operating day (parsed windows)', ['All','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
    if parsed_day!='All':
        supplied=store.read('operating_schedules')
        partners=partners[partners.partner_id.isin(supplied[supplied.operating_day==parsed_day].partner_id)]
        st.sidebar.caption('This filter uses structured source windows only. Unparsed or missing hours are unknown and excluded.')

def data(name):
    frame=store.read(name,PUBLIC)
    if 'partner_id' in frame and name!='partners':
        linked=frame.partner_id.isin(partners.partner_id)
        if name=='operational_constraints': linked |= frame.partner_id.isna() | frame.partner_id.eq('')
        frame=frame[linked]
    if 'destination_partner_id' in frame: frame=frame[frame.destination_partner_id.isin(partners.partner_id)]
    return frame

def geographies():
    units=data('geographic_units')
    if filters['county']: units=units[units.county.isin(filters['county'])]
    for field,resolution in [('zip_code','zip'),('census_tract','tract')]:
        if filters[field]: units=units[(units.geographic_resolution==resolution)&units.geographic_id.isin(filters[field])]
    if filters['neighborhood']: units=units[(units.geographic_resolution=='neighborhood')&units['name'].isin(filters['neighborhood'])]
    if not units.empty:
        resolution=st.selectbox('Boundary resolution',sorted(units.geographic_resolution.unique()),index=list(sorted(units.geographic_resolution.unique())).index('tract') if 'tract' in units.geographic_resolution.unique() else 0,key=page+'_resolution')
        units=units[units.geographic_resolution==resolution]
        vintage=st.selectbox('Boundary vintage',sorted(units.vintage.unique()),key=page+'_vintage')
        units=units[units.vintage==vintage]
        selection=st.multiselect('Geographic areas',units.geographic_id.tolist(),format_func=lambda x: str(units.set_index('geographic_id').loc[x,'name']),key=page+'_areas')
        if selection: units=units[units.geographic_id.isin(selection)]
    return units

def table(frame,filename='analysis.csv'):
    if frame.empty: st.info('No matching published records for this selection.')
    else:
        st.dataframe(frame,hide_index=True,width='stretch')
        st.download_button('Download displayed records',frame.to_csv(index=False).encode(),filename,'text/csv',key=page+filename)

def choose_indicator(units=None):
    frame=data('community_indicators')
    if units is not None and not units.empty:
        frame=frame.merge(units[['geographic_id','geographic_resolution']],on=['geographic_id','geographic_resolution'])
    if frame.empty: return frame
    for field,label in [('indicator_name','Indicator'),('geographic_resolution','Geographic resolution'),('reporting_year','Reporting year'),('unit','Unit: count and rate are separate measures'),('source','Source'),('vintage','Indicator vintage')]:
        options=sorted(frame[field].dropna().unique().tolist())
        selected=st.selectbox(label,options,key=page+'_indicator_'+field)
        frame=frame[frame[field]==selected]
    return indicator_values(frame)

st.title(page)
st.caption('Philadelphia · Montgomery · Delaware counties, Pennsylvania')
if PUBLIC:
    st.info('This platform is an exploratory prototype based on publicly available data. Public directories may be incomplete or outdated. Findings should not be interpreted as official Share Food Program assessments.')
if any(filters.values()): st.caption('All provider-linked results use the sidebar selection. Community indicators use explicitly selected geographic boundaries, not provider counts.')
if page=='Executive Overview':
    st.subheader('How should limited resources improve food access?')
    st.write('Compare strengthening existing partners, expanding geographic coverage, and improving network coordination. Community need, partner assessment, and operational feasibility remain separate evidence streams.')
    if all_partners.empty: st.warning('No organizational or public records have been loaded. No strategic conclusions or rankings are available.')
    cols=st.columns(4)
    for col,label,value in zip(cols,['Share providers','External providers','Unknown affiliation','Active providers'],[sum(partners.network_membership=='share'),sum(partners.network_membership=='external'),sum(partners.network_membership=='unknown'),sum(partners.active_status=='active')]): col.metric(label,int(value))
    if not partners.empty:
        st.warning(f'{partners.latitude.isna().sum()} selected providers lack coordinates; {partners.last_verified.isna().sum()} lack a verification date. Directories may be incomplete. Nearby providers do not establish available capacity.')
        st.plotly_chart(landscape_map(partners),width='stretch')
    readiness=[]
    for name in SCHEMAS:
        f=data(name)
        readiness.append({'Dataset':name,'Visible records':len(f),'Readiness':'Awaiting data' if f.empty else 'Available; review source and completeness'})
    table(pd.DataFrame(readiness),'readiness.csv')
    if RELEASE:
        st.subheader('County food insecurity · 2024 estimates')
        facts=store.read('community_indicators')
        facts=facts[(facts.geographic_resolution=='county') & (facts.indicator_name=='Food insecurity rate')]
        table(facts[['county','value','unit','reporting_year','source','source_url']],'county_food_insecurity.csv')
        st.caption('Feeding America Map the Meal Gap, 2026 release. County estimates are not disaggregated into tracts. Benefits offices are excluded from the food-provider view by default.')
    if not PUBLIC:
        history=store.history()
        if not history.empty: st.caption('Most recent import: '+history.imported_at.iloc[0])
    st.info('No approved opportunity weights or partner evaluation standards are supplied. No composite ranking is displayed.')

    if RELEASE: st.caption('Source coverage: Philadelphia official city feed; Montgomery PA MAHN member map; Delaware County March 2026 state-assisted pantry list. Published hours have uneven coverage and are subject to change.')

elif page=='Food Access Landscape':
    st.write('Share partners and external food resources are distinct. Unknown affiliation remains unknown. The status filter controls mapped records; coverage calculations use active records.')
    units=geographies()
    st.plotly_chart(landscape_map(partners,units),width='stretch')
    table(partners.drop(columns=['import_id'],errors='ignore'),'providers.csv')
    if RELEASE:
        with st.expander('Possible shared-address records · retained for review'):
            st.dataframe(store.read('duplicate_candidates'),hide_index=True,width='stretch')
    st.caption('Coordinates are supplied, not geocoded automatically. Sources and last-verified dates remain visible. A public directory is not a complete census of services.')

elif page=='Community Need':
    units=geographies()
    indicators=choose_indicator(units)
    if indicators.empty: st.info('Upload community indicators with actual geographic identifiers, units, year, source, vintage, and methodology. Upload matching boundaries for mapping.')
    else:
        table(indicators,'community_need.csv')
        try:
            total=aggregate_indicator(indicators)
            st.metric('Selected-area aggregate · assumes non-overlapping units','Unavailable' if pd.isna(total) else f'{total:,.2f}')
        except ValueError as e: st.info(str(e))
        if not units.empty: st.plotly_chart(landscape_map(partners,units,indicators),width='stretch')
        else: st.info('Matching boundary files are needed for a choropleth. Values are available above.')
        st.caption('Rates use supplied numerators and denominators when available. Unweighted percentages are never averaged. County and tract estimates are not interchangeable.')

    if RELEASE:
        with st.expander('USDA retailer access · separate from pantry access'):
            st.write('2025 SNAP-authorized Retailer Access Map, July 2026 release. These are retailer-access indicators on 2020 tract geography; they do not measure pantry access. Demographic inputs have their own vintages.')
            dataset=st.selectbox('Retailer-access dataset',['usda_general','usda_straight','usda_driving'])
            retail=store.read(dataset)
            if not units.empty: retail=retail[retail.CensusTract20.isin(units.geographic_id)]
            table(retail,'retailer_access.csv')
            if not retail.empty and not units.empty:
                fields=[c for c in retail.select_dtypes('number').columns if c!='CensusTract20']
                metric=st.selectbox('Retailer-access measure (source variable code)',fields)
                st.caption('See the source variable lookup in Data Sources before interpreting this field. Missing and unmatched tracts remain gray.')
                mapped=pd.DataFrame({'geographic_id':retail.CensusTract20,'geographic_resolution':'tract','display_value':retail[metric],'unit':metric})
                st.plotly_chart(landscape_map(partners.iloc[:0],units,mapped),width='stretch')

elif page=='Geographic and Temporal Accessibility':
    radius=st.number_input('Exploratory straight-line radius (km)',min_value=0.1,value=1.0,step=0.1)
    st.caption('User-selected screening radius, not an approved access standard. No walking or transit times are inferred.')
    active=partners[partners.active_status.ne('inactive') if PUBLIC else partners.active_status.eq('active')]
    units=geographies()
    if not units.empty:
        table(coverage(units,active,radius,include_unknown=PUBLIC),'coverage.csv')
        st.caption('Public coverage includes source-documented sites of unknown current operating status. Inside counts use actual supplied polygons. Proximity uses one interior representative point per polygon and is not a population-weighted accessibility measure. Zero means no matching documented provider, not no actual service.')
    if not units.empty:
        active=providers_near_units(active,units,radius)
        st.caption('Pair and schedule analysis is restricted to providers inside the selected polygons or their exploratory straight-line buffer (regional UTM projection). Missing-coordinate sites are excluded.')
    pairs=nearby_pairs(active,radius)
    if RELEASE:
        from partner_network.visualization import transit_map
        st.subheader('SEPTA infrastructure · published GTFS')
        routes=store.read('gtfs_routes')
        stops=store.read('gtfs_stops')
        shapes=store.read('gtfs_shapes')
        if not routes.empty:
            selected_routes=st.multiselect('SEPTA routes (empty selection shows all)',sorted(routes.route_id.unique()))
            if selected_routes: shapes=shapes[shapes.route_id.isin(selected_routes)]
            show_stops=st.checkbox('Show stop points',value=True)
            st.plotly_chart(transit_map(active,units,stops if show_stops else stops.iloc[:0],shapes),width='stretch')
            st.caption(f'{len(stops):,} regional stops; {len(routes)} route records. Representative route shapes and scheduled infrastructure, not transit travel times. Feed service calendars are available in the source assets.')
    st.subheader('Nearby provider pairs')
    table(pairs,'nearby_pairs.csv')
    st.subheader('Supplied routing measurements')
    measures=data('accessibility_measurements')
    measures=measures[measures.destination_partner_id.isin(active.partner_id)]
    if not units.empty: measures=measures[measures.origin_geographic_id.isin(units.geographic_id)]
    if not measures.empty:
        modes=st.multiselect('Travel modes',sorted(measures.travel_mode.unique()))
        if modes: measures=measures[measures.travel_mode.isin(modes)]
    table(measures,'accessibility_measurements.csv')
    if measures.empty or not measures.travel_mode.eq('transit').any(): st.info('Transit accessibility is unknown. Supply dated routing measurements; stop proximity is not proof of access.')
    if RELEASE:
        with st.expander('Published schedule text · includes unparsed and irregular hours'):
            st.dataframe(active[['site_name','county','published_schedule','source']],hide_index=True,width='stretch')
    st.subheader('Weekly operating windows')
    as_of=st.date_input('Schedule effective on',date.today())
    schedules=data('operating_schedules')
    schedules=schedules[schedules.partner_id.isin(active.partner_id)]
    verified=eligible_schedules(schedules,as_of,verified_only=not PUBLIC)
    st.caption(f'{len(schedules)} supplied windows; {len(verified)} source-published and effective on selected date (not independently verified). Only frequency exactly “weekly” contributes to the heatmap and overlap calculations. Other frequencies remain in the source table.')
    hours=weekly_hours(verified)
    if not hours.empty: st.plotly_chart(weekly_chart(hours,active),width='stretch')
    else: st.info('No usable source-published weekly schedules available. Missing schedules are unknown availability.')
    day=st.selectbox('Operating day',['All']+['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
    day_windows=verified if day=='All' else verified[verified.operating_day==day]
    table(day_windows.merge(active[['partner_id','site_name','network_membership']],on='partner_id'),'operating_windows.csv')
    st.plotly_chart(landscape_map(active[active.partner_id.isin(day_windows.partner_id)]),width='stretch')
    with st.expander('All supplied windows, including unverified or expired'):
        st.dataframe(schedules[schedules.partner_id.isin(active.partner_id)],hide_index=True,width='stretch')
    st.subheader('Nearby published weekly schedule overlap')
    table(schedule_overlap(pairs,verified),'schedule_overlap.csv')
    st.caption('Simultaneous scheduled availability does not establish duplicated utilization or justify closing a site. Monthly and irregular windows are not assigned invented dates.')

elif page=='Share Network Analysis':
    if PUBLIC:
        st.write('Publicly documented Share-affiliated providers. Affiliation is retained only where the publisher explicitly names Share. Other affiliations remain unknown.')
        table(partners[partners.network_membership=='share'],'public_share_providers.csv')
        st.info('Pounds sent, pounds distributed and people served await authorized internal Share data. They are not estimated from provider locations.')
    else:
        share=partners[partners.network_membership=='share']
        records=data('distribution_records')
        records=records[records.partner_id.isin(share.partner_id)]
        if not records.empty:
            periods=records[['reporting_period_start','reporting_period_end']].drop_duplicates().sort_values('reporting_period_start')
            labels=periods.apply(lambda r:r.reporting_period_start+' / '+r.reporting_period_end,axis=1).tolist()
            selected=st.multiselect('Exact reporting intervals',labels,default=labels)
            records=records[(records.reporting_period_start+' / '+records.reporting_period_end).isin(selected)]
        summary=distribution_summary(records)
        table(summary,'distribution_summary.csv')
        if not summary.empty:
            import plotly.express as px
            st.plotly_chart(px.bar(summary,x='reporting_period_start',y=['pounds_sent','pounds_received','pounds_distributed'],barmode='group',labels={'value':'Pounds','reporting_period_start':'Exact interval start'}),width='stretch')
        table(records,'share_distribution_records.csv')
        st.caption('Counts of reported sites accompany sums. Missing values remain unknown; households and individuals may recur across events and are not deduplicated people. Received minus distributed is an accounting difference, not waste. Volume alone is not effectiveness.')

elif page=='Partner Assessment':
    st.write('Partner review is separate from geographic community need. Share has not supplied its final assessment framework. No default criteria, weights, ratings, or standards have been invented.')
    if PUBLIC: st.info('Partner assessments and framework records are internal only.')
    else:
        criteria=data('assessment_criteria')
        st.subheader('Source-provided criteria and framework versions')
        table(criteria,'assessment_criteria.csv')
        st.subheader('Assessments, notes, services, and review status')
        assessments=data('partner_assessments')
        table(assessments,'partner_assessments.csv')
        st.info('Use the assessment templates in Data Management. Notes may be recorded without ratings. A rating requires a matching criterion and approved framework version; approval is supplied by Share, not inferred by this application. No numeric scoring is performed.')

elif page=='Strategic Opportunity Explorer':
    st.write('Compare area evidence without a composite ranking. No provider-capacity, population-reach, or unmet-demand claim follows from location counts alone.')
    units=geographies()
    radius=st.number_input('Exploratory radius from area representative point (km)',min_value=0.1,value=1.0)
    indicators=choose_indicator(units)
    if not units.empty:
        profile=coverage(units,partners,radius,include_unknown=PUBLIC)
        if not indicators.empty:
            profile=profile.merge(indicators[['geographic_id','geographic_resolution','display_value','unit','source','reporting_year']],on=['geographic_id','geographic_resolution'],how='left')
        profile['assessment']='Further data required: capacity, routing, source completeness and operational feasibility'
        table(profile,'area_evidence.csv')
    else: st.info('Upload boundaries and community indicators to compare areas at a documented resolution.')
    if not PUBLIC:
        st.subheader('Source-provided operational constraints')
        constraints=data('operational_constraints')
        if not units.empty: constraints=constraints[constraints.geographic_id.isin(units.geographic_id)|constraints.partner_id.isin(partners.partner_id)]
        table(constraints,'operational_constraints.csv')
    st.info('Immediate, short-term, or expansion classifications await approved criteria. Missing capacity information prevents feasibility conclusions.')

elif page=='Resource Allocation Scenarios':
    st.write('Deep, wide, or network optimization: compare explicit proposals against one additional-food budget for one reporting interval. These are staff-entered scenarios, not predictions or optimized recommendations.')
    if PUBLIC:
        strategy=st.radio('Explore a strategy',['GO DEEP','GO WIDE','NETWORK OPTIMIZATION'],horizontal=True)
        prompts={'GO DEEP':'Examine explicitly Share-affiliated sites alongside nearby community need. Capacity, food volumes and partner assessment remain unknown.','GO WIDE':'Compare tract need and the combined documented provider inventory. Missing directory records are not proof of an unmet service gap.','NETWORK OPTIMIZATION':'Explore nearby providers and published schedules for coordination opportunities. Proximity alone does not justify consolidation.'}
        st.write(prompts[strategy])
        units=geographies()
        indicators=choose_indicator(units)
        if not units.empty:
            radius=st.slider('Exploratory proximity radius (km)',0.25,5.0,1.0,0.25)
            evidence=coverage(units,partners,radius,include_unknown=True)
            if not indicators.empty: evidence=evidence.merge(indicators[['geographic_id','display_value','unit','source']],on='geographic_id',how='left')
            table(evidence,'strategy_evidence.csv')
            st.plotly_chart(landscape_map(partners[partners.network_membership=='share'] if strategy=='GO DEEP' else partners,units,indicators),width='stretch')
        st.caption('Interactive evidence comparison only: no invented pounds, financial returns, capacity or optimization results. User controls change the view; no proposals are saved publicly.')
    else:
        strategy=st.selectbox('Strategy',['Go deep','Go wide','Network optimization'])
        prompts={'Go deep':'Strengthen existing partners: capacity, operating windows, distribution or services.','Go wide':'Investigate a documented geographic gap or new partnership, considering external resources.','Network optimization':'Explore coordination, schedule changes or a hub; proximity alone does not justify consolidation.'}
        st.info(prompts[strategy])
        with st.form('scenario'):
            name=st.text_input('Scenario name')
            budget=st.number_input('Additional food budget (pounds)',min_value=0.0,value=0.0)
            start=st.date_input('Reporting period start',date.today())
            end=st.date_input('Reporting period end',date.today())
            proposal=st.data_editor(pd.DataFrame(columns=['target_id','action','additional_pounds','evidence_source','expected_benefit','capacity_requirements','unknowns']),num_rows='dynamic',key='proposal_'+strategy,width='stretch')
            rationale=st.text_area('Rationale and evidence limitations')
            save=st.form_submit_button('Validate and save internal scenario')
        if save:
            try:
                if not name.strip() or proposal.empty or end<start: raise ValueError('Provide a name, proposal rows and a valid reporting interval')
                if proposal.isna().any().any() or proposal.astype(str).apply(lambda s:s.str.strip().eq('')).any().any(): raise ValueError('Complete every proposal field; write “unknown” where evidence is absent')
                if strategy in ('Go deep','Network optimization') and not proposal.target_id.isin(partners[partners.network_membership=='share'].partner_id).all(): raise ValueError('Deep and optimization target IDs must be existing selected Share partners')
                if strategy=='Go wide' and not proposal.target_id.isin(data('geographic_units').geographic_id).all(): raise ValueError('Wide target IDs must match an uploaded geographic area')
                result=scenario_budget(proposal,budget)
                if not result['within_budget']: raise ValueError('Proposed allocations exceed the food budget')
                payload={'budget':budget,'period_start':str(start),'period_end':str(end),'proposals':proposal.to_dict(orient='records'),'budget_check':result,'rationale':rationale,'input_import_ids':store.history().import_id.tolist(),'status':'Unvalidated staff proposal; benefits not estimated'}
                store.save_scenario(name,strategy,payload)
                st.success('Saved as an unvalidated proposal. Review food variety, warehouse, transport, staff and relationship capacity before action.')
            except (ValueError,TypeError) as e: st.error(str(e))
        scenarios=store.scenarios()
        if not scenarios.empty:
            summaries=[]
            for _,r in scenarios.iterrows():
                p=json.loads(r.payload)
                summaries.append({'scenario_id':r.scenario_id,'name':r['name'],'strategy':r.strategy,'period_start':p['period_start'],'period_end':p['period_end'],'budget_pounds':p['budget'],**p['budget_check'],'status':p['status']})
            table(pd.DataFrame(summaries),'scenario_comparison.csv')
            st.download_button('Export full scenario evidence',scenarios.to_json(orient='records'),'scenario_evidence.json','application/json')
            st.caption('Compare budgets only for the same interval. Expected benefits are staff hypotheses. This framework does not estimate marginal impact, choose a winner, or solve hub routing.')

elif page=='Data Management':
    if PUBLIC:
        st.write('Public release assets are read-only. No administrative uploads or database modification are available.')
        if RELEASE: st.dataframe(pd.read_json('public_data/processed/manifest.json'),hide_index=True,width='stretch')
    else:
        category=st.selectbox('Dataset category',list(SCHEMAS))
        spec=SCHEMAS[category]
        template=pd.DataFrame(columns=spec.fields.split()).to_csv(index=False).encode()
        st.download_button('Download blank template',template,category+'.csv','text/csv')
        dictionary=pd.DataFrame([{'field':f,'required':f in spec.required.split(),'format':('nonnegative number (signed coordinates)' if f in spec.numeric.split() else 'YYYY-MM-DD' if f in spec.dates.split() else 'text'),'definition':DESCRIPTIONS.get(f,'Source-provided '+f.replace('_',' '))} for f in spec.fields.split()])
        with st.expander('Field dictionary'): st.dataframe(dictionary,hide_index=True)
        st.download_button('Download field dictionary',dictionary.to_csv(index=False),category+'_dictionary.csv','text/csv')
        st.caption('Imports are all-or-nothing. Errors block import; warnings require acknowledgement. Append adds new IDs; update changes existing IDs; replace synchronizes the selected category and preserves prior raw versions. Referenced providers cannot be removed.')
        upload=st.file_uploader('Upload CSV, XLSX, GeoJSON or GeoPackage',type=['csv','xlsx','geojson','gpkg'])
        if upload is not None:
            try:
                raw=upload.getvalue()
                sheet=0
                layer=None
                if upload.name.lower().endswith('.xlsx'):
                    sheet=st.selectbox('Excel worksheet',pd.ExcelFile(io.BytesIO(raw)).sheet_names)
                if upload.name.lower().endswith('.gpkg'):
                    layer=st.selectbox('GeoPackage layer',geographic_layers(raw))
                frame=read_upload(raw,upload.name,sheet,layer)
                st.write('Preview and detected data types')
                st.dataframe(frame.head(25),hide_index=True)
                st.dataframe(infer_columns(frame),hide_index=True)
                mapping={}
                with st.expander('Map source columns',expanded=True):
                    for field in spec.fields.split():
                        choices=['']+frame.columns.tolist()
                        default=choices.index(field) if field in choices else 0
                        mapping[field]=st.selectbox(field+(' *' if field in spec.required.split() else ''),choices,index=default,key='map_'+category+'_'+field+'_'+upload.name)
                mapped=map_columns(frame,mapping)
                clean,issues=validate(category,mapped,store.read('partners').partner_id,store.read('assessment_criteria'))
                st.subheader('Validation')
                st.dataframe(issues,hide_index=True)
                st.download_button('Download validation report',issues.to_csv(index=False),'validation_report.csv','text/csv')
                source=st.text_input('Import source / internal owner')
                mode=st.selectbox('Import mode',['append','update','replace'])
                warnings=st.checkbox('I reviewed and acknowledge all warnings')
                confirm=st.checkbox('I confirm this import mode and each record’s source and disclosure status')
                if st.button('Confirm transactional import',disabled=not confirm or (issues.severity=='error').any()):
                    try:
                        ident=store.import_data(category,mapped,raw,upload.name,source,mode,warnings)
                        st.success(f'Import {ident} committed. All analyses read the current database on the next navigation or interaction.')
                    except Exception as e: st.error('Import rolled back: '+str(e))
            except Exception as e: st.error('File could not be prepared: '+str(e))
        st.subheader('Import history and original versions')
        history=store.history()
        st.dataframe(history,hide_index=True)
        if not history.empty:
            selected=st.selectbox('Original import',history.import_id.tolist())
            filename,blob=store.raw(selected)
            st.download_button('Download preserved original file',blob,filename)
        st.download_button('Download consistent SQLite backup',store.backup(),'share_network_backup.sqlite','application/octet-stream')

elif page=='Methodology and Data Sources':
    if RELEASE:
        st.dataframe(pd.read_json('public_data/processed/manifest.json'),hide_index=True,width='stretch')
        lookup=st.selectbox('USDA variable definitions',sorted(p.name for p in Path('public_data/processed').glob('*Lookup*.csv')))
        if lookup: st.dataframe(pd.read_csv(Path('public_data/processed')/lookup,encoding='latin1'),hide_index=True,width='stretch')
    st.markdown(Path('docs/methodology.md').read_text())
    st.markdown(Path('docs/public_data_status.md').read_text())
    st.caption('Source-level privacy labels are enforced in public-data view. Public deployment additionally requires a physically separate reviewed database and authentication/hosting review. This application is not publicly deployed.')
