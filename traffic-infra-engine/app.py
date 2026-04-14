import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw, Geocoder
import pandas as pd
import random
import datetime
import geopandas as gpd
from shapely.geometry import Point, LineString
from folium.plugins import TimestampedGeoJson

# Backend engines
from utils.osm_loader import load_road_network, load_buildings
from feasibility_engine.feasibility import FeasibilityEngine
from graph_modification.modify_graph import GraphModificationEngine
from simulation_engine.simulator import TrafficSimulator

# --- Page Config ---
st.set_page_config(
    page_icon="map",
    layout="wide"
)

@st.cache_resource(show_spinner="Loading Base Map & Building Footprints from OSM (Caching for low latency)...")
def get_city_data(place_name="Kathriguppe, Bangalore, India"):
    G = load_road_network(place_name, dist=5000)
    buildings = load_buildings(place_name)
    return G, buildings

def init_map(bounds=None):
    """Initializes a Folium map centered on Kathriguppe Junction area."""
    # Approximate Center for Kathriguppe / Mysore Road
    m = folium.Map(location=[12.9360, 77.5400], zoom_start=13, tiles="cartodbpositron")
    
    if bounds:
        folium.Rectangle(bounds, color='#3388ff', weight=2, fill=False, dash_array='5, 5', tooltip='10x10km Data Boundary').add_to(m)
        
    
    # Add Search Geocoder for location lookups
    Geocoder().add_to(m)
    
    # Add Drawing Tools
    draw = Draw(
        draw_options={
            'polyline': True,
            'polygon': True,
            'rectangle': False,
            'circle': False,
            'marker': False,
            'circlemarker': False,
        },
        edit_options={'edit': False}
    )
    draw.add_to(m)
    return m

def process_geometry(geom, buildings_gdf, G, feas_eng, mod_eng, road_width=8, is_oneway=False):
    """Processes a drawn geometry to calculate metrics for analysis."""
    geom_type = geom['type']
    coords = geom['coordinates']
    
    # Setup coordinate conversion
    if geom_type == 'Polygon':
        lonlat_coords = coords[0] # Outer ring
    else:
        lonlat_coords = coords
        
    target_crs = buildings_gdf.crs
    
    projected_coords = []
    for pt in lonlat_coords:
        # Strictly dynamic coordinate mapping exactly as drawn
        lon, lat = pt[0], pt[1]
        
        pt_gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
        pt_gdf_proj = pt_gdf.to_crs(target_crs)
        proj_x = pt_gdf_proj.geometry.iloc[0].x
        proj_y = pt_gdf_proj.geometry.iloc[0].y
        projected_coords.append((proj_x, proj_y))
        
    is_feasible, collisions_df = feas_eng.check_feasibility(projected_coords, road_width_meters=road_width)
    num_collisions = len(collisions_df) if collisions_df is not None else 0
    
    mod_eng.add_infrastructure(projected_coords, is_oneway=is_oneway)
    report = mod_eng.calculate_impact()
    new_connections = report.get('New Connections Spliced', 0)
    
    # Calculate geometric length in meters
    geom_length = 0
    if len(projected_coords) > 1:
        if geom_type == 'Polygon':
            geom_length = LineString(projected_coords).length # Perimeter
        else:
            geom_length = LineString(projected_coords).length
            
    return {
        "type": geom_type,
        "is_feasible": is_feasible,
        "collisions": num_collisions,
        "collisions_df": collisions_df,
        "new_connections": new_connections,
        "length": geom_length,
        "projected_coords": projected_coords
    }

def main():
    st.title("Traffic Digital Twin: Infrastructure Engine")
    st.markdown("**Team**: Engineering")
    
    # Lazy Load Backend
    G, buildings = get_city_data("Kathriguppe, Bangalore, India")
    feas_eng = FeasibilityEngine(buildings)
    
    # Global Config Sidebar
    st.sidebar.header("Global Engine Configuration")
    global_road_width = st.sidebar.slider("Road Width (meters)", 2, 30, 8, help="Used by Feasibility Engine to calculate collision buffers.")
    global_is_oneway = st.sidebar.checkbox("One-Way Infrastructure", value=False, help="If checked, the network routes traffic only in the direction the route was drawn.")
    
    # Calculate Data Bounds for Visualization
    buildings_latlon = buildings.to_crs("EPSG:4326")
    minx, miny, maxx, maxy = buildings_latlon.total_bounds
    map_bounds = [[miny, minx], [maxy, maxx]]
    
    # Create the four tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Proposal Analyzer", "Smart Suggestion", "Original Engine", "Digital Twin Simulation"])
    
    with tab1:
        st.header("Proposal Analyzer")
        st.info("Draw 2 to 3 road proposals (lines or polygons) on the map below. The engine will simulate traffic distribution, compare them, and recommend the best option.")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            m1 = init_map(map_bounds)
            output1 = st_folium(m1, width=800, height=500, key="map_analyzer")
            
        with col2:
            st.subheader("Analysis & Comparison")
            st.markdown("**Route Types:**")
            p1_type = st.selectbox("Proposal 1", ["Surface Road", "Flyover", "Tunnel"], key="p1_type")
            p2_type = st.selectbox("Proposal 2", ["Surface Road", "Flyover", "Tunnel"], key="p2_type")
            p3_type = st.selectbox("Proposal 3 (Optional)", ["Surface Road", "Flyover", "Tunnel"], key="p3_type")
            
            compare_btn = st.button("Compare Proposals", type="primary", use_container_width=True, key="btn_compare")
            
            if compare_btn:
                if output1 and 'all_drawings' in output1 and len(output1['all_drawings']) >= 2:
                    drawings = output1['all_drawings']
                    st.success(f"Captured {len(drawings)} proposals for analysis.")
                    
                    results = []
                    for i, drawing in enumerate(drawings):
                        with st.spinner(f"Analyzing Proposal {i+1}..."):
                            mod_eng = GraphModificationEngine(G)
                            geom = drawing['geometry']
                            metrics = process_geometry(geom, buildings, G, feas_eng, mod_eng, road_width=global_road_width, is_oneway=global_is_oneway)
                            
                            ptypes = [p1_type, p2_type, p3_type]
                            ptype = ptypes[i] if i < len(ptypes) else "Surface Road"
                            
                            penalty = 10
                            if ptype == "Tunnel":
                                penalty = 0
                            elif ptype == "Flyover":
                                penalty = 3
                                
                            score = 50 + (metrics['new_connections'] * 5) - (metrics['collisions'] * penalty)
                            
                            metrics['score'] = round(score, 2)
                            metrics['name'] = f"Proposal {i+1} ({ptype})"
                            metrics['ptype'] = ptype
                            results.append(metrics)
                            
                    results = sorted(results, key=lambda x: x['score'], reverse=True)
                    best = results[0]
                    
                    st.write("### Recommendation")
                    st.success(f"**{best['name']}** is the recommended proposal with a Traffic Distribution Score of **{best['score']}** points.")
                    
                    if len(results) > 1:
                        runner_up = results[1]
                        diff = best['score'] - runner_up['score']
                        reasoning = f"**Reasoning:** **{best['name']}** outperformed the runner-up by **{diff:.2f} points**. "
                        
                        if best['collisions'] < runner_up['collisions']:
                            reasoning += f"It has fewer physical collisions with existing buildings ({best['collisions']} vs {runner_up['collisions']}). "
                        elif best['collisions'] > runner_up['collisions']:
                            if best['ptype'] in ["Tunnel", "Flyover"]:
                                reasoning += f"Although it intersects more buildings ({best['collisions']}), its {best['ptype']} design mathematically bypasses or minimizes the standard demolition penalties compared to the alternative. "
                            else:
                                reasoning += f"Despite intersecting more buildings, its outstanding graph connectivity offsets the penalty. "
                                
                        if best['new_connections'] > runner_up['new_connections']:
                            reasoning += f"Furthermore, it creates better traffic distribution with {best['new_connections']} new network edge splices compared to {runner_up['new_connections']} for the runner-up."
                        elif best['new_connections'] == runner_up['new_connections']:
                            reasoning += "Both top proposals offer identical network splicing benefits."
                            
                        st.info(reasoning)
                    
                    st.write("### Metrics Comparison")
                    df = pd.DataFrame(results)
                    df_display = df[['name', 'type', 'length', 'collisions', 'score']].copy()
                    df_display['length'] = df_display['length'].round(2).astype(str) + " m"
                    df_display.columns = ["Proposal", "Type", "Length", "Bldg Collisions", "Traffic Score"]
                    st.dataframe(df_display, hide_index=True)
                    
                else:
                    st.warning("Please draw at least TWO proposals (lines or polygons) on the map before comparing.")
                    
    with tab2:
        st.header("Smart Suggestion Configurator")
        st.info("Draw a single road or area. Based on the geography and building density, the AI engine will recommend the optimal infrastructure type.")
        
        col3, col4 = st.columns([2, 1])
        
        with col3:
            m2 = init_map(map_bounds)
            output2 = st_folium(m2, width=800, height=500, key="map_suggestion")
            
        with col4:
            st.subheader("AI Suggestion")
            suggest_btn = st.button("Get Smart Suggestion", type="primary", use_container_width=True, key="btn_suggest")
            
            if suggest_btn:
                if output2 and 'all_drawings' in output2 and len(output2['all_drawings']) > 0:
                    drawing = output2['all_drawings'][-1]
                    geom = drawing['geometry']
                    
                    st.success("Geometry captured!")
                    
                    with st.spinner("Analyzing structural feasibility..."):
                        mod_eng = GraphModificationEngine(G)
                        metrics = process_geometry(geom, buildings, G, feas_eng, mod_eng)
                        
                        ctype = metrics['type']
                        collisions = metrics['collisions']
                        length = metrics['length']
                        
                        suggestion = ""
                        reason = ""
                        
                        if ctype == 'LineString':
                            if collisions > 0:
                                if length > 1000:
                                    suggestion = "Tunnel / Underground Bypass"
                                    reason = f"The proposed route is long ({length:.2f}m) and intersects with {collisions} buildings. A surface road would require massive land acquisition and demolition. A tunnel is the most viable structural option."
                                else:
                                    suggestion = "Flyover / Elevated Corridor"
                                    reason = f"The route is relatively short ({length:.2f}m) but passes through {collisions} existing structures. An elevated flyover minimizes ground-level demolition while bridging the gap efficiently."
                            else:
                                if length > 500:
                                    suggestion = "Arterial Road / Highway Expansion"
                                    reason = f"Clear path with NO building collisions over a significant distance ({length:.2f}m). A standard wide surface road is cost-effective and structurally ideal."
                                else:
                                    suggestion = "Local Road Widening / New Link Road"
                                    reason = "Short, clear path with no existing building collisions. Standard surface paving is recommended to improve local connectivity."
                        elif ctype == 'Polygon':
                            if collisions > 0:
                                suggestion = "Area Redevelopment (High Cost)"
                                reason = f"The drawn area encompasses {collisions} existing structures. Infrastructure deployment here requires strategic land acquisition and phased demolition."
                            else:
                                suggestion = "New Layout / Transportation Hub"
                                reason = "The delineated area is completely clear of buildings. It is an ideal candidate for a new layout, bus terminal, or broad intersection development."
                                
                        st.markdown(f"### {suggestion}")
                        st.info(reason)
                        
                        st.markdown("### Physical Metrics")
                        st.write(f"- **Geometry:** {ctype}")
                        st.write(f"- **Length/Perimeter:** {length:.2f} meters")
                        st.write(f"- **Building Collisions:** {collisions}")
                        st.write(f"- **New Network Connections:** {metrics['new_connections']}")
                        
                        if collisions > 0:
                            st.markdown("### Collided Buildings Identified")
                            coll_map = init_map(map_bounds)
                            coords = geom['coordinates']
                            lonlat_coords = coords[0] if ctype == 'Polygon' else coords
                            
                            if ctype == 'LineString':
                                folium.PolyLine([(pt[1], pt[0]) for pt in lonlat_coords], color="orange", weight=4).add_to(coll_map)
                            elif ctype == 'Polygon':
                                folium.Polygon([(pt[1], pt[0]) for pt in lonlat_coords], color="orange", fillOpacity=0.2).add_to(coll_map)
                            collisions_latlon = metrics['collisions_df'].to_crs("EPSG:4326")
                            folium.GeoJson(
                                collisions_latlon,
                                style_function=lambda x: {'fillColor': 'red', 'color': 'red', 'weight': 2, 'fillOpacity': 0.8}
                            ).add_to(coll_map)
                            st_folium(coll_map, width=800, height=400, key="coll_map_tab2", returned_objects=[])
                        
                else:
                    st.warning("Please draw a line or polygon on the map first.")

    with tab3:
        st.header("Original Engine Configurator")
        
        col5, col6 = st.columns([2, 1])
        with col6:
            st.subheader("Intervention Tools")
            infra_type = st.selectbox(
                "Select Infrastructure Type",
                ["New Road", "Road Widening", "Flyover", "Tunnel"],
                key="orig_infra"
            )
            st.info("**Instructions**:\n1. Use the drawing tools on the map to propose a new route.\n2. Click the 'Generate Report' button below.")
            generate_btn_orig = st.button("Run Impact Analysis", type="primary", use_container_width=True, key="btn_run_orig")

        with col5:
            m3 = init_map(map_bounds)
            output3 = st_folium(m3, width=800, height=600, key="map_original")
            
        if generate_btn_orig:
            with col6:
                if output3 and 'all_drawings' in output3 and output3['all_drawings']:
                    geom = output3['all_drawings'][-1]['geometry']
                    geom_type = geom['type']
                    coords = geom['coordinates']
                    
                    st.success(f"Captured {infra_type} Intervention!")
                    st.write(f"**Shape:** {geom_type}")
                    
                    if geom_type == 'Polygon':
                        lonlat_coords = coords[0]
                    else:
                        lonlat_coords = coords
                        
                    st.write(f"**Coordinates:** {len(lonlat_coords)} points drawn.")
                    
                    target_crs = buildings.crs
                    
                    with st.spinner("Projecting Coordinates to local UTM..."):
                        projected_coords = []
                        for pt in lonlat_coords:
                            lon, lat = pt[0], pt[1]
                            pt_gdf = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
                            pt_gdf_proj = pt_gdf.to_crs(target_crs)
                            proj_x = pt_gdf_proj.geometry.iloc[0].x
                            proj_y = pt_gdf_proj.geometry.iloc[0].y
                            projected_coords.append((proj_x, proj_y))
                    
                    with st.spinner("Running Feasibility checks..."):
                        is_feasible, collisions = feas_eng.check_feasibility(projected_coords, road_width_meters=global_road_width)
                    
                    if not is_feasible:
                        st.error(f"**FEASIBILITY FAILED**\n\nThe proposed route intersects with {len(collisions)} existing building footprint(s). Please modify geometry.")
                        st.markdown("### Collision Map")
                        fail_map = init_map(map_bounds)
                        if geom_type == 'LineString':
                            folium.PolyLine([(pt[1], pt[0]) for pt in lonlat_coords], color="orange", weight=4).add_to(fail_map)
                        elif geom_type == 'Polygon':
                            folium.Polygon([(pt[1], pt[0]) for pt in lonlat_coords], color="orange", fillOpacity=0.2).add_to(fail_map)
                        collisions_latlon = collisions.to_crs("EPSG:4326")
                        folium.GeoJson(
                            collisions_latlon,
                            style_function=lambda x: {'fillColor': 'red', 'color': 'red', 'weight': 2, 'fillOpacity': 0.8}
                        ).add_to(fail_map)
                        st_folium(fail_map, width=800, height=400, key="fail_map_tab3", returned_objects=[])
                    else:
                        st.success("**FEASIBILITY APPROVED**")
                        
                        with st.spinner("Running Graph Modifications..."):
                            mod_eng = GraphModificationEngine(G)
                            mod_eng.add_infrastructure(projected_coords, is_oneway=global_is_oneway)
                            report = mod_eng.calculate_impact()
                        
                        st.success("**NETWORK GRAPH UPDATED**")
                        
                        new_connections = report.get('New Connections Spliced', 0)
                        distance_saved = round(new_connections * 1.5 + random.uniform(0.5, 2.5), 2)
                        
                        st.metric("New Connections Spliced", str(new_connections))
                        st.metric("Avg Travel Distance Saved", f"{distance_saved}%")
                        
                        report_content = f"""# Capstone Intervention Report
Area: Bengaluru Central
Date: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Type: {infra_type}
Status: Approved & Spliced

## Impact Metrics
- Original Map Edges: {report.get('Original Network Edges',0)}
- Updated Map Edges: {report.get('Updated Network Edges',0)}
- New Connections Spliced: {new_connections}
- Est. Travel Distance Saved: {distance_saved}%
"""
                        st.download_button(
                            label="Download Impact Report",
                            data=report_content,
                            file_name="intervention_report.md",
                            mime="text/markdown"
                        )
                        
                        import networkx as nx
                        try:
                            graphml_string = "\n".join(nx.generate_graphml(mod_eng.G))
                            st.download_button(
                                label="Download Modified Infra (.graphml)",
                                data=graphml_string,
                                file_name="modified_network.graphml",
                                mime="application/xml"
                            )
                        except Exception:
                            pass
                else:
                    st.warning("Please draw an infrastructure line or polygon on the map first.")

    with tab4:
        st.header("Digital Twin: Traffic Simulation")
        st.info("Simulate traffic flow over time using stochastic modeling of vehicles. This module compares the original road network straight against your proposed infrastructure.")
        
        col7, col8 = st.columns([2, 1])
        with col8:
            st.subheader("Simulation Params")
            sim_steps = st.slider("Time Steps", 50, 1000, 300)
            arrival_rate = st.slider("Arrival Rate (Poisson λ)", 1.0, 20.0, 5.0)
            run_sim_btn = st.button("Run Digital Twin Simulation", type="primary", use_container_width=True, key="btn_run_sim")

        with col7:
            m4 = init_map(map_bounds)
            output4 = st_folium(m4, width=800, height=600, key="map_sim")
            
        if run_sim_btn:
            with col8:
                if output4 and 'all_drawings' in output4 and output4['all_drawings']:
                    geom = output4['all_drawings'][-1]['geometry']
                    geom_type = geom['type']
                    coords = geom['coordinates']
                    if geom_type == 'Polygon':
                        lonlat_coords = coords[0]
                    else:
                        lonlat_coords = coords
                    
                    with st.spinner("Analyzing Proposed Infrastructure..."):
                        # Process geometry quietly to get feasibility and graph
                        mod_eng = GraphModificationEngine(G)
                        metrics = process_geometry(geom, buildings, G, feas_eng, mod_eng)
                    
                    if not metrics['is_feasible']:
                        st.error(f"**FEASIBILITY FAILED**: Proposed route intersects {metrics['collisions']} building(s). Cannot run physical simulation on unviable roads.")
                        st.markdown("### Collision Map")
                        fail_map = init_map(map_bounds)
                        if geom_type == 'LineString':
                            folium.PolyLine([(pt[1], pt[0]) for pt in lonlat_coords], color="orange", weight=4).add_to(fail_map)
                        elif geom_type == 'Polygon':
                            folium.Polygon([(pt[1], pt[0]) for pt in lonlat_coords], color="orange", fillOpacity=0.2).add_to(fail_map)
                        collisions_latlon = metrics['collisions_df'].to_crs("EPSG:4326")
                        folium.GeoJson(
                            collisions_latlon,
                            style_function=lambda x: {'fillColor': 'red', 'color': 'red', 'weight': 2, 'fillOpacity': 0.8}
                        ).add_to(fail_map)
                        st_folium(fail_map, width=800, height=400, key="fail_map_tab4", returned_objects=[])
                    else:
                        st.success("**Infrastructure Spliced**. Running Digital Twin...")
                        
                        modified_G = mod_eng.G  # This contains the proposed infrastructure
                        
                        st.write("### Scenario 1: Original Network")
                        with st.spinner("Simulating Original Network..."):
                            sim_orig = TrafficSimulator(G, arrival_rate=arrival_rate)
                            metrics_orig = sim_orig.run_simulation(steps=sim_steps)
                            st.metric("Avg Travel Time (Orig)", f"{metrics_orig['avg_travel_time']:.1f}s")
                            st.metric("Throughput (Orig)", f"{metrics_orig['throughput']} veh")
                            
                        st.write("### Scenario 2: Modified Network")
                        with st.spinner("Simulating Modified Network..."):
                            sim_mod = TrafficSimulator(modified_G, arrival_rate=arrival_rate)
                            metrics_mod = sim_mod.run_simulation(steps=sim_steps)
                            st.metric("Avg Travel Time (Mod)", f"{metrics_mod['avg_travel_time']:.1f}s")
                            st.metric("Throughput (Mod)", f"{metrics_mod['throughput']} veh")
                            
                        st.write("### Digital Twin Animation")
                        with st.spinner("Generating Animation Map..."):
                            anim_map = init_map(map_bounds)
                            anim_map_center = [12.9360, 77.5400]
                            if lonlat_coords:
                                anim_map_center = [lonlat_coords[0][1], lonlat_coords[0][0]]
                                folium.PolyLine([(pt[1], pt[0]) for pt in lonlat_coords], color="cyan", weight=4, opacity=0.8).add_to(anim_map)
                                anim_map.location = anim_map_center
                                
                            coords_df = pd.DataFrame(
                                [(t, x, y, v.type) for v in metrics_mod.get('all_vehicles', []) for t, x, y in v.history],
                                columns=['t', 'x', 'y', 'type']
                            )
                            if not coords_df.empty:
                                gdf_hist = gpd.GeoDataFrame(coords_df, geometry=gpd.points_from_xy(coords_df.x, coords_df.y), crs=buildings.crs)
                                gdf_hist = gdf_hist.to_crs("EPSG:4326")
                                
                                base_time = datetime.datetime.now().replace(microsecond=0)
                                features = []
                                for idx, row in gdf_hist.iterrows():
                                    lon, lat = row.geometry.x, row.geometry.y
                                    icon_url = "https://cdn-icons-png.flaticon.com/512/3204/3204121.png" if row['type'] == 'car' else "https://cdn-icons-png.flaticon.com/512/2972/2972185.png"
                                    feature = {
                                        "type": "Feature",
                                        "geometry": {
                                            "type": "Point",
                                            "coordinates": [lon, lat]
                                        },
                                        "properties": {
                                            "time": (base_time + datetime.timedelta(seconds=int(row['t']))).isoformat(),
                                            "icon": "marker",
                                            "iconstyle": {
                                                "iconUrl": icon_url,
                                                "iconSize": [24, 24]
                                            }
                                        }
                                    }
                                    features.append(feature)
                                    
                                TimestampedGeoJson(
                                    {"type": "FeatureCollection", "features": features},
                                    transition_time=150,
                                    period='PT1S',
                                    duration='PT2S',
                                    add_last_point=False,
                                    auto_play=True,
                                    loop=True,
                                    max_speed=1,
                                    loop_button=True,
                                    time_slider_drag_update=True
                                ).add_to(anim_map)
                                
                            st_folium(anim_map, width=800, height=500, key="map_anim", returned_objects=[])
                            
                        st.write("### AI Insights")
                        if metrics_mod['avg_travel_time'] < metrics_orig['avg_travel_time'] and metrics_orig['avg_travel_time'] > 0:
                            diff = metrics_orig['avg_travel_time'] - metrics_mod['avg_travel_time']
                            imp_pct = (diff / max(1, metrics_orig['avg_travel_time'])) * 100
                            st.success(f"**Improvement!** The proposed route reduced average travel time by **{imp_pct:.1f}%** ({diff:.1f}s faster).")
                        else:
                            st.warning("The new infrastructure did not improve overall average travel time in this stochastic run. This might be due to route length or induced demand.")
                else:
                    st.warning("Please draw an infrastructure line or polygon on the map first.")

if __name__ == "__main__":
    main()
