import osmnx as ox
import pandas as pd
import geopandas as gpd
import os

# Enable OSMnx's built-in HTTP request cache
ox.settings.use_cache = True
ox.settings.timeout = 3000  # Increase timeout to 50 minutes for massive queries

CACHE_DIR = "cache"

def load_road_network(place_name="Kathriguppe, Bangalore, India", dist=5000):
    """
    Downloads the drivable road network, caching it to disk to prevent massive API loads on restart.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_name = f"{place_name.replace(', ', '_').replace(' ', '_').lower()}_{dist}m"
    graph_path = os.path.join(CACHE_DIR, f"{safe_name}_drive.graphml")
    
    if os.path.exists(graph_path):
        print(f"[OSM Loader] ⚡ Loading road network from local disk cache: {graph_path}")
        G_proj = ox.load_graphml(graph_path)
        print(f"Loaded Graph: {len(G_proj.nodes)} nodes, {len(G_proj.edges)} edges.")
        return G_proj

    print(f"[OSM Loader] 🌐 Downloading 10x10km road network around {place_name} from Overpass API...")
    G = ox.graph_from_address(place_name, dist=dist, network_type='drive')
    
    # Project graph to UTM local CRS
    G_proj = ox.project_graph(G)
    
    print(f"[OSM Loader] 💾 Saving road network to local disk cache...")
    ox.save_graphml(G_proj, graph_path)
    print(f"Loaded Graph: {len(G_proj.nodes)} nodes, {len(G_proj.edges)} edges.")
    
    return G_proj

def load_buildings(place_name="Kathriguppe, Bangalore, India", dist=5000):
    """
    Downloads building footprints for the specified radius.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe_name = f"{place_name.replace(', ', '_').replace(' ', '_').lower()}_{dist}m"
    buildings_path = os.path.join(CACHE_DIR, f"{safe_name}_buildings.geojson")
    
    if os.path.exists(buildings_path):
        print(f"[OSM Loader] ⚡ Loading building footprints from local disk cache: {buildings_path}")
        buildings_proj = gpd.read_file(buildings_path)
        print(f"Loaded {len(buildings_proj)} building footprints.")
        return buildings_proj

    print(f"[OSM Loader] 🌐 Downloading 10x10km building footprints around {place_name} from Overpass API...")
    tags = {'building': True}
    buildings = ox.features_from_address(place_name, tags=tags, dist=dist)
    
    # Project to UTM CRS
    buildings_proj = buildings.to_crs(buildings.estimate_utm_crs())
    
    print(f"[OSM Loader] 💾 Saving building footprints to local disk cache (GeoJSON)...")
    buildings_proj.to_file(buildings_path, driver="GeoJSON")
    print(f"Loaded {len(buildings_proj)} building footprints.")
    
    return buildings_proj