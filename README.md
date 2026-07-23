# Hand & Herd – Webdesign für Handwerker & Gastronomen

Statische Website, kein Build-Step. Alle Dateien einfach per FTP auf den Webspace
hochladen – fertig.

## Struktur

| Datei | Inhalt |
|---|---|
| `index.html` | Startseite mit Weiche Gastronomie / Handwerk |
| `gastro.html` | Landingpage Gastronomie |
| `handwerk.html` | Landingpage Handwerk |
| `kontakt.html` | Kontaktformular (Formspree-Platzhalter) + Direktkontakt |
| `impressum.html` | Impressum-Gerüst (Platzhalter ersetzen) |
| `datenschutz.html` | Datenschutz-Gerüst (Platzhalter ersetzen) |
| `assets/logo-light.svg` | Logo Navy – für helle Hintergründe (Header) |
| `assets/logo-dark.svg` | Logo Off-White – für Navy-Hintergründe (Footer) |
| `assets/favicon.svg` | Favicon: Terracotta-Ampersand auf Navy |

## Vor dem Livegang

1. **Logos tauschen:** Die drei SVGs in `assets/` gegen die echten Dateien ersetzen –
   gleiche Dateinamen, sonst ist nichts zu ändern.
2. **Formular:** In `kontakt.html` die Formspree-ID eintragen (`IHRE-FORM-ID` in der
   `action`-URL) – oder das Formular entfernen und nur den mailto-Link nutzen.
3. **Kontaktdaten:** Platzhalter-Telefonnummer und -Adresse in `kontakt.html` sowie
   alle `[PLATZHALTER]` in `impressum.html` und `datenschutz.html` ersetzen.
4. **Optional (empfohlen):** Google Fonts und Tailwind lokal einbinden statt per CDN –
   dann entfällt der entsprechende Abschnitt in der Datenschutzerklärung.

## Corporate Design

- Navy `#1E3A5F` · Terracotta `#C4622D` · Off-White `#F5F2ED`
- Überschriften/Navigation: Montserrat, Versalien, gesperrt
- Fließtext: Source Sans 3
