"""Offline-friendly Plotly geographic views, without remote map tiles."""
import json
import plotly.graph_objects as go
import plotly.express as px

def landscape_map(partners, units=None, indicators=None):
    """Projected polygon map without tile servers, CDN geography, or internet."""
    import numpy as np
    from pyproj import Transformer
    from shapely.geometry import shape
    from plotly.colors import sample_colorscale
    transform=Transformer.from_crs(4326,3857,always_xy=True)
    fig=go.Figure()
    values={}
    low=high=None
    if indicators is not None and not indicators.empty:
        values={(r.geographic_id,r.geographic_resolution):r.display_value for _,r in indicators.iterrows()}
        vals=[v for v in values.values() if pd_notna(v)]
        if vals: low,high=min(vals),max(vals)
    if units is not None:
        for _,r in units.iterrows():
            geometry=shape(json.loads(r.geometry_json))
            val=values.get((r.geographic_id,r.geographic_resolution))
            color='#dce1e6' if not pd_notna(val) else sample_colorscale('Teal',[(val-low)/(high-low) if high>low else 0.5])[0]
            polys=[geometry] if geometry.geom_type=='Polygon' else geometry.geoms
            for poly in polys:
                # Boundary holes use a separate ring; even-odd SVG fill preserves interior holes.
                xs=[];ys=[]
                for ring in [poly.exterior]+list(poly.interiors):
                    x,y=transform.transform(*zip(*ring.coords));xs.extend(list(x)+[None]);ys.extend(list(y)+[None])
                text=str(r['name'])+' · '+('No indicator data' if not pd_notna(val) else str(round(float(val),3)))
                fig.add_trace(go.Scatter(x=xs,y=ys,mode='lines',fill='toself',fillcolor=color,line=dict(color='white',width=1),name=str(r['name']),text=text,hoveron='fills',hovertemplate='%{text}<extra></extra>',showlegend=False))
        if low is not None:
            fig.add_trace(go.Scatter(x=[None,None],y=[None,None],mode='markers',marker=dict(color=[low,high],colorscale='Teal',cmin=low,cmax=high if high>low else low+1,showscale=True,colorbar=dict(title=str(indicators.unit.iloc[0]))),showlegend=False,hoverinfo='skip'))
    colors={'share':'#20806a','external':'#466ea2','unknown':'#8a8295'}
    for group,color in colors.items():
        sites=partners[partners.network_membership==group].dropna(subset=['latitude','longitude'])
        if not sites.empty:
            x,y=transform.transform(sites.longitude.to_numpy(float),sites.latitude.to_numpy(float))
            fig.add_trace(go.Scatter(x=x,y=y,text=sites.site_name,customdata=sites[['active_status','source','last_verified']].fillna('unknown'),mode='markers',marker=dict(size=9,color=color,line=dict(width=1,color='white')),name=group.title(),hovertemplate='%{text}<br>Status: %{customdata[0]}<br>Source: %{customdata[1]}<br>Verified: %{customdata[2]}<extra></extra>'))
    fig.update_layout(height=520,margin=dict(l=0,r=0,t=10,b=0),legend=dict(orientation='h'),paper_bgcolor='#f6f7f9',plot_bgcolor='#eef1f4',xaxis=dict(visible=False),yaxis=dict(visible=False,scaleanchor='x',scaleratio=1),dragmode='pan')
    return fig

def pd_notna(value):
    import pandas as pd
    return value is not None and pd.notna(value)

def weekly_chart(hours, partners):
    from .analytics import DAYS
    joined=hours.merge(partners[['partner_id','site_name']],on='partner_id')
    joined['site_label']=joined.site_name+' ['+joined.partner_id+']'
    pivot=joined.pivot_table(index='site_label',columns='operating_day',values='scheduled_hours',aggfunc='sum').reindex(columns=DAYS)
    # NaN stays missing: absent schedule is not known zero availability.
    return px.imshow(pivot,color_continuous_scale='Teal',labels={'color':'Scheduled hours'},aspect='auto',title='Published weekly windows · missing cells mean no supplied window')

def transit_map(partners, units, stops, shapes):
    from pyproj import Transformer
    transform=Transformer.from_crs(4326,3857,always_xy=True)
    fig=landscape_map(partners,units)
    if not shapes.empty:
        for (mode,route),group in shapes.groupby(['mode','route_id']):
            group=group.sort_values('shape_pt_sequence')
            x,y=transform.transform(group.shape_pt_lon.to_numpy(float),group.shape_pt_lat.to_numpy(float))
            fig.add_trace(go.Scatter(x=x,y=y,mode='lines',line=dict(width=1,color='#8394a8'),opacity=.65,name=mode+' '+route,showlegend=False,hovertemplate='SEPTA '+mode+' route '+route+'<extra></extra>'))
    if not stops.empty:
        x,y=transform.transform(stops.stop_lon.to_numpy(float),stops.stop_lat.to_numpy(float))
        fig.add_trace(go.Scatter(x=x,y=y,mode='markers',text=stops.stop_name,marker=dict(size=4,color='#c9913c'),name='SEPTA stops',hovertemplate='%{text}<extra></extra>'))
    return fig
