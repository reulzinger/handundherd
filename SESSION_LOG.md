# Session-Protokoll — Hand & Herd

> Zweck: Nahtloser Wiedereinstieg bei neuer Terminal-Session. Neuester Eintrag oben.
> **Vor der Arbeit:** diese Datei lesen. **Nach der Arbeit:** neuen Eintrag oben ergänzen (Datum, was gemacht, aktueller Stand, nächste Schritte).

---

## 2026-07-24 — Lead-Tracking ergänzt (persistente Liste, markieren, löschen)
**Kontext:** Aufbauend auf dem Lead-Scraper (siehe Eintrag darunter) wollte der User pro Firma Fortschritt festhalten ("Website-Entwurf gebaut?", "Anfrage geschickt?") und nicht nützliche Treffer dauerhaft aus der Liste entfernen können.

**Gebaut:**
- `scraper.py` schreibt jetzt standardmäßig (ohne `--output`) in eine persistente `output/leads_master.csv` statt in eine neue Datei pro Lauf — jeder Lauf **ergänzt nur neue Treffer** (Merge über `osm_id`), bestehender Bearbeitungsstatus bleibt unangetastet. `--output <pfad>` erzwingt weiterhin einen einmaligen, nicht-persistenten Report zum Testen.
- Neue Spalten: `entwurf_gebaut`, `anfrage_geschickt`, `notiz`, `hinzugefuegt_am`.
- Neues Tool `manage_leads.py`: `list [--offen]`, `mark <name> --entwurf|--anfrage [true|false]`, `note <name> "text"`, `delete <name>`. Namenssuche per Teilstring, bei Mehrdeutigkeit werden Kandidaten mit `osm_id` angezeigt statt etwas zu ändern.
- **Löschen ist dauerhaft:** gelöschte `osm_id`s landen in `output/deleted_ids.txt` und werden von `scraper.py` bei künftigen Läufen übersprungen, tauchen also nicht wieder auf.
- Bug gefunden+gefixt: `osmium export` liefert ohne `-a type,id` keine `@id`/`@type` in den Properties → `osm_id` war leer. Fix in `build_local_index.py`, Index (`data/index_hessen.json`) neu gebaut und funktioniert jetzt korrekt.
- End-to-End getestet (Region Langen, Restaurants): markieren, Notiz setzen, löschen, erneuter Scraper-Lauf → gelöschter Eintrag blieb korrekt draußen, bereits bekannte Einträge unverändert.

**Aktueller Stand:** `output/leads_master.csv` ist nach dem Test wieder geleert (Testdaten entfernt) — bereit für den ersten echten Durchlauf.

**Nächste Schritte:** Echte Läufe für gewünschte Regionen starten, Liste mit `manage_leads.py` durchgehen und pflegen.

**Details siehe:** `leadgen/README.md`.

## 2026-07-24 — Lead-Scraper gebaut (Handwerker/Restaurants mit veralteten Websites)
**Kontext:** User wollte einen Python-Scraper, der Handwerker & Restaurants in Frankfurt/Umgebung findet — bevorzugt solche mit "alten" Websites (Akquise-Ziel für Hand & Herd) oder ganz ohne Website.

**Gebaut:** `leadgen/` — neues Unterprojekt:
- `scraper.py` — findet Betriebe via OpenStreetMap-Daten, bewertet jede Website mit einer Heuristik (Score aus: fehlendes Viewport-Tag, Table-Layout, `<font>`/`<marquee>`-Tags, Flash-Reste, altes Copyright-Jahr, kein HTTPS, alte Generator-Meta-Tags; moderne Frameworks wie React/Tailwind/Bootstrap ziehen Punkte ab). Label MODERN wird standardmäßig aus der CSV gefiltert, Betriebe ganz ohne Website bekommen automatisch Top-Priorität (Score 99).
- `--region <name>` — 14 Presets im Rhein-Main-Raum (frankfurt, offenbach, wiesbaden, mainz, darmstadt, hanau, bad-homburg, oberursel, ruesselsheim, aschaffenburg, giessen, friedberg, langen, neu-isenburg), siehe `--list-regions`.
- `build_local_index.py` — **wichtig:** die öffentliche Overpass-API (Live-OSM-Abfrage) war mehrfach überlastet/timeoutete unabhängig von Radius/Kategorie (bestätigt per direktem curl-Test: "server too busy"). Deshalb umgestellt auf lokalen Index: einmalig `hessen-latest.osm.pbf` von Geofabrik geladen (342MB, `leadgen/data/`, Git-ignoriert), mit `osmium-tool` (via apt installiert) gefiltert + als GeoJSON exportiert, daraus `data/index_hessen.json` gebaut (15.471 Betriebe: Restaurants + Handwerker in ganz Hessen). `scraper.py` nutzt diesen Index automatisch wenn vorhanden (Radius-Filterung per Haversine-Distanz) — kein Netzwerk-Abhängigkeit mehr für die Betriebssuche, nur noch für den Abruf der einzelnen Firmen-Websites selbst.
- Getestet: `--region frankfurt --category both` (12km) lieferte in 18 Sekunden 2136 eindeutige Betriebe (1059 ohne Website, 1077 mit Website).
- Bewusst **nicht** auf Gelbe Seiten/Das Örtliche aufgebaut — als Datenbank nach §87a-e UrhG geschützt, Scraping dort rechtlich riskant (Abmahnungen bekannt bei diesen Anbietern). OSM ist explizit für programmatische Nutzung gedacht.

**Offene Punkte / nächste Schritte:**
- Mainz (Rheinland-Pfalz) und Aschaffenburg (Bayern) sind vom Hessen-Extract nicht abgedeckt — bräuchten zusätzliche Geofabrik-Extracts (siehe `leadgen/README.md`).
- Score-Schwellenwerte (aktuell ALT ≥6, MODERN ≤1) sind eine erste grobe Heuristik, ggf. beim echten Durchsehen der Ergebnisse nachjustieren.
- Voller Lauf über alle/mehrere Regionen noch nicht durchgeführt (nur Frankfurt getestet) — nächster Schritt wäre, systematisch Region für Region durchzugehen und die CSVs zu sichten.

**Details siehe:** `leadgen/README.md`.

## 2026-07-24 — Log-System eingerichtet
**Kontext:** Kein inhaltlicher Arbeits-Task heute, sondern Einrichtung dieses Protokolls auf Wunsch des Users. Projekt war bisher noch nicht im Memory-System erfasst.
**Zuletzt inhaltlich gemacht (aus Git-Historie, vor heute):**
- `b82b7b0` — Porträt aktualisiert: warmer Restaurant-Hintergrund, auf 4:5 zugeschnitten
- `85c79e4` — Platzhalter-Porträt durch echtes Foto ersetzt
- `8ce5baf` — Visuelle Elemente ergänzt: Hero-Ampersands, Ticker, Icons, Scroll-Reveals
- `52bbf3f` — Pages-Workflow auf gh-pages-Branch-Deploy umgestellt
- `54c1056` — GitHub Pages Deploy-Workflow hinzugefügt

**Aktueller Stand:** Statische Website (HTML + Tailwind CDN, kein Build-Step), Deploy via GitHub Pages (gh-pages-Branch). Repo: `reulzinger/handundherd`.

**Offen vor Livegang (laut README.md):**
1. Logo-Platzhalter in `assets/` gegen echte SVGs tauschen
2. Formspree-ID in `kontakt.html` eintragen (oder Formular entfernen, nur mailto behalten)
3. Platzhalter-Kontaktdaten (Telefon, Adresse) in `kontakt.html` sowie `[PLATZHALTER]` in `impressum.html`/`datenschutz.html` ersetzen
4. Optional: Google Fonts + Tailwind lokal statt CDN einbinden (spart Absatz in Datenschutzerklärung)

**Details siehe:** `README.md`.
