"""
One-shot script that mirrors notebook cell 13 ("creating demand points")
but reads the cached building GeoJSONs from a local folder instead of
Google Drive. Pickles the resulting Points object so the FastAPI app
starts instantly.

Run once from the website/backend directory:
    python build_points_cache.py
"""

import os
import pickle
import sys

import geopandas as gpd

from calculations import (
    Points,
    hood_border,
    hood_population,
    area_for_each_neighberhood_beer_sheva,
)


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CACHE_DIR = os.path.join(PROJECT_ROOT, "ng_demand_points", "beer_sheva")
PICKLE_PATH = os.path.join(HERE, "cache", "beer_sheva_points.pkl")


def load_buildings_for_hood(hood_id: int) -> gpd.GeoDataFrame:
    """Same shape as the notebook's get_demand_points_from_neighberhood,
    but skips OSM/Drive and just reads the local cached GeoJSON."""
    path = os.path.join(CACHE_DIR, f"buildings_{hood_id}.geojson")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing cache file: {path}")

    buildings = gpd.read_file(path)
    buildings = buildings.to_crs(epsg=2039)
    buildings["area_m2"] = buildings.area
    buildings["point"] = buildings.geometry.representative_point()
    total_area = buildings["area_m2"].sum()
    buildings["estimated_people"] = (buildings["area_m2"] / total_area) * hood_population[hood_id]
    return buildings


def build_points() -> Points:
    points = Points()
    for i in range(len(hood_border)):
        print(f"  [hood {i}] loading buildings_{i}.geojson…")
        df = load_buildings_for_hood(i)

        points_latlon = gpd.GeoSeries(df["point"], crs="EPSG:2039").to_crs(epsg=4326)
        points.add_area_in_demand_zone(i + 1, area_for_each_neighberhood_beer_sheva[i])

        for idx, point_geom in points_latlon.items():
            lon = point_geom.x
            lat = point_geom.y
            demand = df.loc[idx, "estimated_people"]
            points.add_demand_point(i + 1, lat, lon, demand)
    return points


def main():
    print(f"Cache source: {CACHE_DIR}")
    print(f"Output pickle: {PICKLE_PATH}")
    if not os.path.isdir(CACHE_DIR):
        print(f"ERROR: cache dir does not exist: {CACHE_DIR}", file=sys.stderr)
        sys.exit(1)

    points = build_points()

    # Touch the property so the demand-zone centers get computed before
    # we pickle. That way the loaded object is ready to use immediately.
    _ = points.demand_zone_centers

    os.makedirs(os.path.dirname(PICKLE_PATH), exist_ok=True)
    with open(PICKLE_PATH, "wb") as f:
        pickle.dump(points, f)

    print(f"\nDone. Wrote {PICKLE_PATH}")
    print(f"  zones: {len(points.demand_zone_centers)}")
    print(f"  demand points: {len(points._demand_points)}")


if __name__ == "__main__":
    main()
