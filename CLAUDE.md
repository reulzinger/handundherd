# Hand & Herd — Projektdokumentation für Claude

## Wichtiger Hinweis für neue Sessions
**IMMER zuerst `SESSION_LOG.md` lesen** — enthält den Stand der letzten Session für nahtlosen Wiedereinstieg. Am Ende der Session neuen Eintrag oben ergänzen (was gemacht, aktueller Stand, nächste Schritte).

## Was ist Hand & Herd?
Webdesign-Website für Handwerker & Gastronomen. Statische Website, kein Build-Step — Dateien direkt per FTP hochladen. Deploy aktuell auch via GitHub Pages (gh-pages-Branch). Repo: `reulzinger/handundherd`.

## Struktur
| Datei | Inhalt |
|---|---|
| `index.html` | Startseite mit Weiche Gastronomie/Handwerk |
| `gastro.html` | Landingpage Gastronomie |
| `handwerk.html` | Landingpage Handwerk |
| `kontakt.html` | Kontaktformular (Formspree-Platzhalter) + Direktkontakt |
| `impressum.html` / `datenschutz.html` | Rechtliche Seiten (Platzhalter-Gerüst) |
| `assets/` | Logos (light/dark), Favicon |

## Corporate Design
Navy `#1E3A5F` · Terracotta `#C4622D` · Off-White `#F5F2ED`. Überschriften/Navigation: Montserrat (Versalien, gesperrt). Fließtext: Source Sans 3.

## Offen vor Livegang
Siehe `README.md` und `SESSION_LOG.md`: Logo-Platzhalter tauschen, Formspree-ID eintragen, Platzhalter-Kontaktdaten/Impressum/Datenschutz ausfüllen.

## Lead-Scraper (`leadgen/`)
Python-Tool zur Akquise: findet Handwerker/Restaurants im Rhein-Main-Raum über einen lokalen OpenStreetMap-Index (nicht die überlastete Live-Overpass-API) und markiert, welche keine oder eine veraltete Website haben. Details: `leadgen/README.md`, Verlauf: `SESSION_LOG.md`.
