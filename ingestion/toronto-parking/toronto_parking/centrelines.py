"""
Fetcher for the Toronto Centreline (TCL) dataset from Toronto Open Data.

Downloads the WGS84 GeoJSON, extracts the street name (LNAME) and computes
the centroid of each road segment, then aggregates to one representative
lat/lon per unique street name for joining against dim_locations.
"""
import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)

CKAN_BASE_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
PACKAGE_ID = "toronto-centreline-tcl"
REQUEST_TIMEOUT = 180


def _get_centreline_resources() -> list[dict]:
    url = f"{CKAN_BASE_URL}/api/3/action/package_show"
    resp = requests.get(url, params={"id": PACKAGE_ID}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"CKAN API returned success=false for package {PACKAGE_ID}")
    return data["result"]["resources"]


def _find_geojson_url(resources: list[dict]) -> str:
    """Return the download URL for the WGS84 GeoJSON resource.

    Requires the URL to end in .geojson to avoid CKAN datastore dump endpoints
    that report format=GeoJSON but serve CSV content.
    Prefers 4326 (WGS84) over other projections.
    """
    candidates = [
        r for r in resources
        if r.get("format", "").upper() == "GEOJSON"
        and r.get("url", "").lower().endswith(".geojson")
    ]
    if not candidates:
        raise RuntimeError(
            f"No GeoJSON file resource found in CKAN package '{PACKAGE_ID}'. "
            f"Available: {[r.get('name') for r in resources]}"
        )
    # Prefer WGS84 (EPSG:4326) over local projections (e.g. 2952)
    wgs84 = [r for r in candidates if "4326" in r.get("url", "") or "4326" in r.get("name", "")]
    chosen = wgs84[0] if wgs84 else candidates[0]
    logger.info(f"Selected centreline resource: {chosen['name']} ({chosen['url']})")
    return chosen["url"]


def _segment_centroid(coordinates: list) -> tuple[float, float]:
    """Return the average lat/lon of a LineString or MultiLineString."""
    # MultiLineString: coordinates is a list of rings; flatten to a single list of pairs
    if coordinates and isinstance(coordinates[0][0], list):
        coordinates = [pt for ring in coordinates for pt in ring]
    lats = [c[1] for c in coordinates]
    lngs = [c[0] for c in coordinates]
    return sum(lats) / len(lats), sum(lngs) / len(lngs)


def fetch_centrelines() -> pd.DataFrame:
    """Download Toronto Centreline and return (lname, latitude, longitude).

    One row per unique street name. Coordinates are the average centroid
    across all road segments bearing that name.
    """
    resources = _get_centreline_resources()
    geojson_url = _find_geojson_url(resources)

    logger.info(f"Downloading Toronto Centreline from {geojson_url}")
    resp = requests.get(geojson_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    data = resp.json()
    features = data.get("features", [])
    logger.info(f"Parsing {len(features):,} centreline features")

    rows = []
    skipped = 0
    for f in features:
        props = f.get("properties") or {}
        lname = (props.get("LINEAR_NAME_FULL") or "").strip().upper()
        if not lname:
            skipped += 1
            continue

        geom = f.get("geometry") or {}
        coords = geom.get("coordinates", [])
        if not coords:
            skipped += 1
            continue

        lat, lng = _segment_centroid(coords)
        rows.append({"lname": lname, "centroid_lat": lat, "centroid_lng": lng})

    logger.info(f"Parsed {len(rows):,} segments, skipped {skipped} with missing name or geometry")

    df = pd.DataFrame(rows)
    aggregated = (
        df.groupby("lname", sort=False)
        .agg(latitude=("centroid_lat", "mean"), longitude=("centroid_lng", "mean"))
        .reset_index()
    )
    logger.info(f"Aggregated to {len(aggregated):,} unique street names")
    return aggregated
