"""Public food directory and county summaries."""
from datetime import time
from urllib.parse import urlencode

import pandas as pd
import streamlit as st


PUBLIC_SECTIONS = ("Find food", "County snapshot", "Research tools")
COUNTIES = ("Philadelphia County", "Montgomery County", "Delaware County")
PAGE_SIZE = 12


def public_navigation():
    st.markdown(
        '<style>[data-testid="stMainBlockContainer"] {padding-top: 4rem;} '
        '[data-testid="stText"] pre {white-space: pre-wrap; overflow-wrap: anywhere;}</style>',
        unsafe_allow_html=True,
    )
    st.title("Regional Food Access")
    st.caption("Philadelphia, Montgomery, and Delaware counties, Pennsylvania")
    st.info('This platform is an exploratory prototype based on publicly available data. Public directories may be incomplete or outdated. Findings should not be interpreted as official Share Food Program assessments.')
    return st.radio("Explore food access", PUBLIC_SECTIONS, horizontal=True,
                    label_visibility="collapsed", key="public_section")


def find_food(store):
    search_col, county_col = st.columns([2, 1])
    query = search_col.text_input("ZIP code, site name, or street address",
                                 placeholder="For example, 19104").strip()
    county = county_col.selectbox("County", ("All counties", *COUNTIES))
    st.info("Call ahead or check the listing before traveling. Hours, eligibility, and food availability can change.")

    sites = store.read("partners")
    sites = sites[sites.active_status.ne("inactive") & sites.partner_type.ne("public benefits")]
    if county != "All counties":
        sites = sites[sites.county.eq(county)]
    if query and not sites.empty:
        if len(query) == 5 and query.isascii() and query.isdigit():
            sites = sites[sites.zip_code.fillna("").str[:5].eq(query)]
        else:
            fields = sites[["site_name", "street_address", "city"]].fillna("")
            match = fields.agg(" ".join, axis=1).str.contains(query, case=False, regex=False)
            sites = sites[match]
    sites = sites.sort_values(["site_name", "partner_id"], key=lambda values: values.str.casefold())
    st.caption(f"{len(sites):,} matching directory {'listing' if len(sites) == 1 else 'listings'}")
    if sites.empty:
        st.info("No listings match. Try another ZIP code, a shorter name, or all counties.")
        return

    pages = range(1, (len(sites) - 1) // PAGE_SIZE + 2)
    page = st.selectbox("Results page", pages, key=f"directory_page:{county}:{query}") if len(pages) > 1 else 1
    offset = (page - 1) * PAGE_SIZE
    schedules = store.read("operating_schedules")
    windows_by_site = dict(tuple(schedules.groupby("partner_id", sort=False)))
    for site in sites.iloc[offset:offset + PAGE_SIZE].itertuples():
        with st.container(border=True):
            st.subheader(site.site_name, anchor=False)
            locality = " ".join(str(value) for value in (site.city, site.state, site.zip_code)
                                if pd.notna(value) and str(value).strip())
            address = ", ".join(str(value) for value in (site.street_address, locality)
                                if pd.notna(value) and str(value).strip())
            if address:
                st.text(address)
            st.caption(f"{site.partner_type.capitalize()} · {site.county}")
            seasonal = str(site.seasonally_closed).strip().lower() == "yes"
            if seasonal:
                st.warning("The source flags this site as seasonally closed. Check before visiting.")
            windows = windows_by_site.get(site.partner_id)
            if windows is not None:
                with st.expander("Published hours · confirm before visiting"):
                    for window in windows.itertuples():
                        opening = time.fromisoformat(window.opening_time).strftime("%-I:%M %p")
                        closing = time.fromisoformat(window.closing_time).strftime("%-I:%M %p")
                        notes = f" · {window.source_notes}" if pd.notna(window.source_notes) else ""
                        st.text(f"{window.operating_day} · {opening}–{closing}{notes}")
            elif isinstance(site.published_schedule, str) and site.published_schedule.strip() and not site.published_schedule.lstrip().startswith("{"):
                st.caption("Published hours · confirm before visiting")
                st.text(site.published_schedule)
            else:
                st.caption("Check the original listing for hours.")
            links = st.columns(2)
            if pd.notna(site.street_address) and str(site.street_address).strip():
                maps_query = urlencode({"api": 1, "destination": address})
                links[0].link_button("Get directions", f"https://www.google.com/maps/dir/?{maps_query}")
            if isinstance(site.website, str) and site.website.startswith(("https://", "http://")):
                links[1].link_button("Site website", site.website)
            elif isinstance(site.source, str) and site.source.startswith(("https://", "http://")):
                links[1].link_button("Original listing", site.source)


def county_snapshot(store):
    st.header("County snapshot")
    county = st.selectbox("Choose a county", COUNTIES)
    facts = store.read("community_indicators")
    facts = facts[facts.county.eq(county) & facts.geographic_resolution.eq("county")]
    rate = facts[facts.indicator_name.eq("Food insecurity rate")]
    people = facts[facts.indicator_name.eq("Food-insecure population")]
    sites = store.read("partners")
    sites = sites[sites.county.eq(county) & sites.active_status.ne("inactive") &
                  sites.partner_type.ne("public benefits")]

    rate_col, people_col, site_col = st.columns(3)
    rate_col.metric("Estimated food insecurity", f"{rate.value.iloc[0]:.1f}%" if len(rate) else "Unavailable")
    people_col.metric("Estimated people affected", f"{people.value.iloc[0]:,.0f}" if len(people) else "Unavailable")
    site_col.metric("Food directory listings", f"{len(sites):,}")
    st.write("Food insecurity estimates describe 2024. Directory totals reflect the sources available for this county and may include multiple listings at one address.")
    if len(rate):
        st.link_button("See Feeding America’s county estimate", rate.source_url.iloc[0])
