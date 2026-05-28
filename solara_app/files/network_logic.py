# network_logic.py
# Core domain logic: Points, Network, demand-point fetching, and scoring formulas.

from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as ShapelyPolygon

from data import area_for_each_neighberhood_beer_sheva

# Local folder used to cache OSM GeoJSON downloads between runs.
DRIVE_FOLDER = Path("data/ng_demand_points/beer_sheva_demand_points")
DRIVE_FOLDER.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Points
# ---------------------------------------------------------------------------

class Points:
    """Stores demand points and computes weighted zone centers."""
    def __init__(self):
        self._demand_points = []
        self._demand_zone_centers = defaultdict(float)
        self._q_in_demand_zone = defaultdict(float)
        self._area_in_demand_zone = defaultdict(float)
        self.__centers_dirty = False

    def add_demand_point(self, demand_zone, x, y, q) -> None:
        if None in (demand_zone, x, y, q):
            raise ValueError(
                f"Missing values. Received: zone={demand_zone}, x={x}, y={y}, q={q}"
            )
        self._demand_points.append({"demand_zone": demand_zone, "x": x, "y": y, "q": q})
        self.__centers_dirty = True

    def add_area_in_demand_zone(self, zone: int, area: float) -> None:
        self._area_in_demand_zone[zone] = area

    # -- properties ----------------------------------------------------------

    @property
    def demand_zone_centers(self):
        if self.__centers_dirty:
            self.__calculate_zone_demand_centers()
            self.__centers_dirty = False
        return self._demand_zone_centers

    @property
    def q_in_demand_zone(self):
        return self._q_in_demand_zone

    @property
    def area_in_demand_zone(self):
        return self._area_in_demand_zone

    # -- private helpers -----------------------------------------------------

    def __calculate_zone_demand_centers(self):
        q_x_num = defaultdict(float)
        q_y_num = defaultdict(float)
        self._q_in_demand_zone.clear()
        self._demand_zone_centers.clear()

        for dp in self._demand_points:
            zone = dp["demand_zone"]
            q_x_num[zone] += dp["x"] * dp["q"]
            q_y_num[zone] += dp["y"] * dp["q"]
            self._q_in_demand_zone[zone] += dp["q"]

        for zone, total_q in self._q_in_demand_zone.items():
            if total_q == 0:
                continue
            self._demand_zone_centers[zone] = (
                q_x_num[zone] / total_q,
                q_y_num[zone] / total_q,
            )


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

class Network:
    """Represents a transit route and computes coverage/inertia metrics."""

    def __init__(self):
        self._gravitating = 0.8   # service radius in km
        self._attracting = 0.4
        self._L = 0
        self._K = 0
        self._network_inertia = 0
        self._all_of_demand_zones_q = 0
        self._gravitating_demand_zones_area = 0
        self._network_nodes = []
        self.__network_dirty = False
        self.transformer = Transformer.from_crs("EPSG:4326", "EPSG:2039", always_xy=True)

    def add_node(self, node: tuple):
        self._network_nodes.append(node)
        self.__network_dirty = True
        if len(self._network_nodes) >= 2:
            projected = [self.transformer.transform(lon, lat) for lat, lon in self._network_nodes]
            self.geo_route = LineString(projected)
            self._L = self.geo_route.length / 1000  # metres → km

    def calculate_network(self, points: Points) -> None:
        if self.__network_dirty:
            self.__calculate_network(points)
            self.__network_dirty = False

    # -- properties ----------------------------------------------------------

    @property
    def gravitating(self):
        return self._gravitating

    @property
    def attracting(self):
        return self._attracting

    @property
    def L(self):
        return self._L

    @property
    def K(self):
        return self._K

    @property
    def network_inertia(self):
        return self._network_inertia

    @property
    def all_of_demand_zones_q(self):
        return self._all_of_demand_zones_q

    @property
    def gravitating_demand_zones_area(self):
        return self._gravitating_demand_zones_area

    # -- private helpers -----------------------------------------------------

    def __calculate_network(self, points: Points) -> None:
        self._K = 0
        self._network_inertia = 0
        self._all_of_demand_zones_q = 0
        self._gravitating_demand_zones_area = 0

        for zone, center in points.demand_zone_centers.items():
            lat, lon = center
            q = points.q_in_demand_zone[zone]
            area = points.area_in_demand_zone[zone]
            self._all_of_demand_zones_q += q

            point_m = Point(self.transformer.transform(lon, lat))
            min_dist = self.geo_route.distance(point_m) / 1000  # km

            if min_dist <= self._gravitating:
                self._gravitating_demand_zones_area += area
                self._network_inertia += q * (min_dist ** 2)
                self._K += 1


# ---------------------------------------------------------------------------
# OSM helpers
# ---------------------------------------------------------------------------

def get_demand_points_from_neighberhood(hood_border, hood_population, hood_id):
    """
    Returns a GeoDataFrame of residential buildings with estimated population
    per building, fetching from OSM on first run and caching locally afterwards.
    """
    file_name = DRIVE_FOLDER / f"buildings_{hood_id}.geojson"

    if file_name.exists():
        print(f"  [Cache] Loading hood {hood_id} from local cache…")
        buildings = gpd.read_file(file_name)
    else:
        print(f"  [OSM] Fetching hood {hood_id} from OSM and saving locally…")
        pts_lonlat = [(lon, lat) for (lat, lon) in hood_border]
        poly = ShapelyPolygon(pts_lonlat)
        buildings = ox.features_from_polygon(poly, tags={"building": True})
        buildings.to_file(file_name, driver="GeoJSON")
        print(f"  [Cache] Saved → {file_name}")

    buildings = buildings.to_crs(epsg=2039)
    buildings["area_m2"] = buildings.area
    buildings["point"] = buildings.geometry.representative_point()
    total_area = buildings["area_m2"].sum()
    buildings["estimated_people"] = (buildings["area_m2"] / total_area) * hood_population
    return buildings


def compute_neighborhood_areas(hood_borders):
    """Return a list of areas in km² for each neighbourhood polygon."""
    areas = []
    for border in hood_borders:
        pts_lonlat = [(lon, lat) for (lat, lon) in border]
        poly = ShapelyPolygon(pts_lonlat)
        hood_poly = gpd.GeoSeries([poly], crs="EPSG:4326").to_crs(epsg=2039)
        areas.append(hood_poly.area.iloc[0] / 1_000_000)
    return areas


# ---------------------------------------------------------------------------
# Scoring formulas
# ---------------------------------------------------------------------------

def formula1(network: Network):
    return (network.K ** 2 + network.K ** 3) / (network.L ** 2 + network.network_inertia)


def formula2(network: Network):
    return network.K ** 2 / network.L ** 2 + network.K ** 3 / network.network_inertia


def formula3(network: Network):
    """Original article formula."""
    beersheva_area = sum(area_for_each_neighberhood_beer_sheva)
    n = 19  # total neighbourhoods
    part1 = network.K ** 2 * beersheva_area
    part2 = 2 * n ** 2 * network.gravitating * network.L
    part3 = network.K ** 2 * network.attracting ** 2 * network.all_of_demand_zones_q
    part4 = 2 * n ** 2 * network.network_inertia
    return ((part1 / part2) + (part3 / part4)) * 100


def formula4(network: Network):
    """Uses gravitating-zones area instead of full Beer Sheva area."""
    n = 19
    part1 = network.K ** 2 * network.gravitating_demand_zones_area
    part2 = 2 * n ** 2 * network.gravitating * network.L
    part3 = network.K ** 2 * network.attracting ** 2 * network.all_of_demand_zones_q
    part4 = 2 * n ** 2 * network.network_inertia
    return ((part1 / part2) + (part3 / part4)) * 100


def formula5(network: Network):
    """Puts Beer Sheva area in denominator."""
    beersheva_area = sum(area_for_each_neighberhood_beer_sheva)
    n = 19
    part1 = network.K ** 2 * network.gravitating_demand_zones_area
    part2 = 2 * n ** 2 * network.gravitating * network.L * beersheva_area
    part3 = network.K ** 2 * network.attracting ** 2 * network.all_of_demand_zones_q
    part4 = 2 * n ** 2 * network.network_inertia
    return ((part1 / part2) + (part3 / part4)) * 100


def formula6(network: Network):
    """Swaps gravitating area into numerator/denominator positions."""
    n = 19
    part1 = network.K ** 2 * network.gravitating * network.L
    part2 = 2 * n ** 2 * network.gravitating_demand_zones_area
    part3 = network.K ** 2 * network.attracting ** 2 * network.all_of_demand_zones_q
    part4 = 2 * n ** 2 * network.network_inertia
    return ((part1 / part2) + (part3 / part4)) * 100
