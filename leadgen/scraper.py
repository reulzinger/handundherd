#!/usr/bin/env python3
"""
Lead-Scraper für Hand & Herd: findet Handwerker & Restaurants in Frankfurt/Umgebung
über OpenStreetMap (Overpass API, kostenlos, kein API-Key nötig) und bewertet
ihre Website nach "wie alt/veraltet wirkt sie" mittels einfacher Heuristiken.

Nutzung:
    python3 scraper.py --category both --radius 20 --output output/leads.csv

Rechtlich/ethisch:
- OSM-Daten stehen unter ODbL — bei Weiterveröffentlichung Attribution nötig
  (siehe https://www.openstreetmap.org/copyright). Für internen Gebrauch (Lead-Liste)
  unproblematisch.
- Es wird nur die öffentliche Startseite jeder Firma abgerufen (kein Login, keine
  privaten Bereiche), robots.txt wird respektiert, es gibt ein Delay zwischen Requests.
- Für die Kontaktaufnahme selbst: in Deutschland ist unaufgeforderte Werbe-E-Mail
  auch B2B ohne vorherige Zustimmung nach UWG §7 riskant. Für Kaltakquise lieber
  Post oder Telefon nutzen, nicht automatisiert E-Mails verschicken.
"""

import argparse
import csv
import json
import math
import re
import time
import sys
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

USER_AGENT_OSM = "handundherd-leadgen/1.0 (privates Lead-Recherche-Tool, Kontakt: reulzinger@googlemail.com)"
USER_AGENT_SITE = "Mozilla/5.0 (compatible; handundherd-leadgen/1.0; +Recherchezwecke, Kontakt: reulzinger@googlemail.com)"

FRANKFURT_LAT = 50.1109
FRANKFURT_LON = 8.6821

# Region-Presets im Rhein-Main-Raum: name -> (lat, lon, empfohlener Radius in km)
# Radius pro Region bewusst klein gehalten (Stadt + nahes Umland), damit ein
# einzelner Lauf überschaubar bleibt. Mit --radius lässt sich das übersteuern.
REGIONS = {
    "frankfurt": (50.1109, 8.6821, 12),
    "offenbach": (50.0956, 8.7761, 8),
    "wiesbaden": (50.0782, 8.2398, 10),
    "mainz": (49.9929, 8.2473, 10),
    "darmstadt": (49.8728, 8.6512, 10),
    "hanau": (50.1310, 8.9166, 8),
    "bad-homburg": (50.2266, 8.6183, 8),
    "oberursel": (50.2028, 8.5814, 8),
    "ruesselsheim": (49.9902, 8.4111, 8),
    "aschaffenburg": (49.9769, 9.1508, 10),
    "giessen": (50.5841, 8.6779, 10),
    "friedberg": (50.3372, 8.7553, 8),
    "langen": (49.9928, 8.6741, 6),
    "neu-isenburg": (50.0505, 8.6879, 6),
}

MODERN_HINTS = [
    "tailwind", "bootstrap", "bulma", "foundation.min.css",
    "next/static", "_next/", "wp-content/themes", "react", "vue.js", "vuejs",
    "vite", "webpack", "cdn.shopify",
]

OLD_GENERATOR_HINTS = [
    "microsoft frontpage", "adobe golive", "microsoft word", "dreamweaver mx",
]

# Persistente Lead-Liste: scraper.py ergänzt hier nur NEUE Treffer, bestehende
# Zeilen (inkl. manuell gepflegtem Status) bleiben unangetastet. Verwaltet wird
# die Liste mit manage_leads.py (markieren, Notiz, dauerhaft löschen).
DEFAULT_MASTER = "output/leads_master.csv"
DEFAULT_DELETED_IDS = "output/deleted_ids.txt"
MASTER_FIELDNAMES = [
    "name", "category", "score", "label",
    "entwurf_gebaut", "anfrage_geschickt", "notiz",
    "address", "phone", "website", "signals", "osm_id", "hinzugefuegt_am",
]


def load_master(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {row["osm_id"]: row for row in csv.DictReader(f)}


def load_deleted_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def build_overpass_query(lat: float, lon: float, radius_m: int, category: str) -> str:
    parts = []
    if category in ("restaurant", "both"):
        parts.append(f'node(around:{radius_m},{lat},{lon})["amenity"="restaurant"];')
        parts.append(f'way(around:{radius_m},{lat},{lon})["amenity"="restaurant"];')
    if category in ("handwerk", "both"):
        parts.append(f'node(around:{radius_m},{lat},{lon})["craft"];')
        parts.append(f'way(around:{radius_m},{lat},{lon})["craft"];')
    body = "\n  ".join(parts)
    return f"""
[out:json][timeout:120];
(
  {body}
);
out center tags;
""".strip()


def fetch_osm_entries(lat: float, lon: float, radius_m: int, category: str) -> list[dict]:
    query = build_overpass_query(lat, lon, radius_m, category)
    last_err = None
    # (connect_timeout, read_timeout) statt einem einzelnen Wert: read_timeout ist die
    # Zeit zwischen zwei empfangenen Datenpaketen, nicht die Gesamtzeit — ein einzelner
    # hoher Wert (z.B. 120) kann sonst bei einer trödelnden Verbindung sehr lange hängen.
    for attempt, endpoint in enumerate(OVERPASS_ENDPOINTS):
        try:
            resp = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": USER_AGENT_OSM},
                timeout=(10, 60),
            )
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as e:  # noqa: BLE001 - nächsten Mirror probieren
            last_err = e
            if attempt < len(OVERPASS_ENDPOINTS) - 1:
                time.sleep(5)
            continue
    raise RuntimeError(
        f"Overpass-Abfrage fehlgeschlagen (alle Endpunkte, evtl. gerade rate-limited): {last_err}\n"
        "Tipp: ein paar Minuten warten und erneut versuchen, oder kleineren Radius/eine Kategorie testen."
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_local_records(index_path: Path, lat: float, lon: float, radius_km: float, category: str) -> list[dict]:
    """Lädt einen von build_local_index.py erzeugten Index und filtert nach Umkreis+Kategorie.
    Ersetzt die Overpass-Live-Abfrage (fetch_osm_entries + tags_to_record) komplett."""
    with open(index_path, encoding="utf-8") as f:
        all_records = json.load(f)

    def category_matches(rec_category: str) -> bool:
        if category == "both":
            return True
        if category == "restaurant":
            return rec_category == "Restaurant"
        if category == "handwerk":
            return rec_category.startswith("Handwerk:")
        return False

    records = []
    for rec in all_records:
        if not category_matches(rec["category"]):
            continue
        if haversine_km(lat, lon, rec["lat"], rec["lon"]) > radius_km:
            continue
        records.append({k: v for k, v in rec.items() if k not in ("lat", "lon")})
    return records


def tags_to_record(el: dict) -> dict:
    tags = el.get("tags", {})
    addr_parts = [
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
    ]
    street = " ".join(p for p in addr_parts if p).strip()
    city_parts = [tags.get("addr:postcode", ""), tags.get("addr:city", "")]
    city = " ".join(p for p in city_parts if p).strip()
    address = ", ".join(p for p in (street, city) if p)

    if tags.get("amenity") == "restaurant":
        category = "Restaurant"
    elif tags.get("craft"):
        category = f"Handwerk:{tags['craft']}"
    else:
        category = "unbekannt"

    website = tags.get("website") or tags.get("contact:website") or ""
    phone = tags.get("phone") or tags.get("contact:phone") or ""

    return {
        "osm_id": f"{el.get('type')}/{el.get('id')}",
        "name": tags.get("name", "(ohne Namen)"),
        "category": category,
        "address": address,
        "phone": phone,
        "website": website,
    }


_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def is_allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"
    if domain not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{domain}/robots.txt")
        try:
            rp.read()
        except Exception:  # noqa: BLE001 - kein robots.txt = alles erlaubt
            rp = None
        _robots_cache[domain] = rp
    rp = _robots_cache[domain]
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT_SITE, url)
    except Exception:  # noqa: BLE001
        return True


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.IGNORECASE):
        raw = "https://" + raw
    return raw


def analyze_site(url: str) -> tuple[int, list[str], str]:
    """Gibt (score, signale, label) zurück. Höherer Score = wirkt älter/veralteter."""
    signals = []
    score = 0

    if not is_allowed_by_robots(url):
        return (0, ["robots.txt verbietet Zugriff -> übersprungen"], "ÜBERSPRUNGEN")

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT_SITE},
            timeout=10,
            allow_redirects=True,
        )
        final_url = resp.url
        html = resp.text
    except requests.exceptions.SSLError:
        return (7, ["SSL-Fehler beim Abruf (evtl. kein gültiges Zertifikat)"], "ALT/PROBLEMATISCH")
    except Exception as e:  # noqa: BLE001
        return (8, [f"Website nicht erreichbar ({type(e).__name__})"], "NICHT ERREICHBAR")

    html_lower = html.lower()

    if not final_url.lower().startswith("https"):
        score += 2
        signals.append("kein HTTPS")

    if "viewport" not in html_lower:
        score += 3
        signals.append("kein responsive Viewport-Meta-Tag")

    table_count = html_lower.count("<table")
    if table_count >= 3:
        score += 3
        signals.append(f"Table-Layout ({table_count}x <table>)")

    if "<font" in html_lower:
        score += 2
        signals.append("veraltete <font>-Tags")

    if "<marquee" in html_lower or "<blink" in html_lower:
        score += 5
        signals.append("<marquee>/<blink> gefunden (sehr alt)")

    if ".swf" in html_lower or "shockwave-flash" in html_lower:
        score += 4
        signals.append("Flash-Elemente referenziert")

    if "cellpadding" in html_lower or "cellspacing" in html_lower:
        score += 2
        signals.append("cellpadding/cellspacing-Attribute (altes HTML)")

    year_matches = [int(y) for y in re.findall(r"(19|20)\d{2}", html)]
    # nur plausible Jahre in Copyright-Nähe berücksichtigen
    copyright_years = [int(y) for y in re.findall(r"(?:©|copyright)[^\d]{0,15}(\d{4})", html_lower)]
    if copyright_years:
        max_year = max(copyright_years)
        current_year = datetime.now(timezone.utc).year
        if max_year < current_year - 4:
            bonus = min(current_year - max_year, 5)
            score += bonus
            signals.append(f"Copyright-Jahr {max_year} (veraltet)")

    generator_match = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', html, re.IGNORECASE)
    if generator_match:
        gen_val = generator_match.group(1).lower()
        if any(hint in gen_val for hint in OLD_GENERATOR_HINTS):
            score += 3
            signals.append(f"Generator-Meta deutet auf altes Tool hin ({generator_match.group(1)})")

    modern_found = [hint for hint in MODERN_HINTS if hint in html_lower]
    if modern_found:
        score -= 5
        signals.append(f"moderne Framework-Hinweise gefunden ({', '.join(modern_found[:3])})")

    score = max(score, 0)

    if score >= 6:
        label = "ALT/vermutlich veraltet"
    elif score <= 1:
        label = "MODERN"
    else:
        label = "UNKLAR"

    return (score, signals, label)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--category", choices=["restaurant", "handwerk", "both"], default="both")
    parser.add_argument(
        "--region",
        choices=sorted(REGIONS.keys()),
        default=None,
        help="Vordefinierte Region im Rhein-Main-Raum statt manueller Koordinaten (siehe --list-regions)",
    )
    parser.add_argument("--list-regions", action="store_true", help="Verfügbare Regionen mit Koordinaten/Empfehlungs-Radius auflisten und beenden")
    parser.add_argument("--lat", type=float, default=None, help="Eigener Mittelpunkt (überschreibt --region), default Frankfurt")
    parser.add_argument("--lon", type=float, default=None, help="Eigener Mittelpunkt (überschreibt --region), default Frankfurt")
    parser.add_argument("--radius", type=float, default=None, help="Radius in km um den Mittelpunkt (default: Region-Empfehlung, sonst 15)")
    parser.add_argument("--limit", type=int, default=None, help="Max. Anzahl Websites analysieren (zum Testen)")
    parser.add_argument("--delay", type=float, default=1.5, help="Sekunden Pause zwischen Website-Abrufen")
    parser.add_argument("--output", default=None, help="Pfad für CSV-Ausgabe")
    parser.add_argument(
        "--local-index",
        default="data/index_hessen.json",
        help="Lokaler Index von build_local_index.py (default: data/index_hessen.json). "
             "Falls die Datei existiert, wird sie statt der Live-Overpass-Abfrage genutzt "
             "(schneller, zuverlässiger, keine Server-Rate-Limits). --no-local-index erzwingt Live-Abfrage.",
    )
    parser.add_argument("--no-local-index", action="store_true", help="Immer Live-Overpass-Abfrage nutzen, auch wenn ein lokaler Index existiert")
    parser.add_argument(
        "--include-modern",
        action="store_true",
        help="Auch Treffer mit Label MODERN in die CSV schreiben (Standard: werden rausgefiltert, da kein Lead)",
    )
    args = parser.parse_args()

    if args.list_regions:
        print("Verfügbare Regionen (--region <name>):\n")
        for name, (lat, lon, rec_radius) in sorted(REGIONS.items()):
            print(f"  {name:15s} lat={lat:<10} lon={lon:<10} Empfehlungs-Radius={rec_radius}km")
        return

    if args.lat is not None or args.lon is not None:
        # eigene Koordinaten haben Vorrang vor --region
        lat = args.lat if args.lat is not None else FRANKFURT_LAT
        lon = args.lon if args.lon is not None else FRANKFURT_LON
        default_radius = 15
        region_label = "custom"
    elif args.region:
        lat, lon, default_radius = REGIONS[args.region]
        region_label = args.region
    else:
        lat, lon, default_radius = REGIONS["frankfurt"]
        region_label = "frankfurt"

    radius_km = args.radius if args.radius is not None else default_radius
    radius_m = int(radius_km * 1000)
    is_master_mode = args.output is None
    output_path = args.output or DEFAULT_MASTER

    local_index_path = Path(args.local_index) if args.local_index else None
    use_local = local_index_path is not None and local_index_path.exists() and not args.no_local_index

    if use_local:
        print(f"Nutze lokalen Index: {local_index_path} (Region={region_label}, Kategorie={args.category}, Radius={radius_km}km um ({lat},{lon}))")
        records = load_local_records(local_index_path, lat, lon, radius_km, args.category)
        print(f"{len(records)} Einträge aus lokalem Index gefunden.")
    else:
        print(f"Frage OpenStreetMap ab: Region={region_label}, Kategorie={args.category}, Radius={radius_km}km um ({lat},{lon}) ...")
        elements = fetch_osm_entries(lat, lon, radius_m, args.category)
        print(f"{len(elements)} Einträge von OSM erhalten.")
        records = [tags_to_record(el) for el in elements]
    # Duplikate über Name+Adresse grob rausfiltern
    seen = set()
    unique_records = []
    for r in records:
        key = (r["name"], r["address"])
        if key in seen:
            continue
        seen.add(key)
        unique_records.append(r)
    records = unique_records
    print(f"{len(records)} eindeutige Betriebe nach Deduplizierung.")

    no_website = [r for r in records if not r["website"]]
    with_website = [r for r in records if r["website"]]
    print(f"Davon ohne hinterlegte Website: {len(no_website)} (= starke Leads), mit Website: {len(with_website)}")

    if args.limit:
        with_website = with_website[: args.limit]

    results = []

    for r in no_website:
        results.append({**r, "score": 99, "label": "KEINE WEBSITE HINTERLEGT", "signals": "kein website-Tag in OSM - ggf. hat die Firma gar keine Website"})

    for i, r in enumerate(with_website, 1):
        url = normalize_url(r["website"])
        print(f"[{i}/{len(with_website)}] Prüfe {r['name']} -> {url}")
        try:
            score, signals, label = analyze_site(url)
        except Exception as e:  # noqa: BLE001
            score, signals, label = 0, [f"Fehler bei Analyse: {e}"], "FEHLER"
        results.append({**r, "score": score, "label": label, "signals": "; ".join(signals)})
        time.sleep(args.delay)

    if not args.include_modern:
        before = len(results)
        results = [r for r in results if r["label"] != "MODERN"]
        print(f"{before - len(results)} Treffer mit moderner Website rausgefiltert (nicht in der CSV, kein Lead).")

    today = datetime.now().strftime("%Y-%m-%d")
    output_file = Path(output_path)

    if is_master_mode:
        deleted_ids_path = output_file.parent / "deleted_ids.txt" if str(output_file) != DEFAULT_MASTER else Path(DEFAULT_DELETED_IDS)
        existing_master = load_master(output_file)
        deleted_ids = load_deleted_ids(deleted_ids_path)

        final_rows = list(existing_master.values())
        existing_ids = set(existing_master.keys())
        new_count = 0
        skipped_deleted = 0
        for r in results:
            if r["osm_id"] in deleted_ids:
                skipped_deleted += 1
                continue
            if r["osm_id"] in existing_ids:
                continue  # schon bekannt, Tracking-Status/Notiz nicht überschreiben
            final_rows.append({
                **r,
                "entwurf_gebaut": "",
                "anfrage_geschickt": "",
                "notiz": "",
                "hinzugefuegt_am": today,
            })
            new_count += 1
        print(f"{new_count} neue Leads zur Liste hinzugefügt, {skipped_deleted} übersprungen (bereits gelöscht), {len(existing_ids)} bereits bekannt.")
    else:
        final_rows = [{**r, "entwurf_gebaut": "", "anfrage_geschickt": "", "notiz": "", "hinzugefuegt_am": today} for r in results]

    final_rows.sort(key=lambda r: float(r["score"]), reverse=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDNAMES)
        writer.writeheader()
        for r in final_rows:
            writer.writerow(r)

    print(f"\nFertig. {len(final_rows)} Leads insgesamt in: {output_file}")
    top = [r for r in final_rows if r["label"] in ("ALT/vermutlich veraltet", "KEINE WEBSITE HINTERLEGT")]
    print(f"Davon {len(top)} vielversprechende Leads (alte Website oder keine Website).")


if __name__ == "__main__":
    sys.exit(main())
