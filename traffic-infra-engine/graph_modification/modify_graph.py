import networkx as nx
import osmnx as ox
from shapely.geometry import Point

class GraphModificationEngine:
    """
    Responsibilities: Modify the mathematical road graph, splice new edges, calculate network metrics.
    """
    def __init__(self, graph):
        # Work on a copy of the graph to easily compare impact later without corrupting original
        self.original_G = graph
        self.G = graph.copy()

    def add_infrastructure(self, proposed_coords, is_oneway=False):
        """
        Modifies the road network graph by adding the proposed infrastructure using Waypoint Snapping.
        Connects each intermediate point drawn to the closest existing nodes in the network sequentially.
        """
        print("\n[Graph Mod Engine] Modifying Network Graph with Waypoint Snapping...")
        
        total_added_length = 0
        spliced_segments = 0
        
        prev_node = None
        prev_coord = None
        
        for coord in proposed_coords:
            # 1. Find the nearest existing node in the graph to the current drawn coordinate
            current_node = ox.distance.nearest_nodes(self.G, X=coord[0], Y=coord[1])
            
            # 2. If we have a previous node and it's different from the current node, connect them
            if prev_node is not None and current_node != prev_node:
                # Calculate geographic distance of this segment length in meters
                segment_length = Point(prev_coord).distance(Point(coord))
                
                # 3. Add the new edge (bi-directional unless specified as one-way)
                self.G.add_edge(prev_node, current_node, length=segment_length, name="Proposed Infra", highway="proposed_road")
                if not is_oneway:
                    self.G.add_edge(current_node, prev_node, length=segment_length, name="Proposed Infra", highway="proposed_road")
                
                total_added_length += segment_length
                spliced_segments += 1
                
            prev_node = current_node
            prev_coord = coord
            
        print(f"GRAPH UPDATED: Spliced {spliced_segments} consecutive segments via Waypoint Snapping.")
        print(f"   ↳ Total added road length: {total_added_length:.2f} meters")
        
        return self.G

    def calculate_impact(self):
        """
        Calculates the impact of the new infrastructure on the network.
        """
        print("\n[Graph Mod Engine] Calculating Impact Metrics...")
        
        orig_nodes, orig_edges = len(self.original_G.nodes), len(self.original_G.edges)
        new_nodes, new_edges = len(self.G.nodes), len(self.G.edges)
        
        # Basic topological metrics
        report = {
            "Original Network Edges": orig_edges,
            "Updated Network Edges": new_edges,
            "New Connections Spliced": new_edges - orig_edges,
        }
        
        return report