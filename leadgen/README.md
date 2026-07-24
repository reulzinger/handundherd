# Lead-Scraper (Handwerker & Restaurants, Rhein-Main-Raum)

Findet Handwerks-Betriebe und Restaurants über OpenStreetMap-Daten und bewertet
ihre Website danach, wie alt/veraltet sie wirkt — für Akquise (Hand & Herd
bietet Website-Relaunch an).

## Setup

```bash
cd leadgen
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Empfohlen: lokaler Index statt Live-Abfrage

Die öffentliche Overpass-API (live OSM-Abfrage) ist eine kostenlose
Community-Infrastruktur und regelmäßig überlastet ("server too busy",
Timeouts) — für zuverlässige, wiederholte Läufe stattdessen einmalig einen
lokalen Index aus einem Regional-Extract bauen:

```bash
# einmalig: osmium-tool installieren (Debian/Ubuntu)
sudo apt install osmium-tool

# einmalig: Hessen-Extract laden (~340MB, deckt Frankfurt, Offenbach, Wiesbaden,
# Darmstadt, Hanau, Bad Homburg, Oberursel, Rüsselsheim, Gießen, Friedberg,
# Langen, Neu-Isenburg ab)
mkdir -p data
curl -L -o data/hessen-latest.osm.pbf \
  https://download.geofabrik.de/europe/germany/hessen-latest.osm.pbf

# einmalig: Index bauen (dauert ein paar Minuten)
python3 build_local_index.py data/hessen-latest.osm.pbf data/index_hessen.json
```

Danach nutzt `scraper.py` diesen Index automatisch (erkennt `data/index_hessen.json`
und braucht keine Netzwerk-Abfrage mehr für die Betriebs-Suche — nur noch für
den Abruf der einzelnen Firmen-Websites selbst). Ein kompletter Lauf dauert dann
nur noch so lange wie die Website-Checks brauchen (Anzahl Treffer × Delay).

**Mainz** (Rheinland-Pfalz) und **Aschaffenburg** (Bayern) sind im Hessen-Extract
nicht enthalten — dafür bräuchte man zusätzlich `rheinland-pfalz-latest.osm.pbf`
bzw. `bayern-latest.osm.pbf` von Geofabrik und müsste `build_local_index.py`
darauf erneut laufen lassen (Index-Dateien könnten dann z.B. gemergt werden).
Ohne lokalen Index für diese beiden Regionen fällt der Scraper automatisch auf
die Live-Overpass-Abfrage zurück.

Mit `--no-local-index` erzwingt man in jedem Fall die Live-Abfrage.

## Nutzung

```bash
# Verfügbare Regionen ansehen
python3 scraper.py --list-regions

# Frankfurt, beide Kategorien, empfohlener Radius (12km)
python3 scraper.py --region frankfurt

# Nur Restaurants in Offenbach
python3 scraper.py --region offenbach --category restaurant

# Eigener Mittelpunkt + Radius statt Region-Preset
python3 scraper.py --lat 50.15 --lon 8.70 --radius 5

# Zum Testen auf wenige Website-Checks begrenzen, ohne die echte Liste zu verändern
python3 scraper.py --region frankfurt --limit 10 --output output/test.csv
```

Ohne `--output` schreibt der Scraper standardmäßig in eine **persistente Liste**
`output/leads_master.csv` — jeder weitere Lauf (egal welche Region) **ergänzt**
nur neue Treffer, bestehende Einträge und ihr Bearbeitungsstatus bleiben
unangetastet. Nur mit explizitem `--output <pfad>` entsteht stattdessen ein
einmaliger, nicht-persistenter Report (z.B. zum schnellen Testen).

Spalten: `name, category, score, label, entwurf_gebaut, anfrage_geschickt, notiz,
address, phone, website, signals, osm_id, hinzugefuegt_am`. Sortiert nach Score
absteigend (Leads ohne Website ganz oben, dann von "am ältesten wirkend" zu
"am wenigsten alt"). Websites mit Label `MODERN` werden standardmäßig
rausgefiltert (`--include-modern` um sie trotzdem mit aufzunehmen).

## Liste pflegen: `manage_leads.py`

```bash
# Liste ansehen (sortiert wie oben, mit Status-Flags)
python3 manage_leads.py list
python3 manage_leads.py list --offen          # nur noch nicht kontaktierte

# Fortschritt markieren
python3 manage_leads.py mark "Pizzeria San Marco" --entwurf     # Website-Entwurf gebaut
python3 manage_leads.py mark "Pizzeria San Marco" --anfrage     # Anfrage geschickt
python3 manage_leads.py mark "Pizzeria San Marco" --anfrage false   # zurücksetzen

# Notiz setzen
python3 manage_leads.py note "Pizzeria San Marco" "Chef bevorzugt Anruf ab 15 Uhr"

# Eintrag dauerhaft entfernen (nicht nützlicher Treffer)
python3 manage_leads.py delete "Pizzeria San Marco"
```

Ein Firmenname als Teilstring reicht (Groß-/Kleinschreibung egal); bei mehreren
Treffern zeigt das Tool die Kandidaten mit `osm_id` an, um gezielt eine davon
anzusprechen. **Löschen ist dauerhaft:** die `osm_id` landet zusätzlich in
`output/deleted_ids.txt` — dadurch taucht der Eintrag bei künftigen
`scraper.py`-Läufen nicht wieder auf, selbst wenn er in OSM weiter existiert.

`leads_master.csv` ist eine normale CSV — lässt sich also auch direkt in
LibreOffice/Excel/Google Sheets öffnen und durchsehen, wenn das bequemer ist
(dann aber Änderungen nicht während ein `scraper.py`- oder `manage_leads.py`-Lauf
läuft speichern, um sich nicht gegenseitig zu überschreiben).

## Wie die Bewertung funktioniert

- **KEINE WEBSITE HINTERLEGT** (Score 99) — in OSM ist keine Website eingetragen.
  Kann heißen: Firma hat wirklich keine Website (bester Lead) oder OSM-Eintrag ist
  unvollständig — vor Kontaktaufnahme kurz per Google prüfen.
- **ALT/vermutlich veraltet** (Score ≥ 6) — mehrere "alte Website"-Signale gefunden
  (kein responsives Viewport-Tag, Table-Layout, `<font>`-Tags, altes Copyright-Jahr,
  kein HTTPS, Flash-Reste, `<marquee>`/`<blink>` usw.)
- **UNKLAR** (Score 2–5) — manuell prüfen
- **MODERN** (Score ≤ 1) — moderne Frameworks/Responsive-Signale erkannt, wird
  standardmäßig aus der CSV rausgefiltert
- **NICHT ERREICHBAR** — Website down/DNS-Fehler → oft ebenfalls ein guter Lead
- **ÜBERSPRUNGEN** — robots.txt der Seite verbietet automatisierten Zugriff, wurde
  übersprungen statt ignoriert

## Wichtig: rechtlich/ethisch

- OSM-Daten stehen unter ODbL — bei interner Nutzung als Lead-Liste unproblematisch,
  bei Veröffentlichung Attribution nötig (openstreetmap.org/copyright).
- Es wird nur die öffentliche Startseite jeder Firma abgerufen, `robots.txt` wird
  respektiert, es gibt ein Delay zwischen Requests (Standard 1,5s) — keine
  Serverlast erzeugen.
- **Kontaktaufnahme:** In Deutschland ist unaufgeforderte Werbe-E-Mail auch im B2B-Bereich
  ohne vorherige Geschäftsbeziehung nach UWG §7 riskant (Abmahngefahr). Für Kaltakquise
  lieber Brief oder Telefonanruf nutzen, keine automatisierten Massen-E-Mails verschicken.
- Bewusst **nicht** auf Verzeichnisse wie Gelbe Seiten/Das Örtliche aufgebaut — diese
  sind als Datenbank nach §87a-e UrhG geschützt, systematisches Scraping ist dort
  rechtlich riskant (Abmahnungen bekannt). OSM ist explizit für programmatische
  Nutzung gedacht.

## Dateien

| Datei | Zweck |
|---|---|
| `scraper.py` | Hauptskript: Firmen finden (lokal oder live) + Website-Alter bewerten + in `leads_master.csv` einpflegen |
| `manage_leads.py` | Liste pflegen: markieren, Notiz setzen, dauerhaft löschen |
| `build_local_index.py` | Einmalig: OSM-Extract → gefilterter lokaler Index |
| `data/` | Downloads + Index (Git-ignoriert, groß) |
| `output/leads_master.csv` | Die persistente Lead-Liste mit Bearbeitungsstatus (Git-ignoriert) |
| `output/deleted_ids.txt` | Dauerhaft ausgeschlossene osm_ids (Git-ignoriert) |
