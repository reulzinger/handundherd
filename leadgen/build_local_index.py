#!/usr/bin/env python3
"""
Baut einmalig einen lokalen Such-Index aus einem OSM-Extract (z.B. von Geofabrik),
damit der eigentliche Scraper (scraper.py) nicht mehr auf die überlastete,
öffentliche Overpass-API angewiesen ist.

Pipeline (nutzt osmium-tool, muss installiert sein: `sudo apt install osmium-tool`):
  1. osmium tags-filter: nur Restaurants + Handwerker aus dem großen Extract rausfiltern
  2. osmium export: Ergebnis als GeoJSON exportieren (inkl. Geometrie)
  3. dieses Skript liest das GeoJSON, berechnet für Flächen (Gebäude) den Schwerpunkt
     als lat/lon und schreibt eine kompakte JSON-Liste mit genau den Feldern, die
     scraper.py braucht.

Nutzung:
    python3 build_local_index.py data/hessen-latest.osm.pbf data/index_hessen.json
"""

import json
import subprocess
import sys
from pathlib import Path


def run_osmium_pipeline(pbf_path: Path, workdir: Path) -> Path:
    filtered_pbf = workdir / "filtered.osm.pbf"
    geojson_path = workdir / "filtered.geojson"

    print(f"[1/2] osmium tags-filter auf {pbf_path.name} ...")
    subprocess.run(
        [
            "osmium", "tags-filter",
            str(pbf_path),
            "n/amenity=restaurant", "w/amenity=restaurant",
            "n/craft", "w/craft",
            "-o", str(filtered_pbf),
            "--overwrite",
        ],
        check=True,
    )

    print("[2/2] osmium export -> GeoJSON ...")
    subprocess.run(
        [
            "osmium", "export",
            str(filtered_pbf),
            "-o", str(geojson_path),
            "-f", "geojson",
            "-a", "type,id",  # sonst fehlen @type/@id in den properties -> keine osm_id
            "--overwrite",
        ],
        check=True,
    )
    return geojson_path


def polygon_centroid(coords) -> tuple[float, float]:
    """Einfacher Mittelwert der Außenring-Punkte - reicht für Umkreis-Filterung locker."""
    ring = coords[0]  # Polygon: [ring, ...holes]; MultiPolygon-Fall wird vorher aufgelöst
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def extract_latlon(geometry) -> tuple[float, float] | None:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates")
    if gtype == "Point":
        lon, lat = coords[0], coords[1]
        return lat, lon
    if gtype == "Polygon":
        return polygon_centroid(coords)
    if gtype == "MultiPolygon":
        # nimm das erste (meist größte) Teilpolygon
        return polygon_centroid(coords[0])
    if gtype in ("LineString", "MultiLineString"):
        # Handwerker/Restaurants sind praktisch nie als Linie gemappt, aber sicherheitshalber
        flat = coords if gtype == "LineString" else coords[0]
        lons = [p[0] for p in flat]
        lats = [p[1] for p in flat]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return None


def tags_to_record(props: dict, osm_id: str, lat: float, lon: float) -> dict:
    addr_parts = [props.get("addr:street", ""), props.get("addr:housenumber", "")]
    street = " ".join(p for p in addr_parts if p).strip()
    city_parts = [props.get("addr:postcode", ""), props.get("addr:city", "")]
    city = " ".join(p for p in city_parts if p).strip()
    address = ", ".join(p for p in (street, city) if p)

    if props.get("amenity") == "restaurant":
        category = "Restaurant"
    elif props.get("craft"):
        category = f"Handwerk:{props['craft']}"
    else:
        category = "unbekannt"

    website = props.get("website") or props.get("contact:website") or ""
    phone = props.get("phone") or props.get("contact:phone") or ""

    return {
        "osm_id": osm_id,
        "name": props.get("name", "(ohne Namen)"),
        "category": category,
        "address": address,
        "phone": phone,
        "website": website,
        "lat": lat,
        "lon": lon,
    }


def build_index(geojson_path: Path, output_path: Path) -> None:
    print(f"Lese {geojson_path} ...")
    with open(geojson_path, encoding="utf-8") as f:
        data = json.load(f)

    records = []
    skipped_no_geom = 0
    for feature in data.get("features", []):
        geometry = feature.get("geometry")
        props = feature.get("properties", {})
        if not geometry:
            skipped_no_geom += 1
            continue
        latlon = extract_latlon(geometry)
        if latlon is None:
            skipped_no_geom += 1
            continue
        lat, lon = latlon
        osm_id = f"{props.get('@type', 'unknown')}/{props.get('@id', '')}"
        records.append(tags_to_record(props, osm_id, lat, lon))

    print(f"{len(records)} Betriebe extrahiert ({skipped_no_geom} ohne verwertbare Geometrie übersprungen).")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False)

    print(f"Index geschrieben nach: {output_path}")


def main():
    if len(sys.argv) != 3:
        print(f"Nutzung: python3 {sys.argv[0]} <input.osm.pbf> <output_index.json>")
        sys.exit(1)

    pbf_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    workdir = pbf_path.parent

    if not pbf_path.exists():
        print(f"Datei nicht gefunden: {pbf_path}")
        sys.exit(1)

    geojson_path = run_osmium_pipeline(pbf_path, workdir)
    build_index(geojson_path, output_path)


if __name__ == "__main__":
    main()
