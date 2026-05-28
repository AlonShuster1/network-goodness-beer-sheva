# app.py
# Solara entry-point.  Run with:  solara run app.py

import solara
import geopandas as gpd
from ipyleaflet import Map, Marker, MeasureControl, Polygon, Polyline
from ipywidgets import Button, HBox, HTML, VBox

from data import hood_border, hood_population, area_for_each_neighberhood_beer_sheva
from network_logic import (
    Network,
    Points,
    formula3,
    formula4,
    formula5,
    formula6,
    get_demand_points_from_neighberhood,
)

# ---------------------------------------------------------------------------
# Map / editor constants
# ---------------------------------------------------------------------------
MAP_CENTER = (31.24524, 34.78958)
MAP_ZOOM = 13
MIN_ROUTE_KM = 3.0
EDIT_COLOR = "red"
SNAPSHOT_COLORS = ["green", "orange", "purple", "blue", "cadetblue", "darkred"]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def build_network_from_nodes(nodes, points: Points) -> Network:
    net = Network()
    for node in nodes:
        net.add_node(tuple(node))
    if len(nodes) >= 2:
        net._Network__calculate_network(points)
    return net


# ---------------------------------------------------------------------------
# NetworkEditor
# ---------------------------------------------------------------------------

class NetworkEditor:
    def __init__(self, neighborhoods_data, points: Points):
        self.neighborhoods_data = neighborhoods_data
        self.points = points

        self.edit_markers = []
        self.edit_segments = []
        self.saved_snapshots = []
        self.saved_layers = []

        self.map = Map(center=MAP_CENTER, zoom=MAP_ZOOM)
        self.map.add_control(
            MeasureControl(
                position="topleft",
                active_color="orange",
                primary_length_unit="meters",
            )
        )

        self.info_panel = HTML(
            value="",
            layout={"width": "100%", "padding": "10px"},
        )

        self.save_btn = Button(description="Save Snapshot", button_style="success")
        self.new_btn = Button(description="New Editable Network", button_style="warning")
        self.undo_btn = Button(description="Undo Last Node", button_style="info")
        self.clear_saved_btn = Button(description="Clear Saved Snapshots", button_style="danger")

        self.save_btn.on_click(self.on_save)
        self.new_btn.on_click(self.on_new_network)
        self.undo_btn.on_click(self.on_undo_last_node)
        self.clear_saved_btn.on_click(self.on_clear_saved)

        self.map.on_interaction(self.on_map_click)

        self.draw_neighborhoods()
        self.refresh_output("Click the map to add the first node.")

    def widget(self) -> VBox:
        return VBox(
            [
                self.map,
                HBox([self.save_btn, self.new_btn, self.undo_btn, self.clear_saved_btn]),
                self.info_panel,
            ]
        )

    def get_current_nodes(self) -> list:
        return [tuple(marker.location) for marker in self.edit_markers]

    def get_current_network(self):
        nodes = self.get_current_nodes()
        if len(nodes) < 2:
            return None
        return build_network_from_nodes(nodes, self.points)

    def draw_neighborhoods(self):
        colors = ["green", "orange", "purple", "blue"]
        for i, coords in enumerate(self.neighborhoods_data):
            self.map.add_layer(
                Polygon(
                    locations=coords,
                    color=colors[i % len(colors)],
                    fill_color=colors[i % len(colors)],
                    fill_opacity=0.2,
                    weight=2,
                )
            )

    def add_marker(self, lat: float, lon: float):
        marker = Marker(
            location=(lat, lon),
            draggable=True,
            title=f"Node {len(self.edit_markers) + 1}",
        )

        def _on_location_change(change):
            if change["name"] == "location":
                self.refresh_edit_line()
                self.refresh_output("Node moved.")

        marker.observe(_on_location_change, names="location")
        self.edit_markers.append(marker)
        self.map.add_layer(marker)
        self.refresh_marker_titles()
        self.refresh_edit_line()

    def refresh_marker_titles(self):
        for i, marker in enumerate(self.edit_markers, start=1):
            marker.title = f"Node {i}"

    def clear_edit_segments(self):
        for seg in self.edit_segments:
            self.map.remove_layer(seg)
        self.edit_segments = []

    def refresh_edit_line(self):
        self.clear_edit_segments()
        nodes = self.get_current_nodes()
        if len(nodes) < 2:
            return
        for i in range(len(nodes) - 1):
            seg = Polyline(
                locations=[nodes[i], nodes[i + 1]],
                color=EDIT_COLOR,
                weight=4,
                opacity=0.9,
            )
            self.map.add_layer(seg)
            self.edit_segments.append(seg)

    def add_saved_snapshot_to_map(self, nodes: list, color: str):
        for i in range(len(nodes) - 1):
            seg = Polyline(
                locations=[nodes[i], nodes[i + 1]],
                color=color,
                weight=3,
                opacity=0.65,
            )
            self.map.add_layer(seg)
            self.saved_layers.append(seg)

    def refresh_output(self, message: str = ""):
        nodes = self.get_current_nodes()
        net = self.get_current_network() if len(nodes) >= 2 else None

        rows = []

        rows.append("<b>Current editable network</b>")
        rows.append(f"<span style='color:gray'>{message}</span>")

        if not nodes:
            rows.append("No nodes yet.")
        else:
            rows.append(f"Nodes: <b>{len(nodes)}</b>")

        if net is not None:
            rows.append(f"L = <b>{net.L:.2f} km</b>")
            rows.append(f"K = <b>{net.K}</b>")
            rows.append(f"Network inertia = <b>{net.network_inertia:.4f}</b>")
            rows.append("<hr/>")
            rows.append(f"formula3 (article) = <b>{formula3(net):.2f}%</b>")
            rows.append(f"formula4 = <b>{formula4(net):.2f}%</b>")
            rows.append(f"formula5 = <b>{formula5(net):.2f}%</b>")
            rows.append(f"formula6 = <b>{formula6(net):.2f}%</b>")

            if net.L < MIN_ROUTE_KM:
                remaining = MIN_ROUTE_KM - net.L
                rows.append(
                    f"<span style='color:orange'>&#9888; Keep drawing... "
                    f"{remaining:.2f} km more before minimum route length</span>"
                )
        elif nodes:
            rows.append("<span style='color:gray'>Add at least 2 nodes to compute the score.</span>")

        if self.saved_snapshots:
            rows.append("<hr/><b>Saved snapshots</b>")
            best_score = max(s["score"] for s in self.saved_snapshots)

            table = (
                "<table style='border-collapse:collapse;width:100%;font-size:13px'>"
                "<tr style='background:#f0f0f0'>"
                "<th style='padding:4px 8px;text-align:right'>Ver</th>"
                "<th style='padding:4px 8px;text-align:right'>Score</th>"
                "<th style='padding:4px 8px;text-align:right'>L (km)</th>"
                "<th style='padding:4px 8px;text-align:right'>K</th>"
                "<th style='padding:4px 8px;text-align:right'>Nodes</th>"
                "<th style='padding:4px 8px'></th>"
                "</tr>"
            )
            for s in self.saved_snapshots:
                best_mark = "&#11088; best" if s["score"] == best_score else ""
                color_dot = f"<span style='color:{s['color']}'>&#9679;</span> "
                table += (
                    "<tr>"
                    f"<td style='padding:4px 8px;text-align:right'>{color_dot}{s['version']}</td>"
                    f"<td style='padding:4px 8px;text-align:right'>{s['score']:.2f}%</td>"
                    f"<td style='padding:4px 8px;text-align:right'>{s['L']:.2f}</td>"
                    f"<td style='padding:4px 8px;text-align:right'>{s['K']}</td>"
                    f"<td style='padding:4px 8px;text-align:right'>{s['nodes']}</td>"
                    f"<td style='padding:4px 8px;color:green'>{best_mark}</td>"
                    "</tr>"
                )
            table += "</table>"
            rows.append(table)

        self.info_panel.value = "<br/>".join(rows)

    def on_map_click(self, **kwargs):
        if kwargs.get("type") != "click":
            return
        lat, lon = kwargs["coordinates"]
        self.add_marker(lat, lon)
        self.refresh_output(f"Added node {len(self.edit_markers)} at ({lat:.5f}, {lon:.5f})")

    def on_save(self, _):
        nodes = self.get_current_nodes()
        cur_net = self.get_current_network()
        if len(nodes) < 2:
            self.refresh_output("Add at least 2 nodes before saving.")
            return
        if cur_net.L < 2:
            self.refresh_output("Network needs to be at least 2 km to save.")
            return

        score = formula4(cur_net)
        version = len(self.saved_snapshots) + 1
        color = SNAPSHOT_COLORS[(version - 1) % len(SNAPSHOT_COLORS)]

        self.saved_snapshots.append(
            {
                "version": version,
                "score": score,
                "nodes": len(nodes),
                "L": round(cur_net.L, 2),
                "K": cur_net.K,
                "node_locations": list(nodes),
                "color": color,
            }
        )
        self.add_saved_snapshot_to_map(nodes, color)
        self.refresh_output(f"Saved snapshot #{version}.")

    def on_new_network(self, _):
        self.clear_edit_segments()
        for marker in self.edit_markers:
            self.map.remove_layer(marker)
        self.edit_markers = []
        self.refresh_output("Started a new editable network. Saved snapshots stayed on the map.")

    def on_undo_last_node(self, _):
        if not self.edit_markers:
            self.refresh_output("Nothing to undo.")
            return
        last_marker = self.edit_markers.pop()
        self.map.remove_layer(last_marker)
        self.refresh_marker_titles()
        self.refresh_edit_line()
        self.refresh_output("Removed last node.")

    def on_clear_saved(self, _):
        for layer in self.saved_layers:
            self.map.remove_layer(layer)
        self.saved_layers = []
        self.saved_snapshots = []
        self.refresh_output("Cleared all saved snapshots from the map.")


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def prepare_points() -> Points:
    pts = Points()
    for i in range(len(hood_border)):
        df = get_demand_points_from_neighberhood(hood_border[i], hood_population[i], i)
        points_latlon = gpd.GeoSeries(df["point"], crs="EPSG:2039").to_crs(epsg=4326)
        pts.add_area_in_demand_zone(i + 1, area_for_each_neighberhood_beer_sheva[i])
        for idx, point_geom in points_latlon.items():
            pts.add_demand_point(
                i + 1,
                point_geom.y,
                point_geom.x,
                df.loc[idx, "estimated_people"],
            )
    return pts


# ---------------------------------------------------------------------------
# Solara page
# ---------------------------------------------------------------------------

@solara.component
def Page():
    solara.Title("Network Goodness")

    with solara.Column():
        solara.Markdown("# Network Goodness Calculation")
        solara.Markdown(
            "Draw a network by clicking the map and compare results. "
            "Click to add nodes, drag to reposition them."
        )

        points = solara.use_memo(prepare_points, dependencies=[])

        if points is None:
            solara.Text("Loading demand points from OSM cache...")
            return

        editor = NetworkEditor(
            neighborhoods_data=hood_border,
            points=points,
        )

        solara.display(editor.widget())