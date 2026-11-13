"""Philadelphia-only historical context; never joins strata into regional scores."""
import pandas as pd
import plotly.express as px
import streamlit as st
from .supplemental import PRIORITY,LABELS
from .visualization import landscape_map

def health_context(store,counties,key,compact=False):
    st.subheader('Philadelphia context · Health of the City')
    st.caption('Historical Philadelphia-only observations. Separate from ACS 2024 regional indicators; no tract estimates or geographic crosswalk is applied.')
    if counties and 'Philadelphia County' not in counties:
        st.info('This dataset does not cover the selected county. No Philadelphia value is substituted for another county.')
        return
    health=store.read('health_of_city')
    if health.empty:
        st.info('Health of the City public asset has not been loaded.');return
    st.markdown('[Public dataset and original sources](https://opendataphilly.org/datasets/health-of-the-city/) · [Publisher technical notes](https://philadelphiapublichealth.shinyapps.io/health-of-the-city/#technical-notes)')
    st.caption('Poverty and unemployment are source-defined percentages. Renter burden is the publisher’s measure, not all-household housing burden. Population counts and population-composition percentages remain distinct. Missing/suppressed/unreliable observations are never zero.')
    catalog=store.read('health_metric_catalog')
    if not compact:
        with st.expander('Review all 47 indicators, periods, source coverage and missing values'):
            st.dataframe(catalog,hide_index=True,width='stretch')
            st.download_button('Download 47-indicator catalog',catalog.to_csv(index=False),'health_metric_catalog.csv','text/csv',key=key+'_catalog')
    all_metrics=st.checkbox('Explore all 47 health indicators',key=key+'_all') if not compact else False
    options=PRIORITY+[m for m in sorted(health.metric_name.unique()) if m not in PRIORITY] if all_metrics else PRIORITY
    metric=st.selectbox('Philadelphia context measure',options,format_func=lambda m:LABELS.get(m,m.replace('_',' ')),key=key+'_metric')
    selected=health[health.metric_name==metric].copy()
    for field,label,default in [('geography','Source geography','County'),('year','Original reporting period',None),('sex','Sex','All sexes'),('race_ethnicity','Race / ethnicity','All races/ethnicities'),('age_category','Age category','All ages')]:
        values=sorted(selected[field].unique().tolist())
        index=values.index(default) if default in values else len(values)-1 if field=='year' else 0
        choice=st.selectbox(label,values,index=index,key=key+'_'+field)
        selected=selected[selected[field]==choice]
    # Resolve outcome-specific strata instead of pooling them in charts.
    for field in ['source','candida_auris_case_type','blood_lead_level','fatal_nonfatal_shootings','leading_cause_death','leading_cause_death_rank','drug_category','aqi_category','syphilis_transmission_category','smoke_type']:
        if selected[field].nunique()>1:
            choice=st.selectbox(field.replace('_',' ').capitalize(),sorted(selected[field].unique()),key=key+'_'+field)
            selected=selected[selected[field]==choice]
    st.caption(f'{len(selected)} source observations · {selected.metric_value.isna().sum()} missing after sentinel/quality handling. Bounds retain their source uncertainty type. No aggregation or cross-period pooling.')
    if not selected.empty and not selected.geographic_id.duplicated().any():
        if selected.geographic_resolution.iloc[0]=='county':
            units=store.read('geographic_units');units=units[(units.geographic_resolution=='county') & (units.geographic_id=='42101')]
            mapped=selected.rename(columns={'metric_value':'display_value'})
            st.plotly_chart(landscape_map(store.read('partners').iloc[:0],units,mapped),width='stretch',key=key+'_map')
        else:
            st.info('Matching-vintage ZCTA / planning-district polygons are not integrated. These observations are compared as source geographies, never placed on tract or postal ZIP maps.')
        fig=px.bar(selected.sort_values('geography_name'),x='geography_name',y='metric_value',labels={'geography_name':'Source geographic area','metric_value':selected.unit.iloc[0]},title=LABELS.get(metric,metric.replace('_',' ')),hover_data=['year','source','quality_flag','lower_bound','upper_bound','uncertainty_type'])
        st.plotly_chart(fig,width='stretch',key=key+'_chart')
    elif not selected.empty:st.warning('More than one observation remains per area; inspect the source strata below. No pooled comparison is calculated.')
    columns=['year','geography_name','geography','sex','race_ethnicity','age_category','metric_name','metric_value','unit','lower_bound','upper_bound','uncertainty_type','source','quality_flag','missing_reason','dataset_source_url']
    st.dataframe(selected[columns],hide_index=True,width='stretch')
    st.download_button('Download selected Philadelphia context',selected.to_csv(index=False),'philadelphia_health_context.csv','text/csv',key=key+'_download')
