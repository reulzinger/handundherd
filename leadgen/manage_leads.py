#!/usr/bin/env python3
"""
Verwaltet die persistente Lead-Liste (output/leads_master.csv), die scraper.py
befüllt: Fortschritt pro Firma markieren ("Website-Entwurf gebaut?",
"Anfrage geschickt?"), Notizen setzen und nicht nützliche Treffer dauerhaft
aus der Liste entfernen.

Gelöschte Einträge landen zusätzlich in output/deleted_ids.txt — dadurch
tauchen sie bei künftigen scraper.py-Läufen nicht wieder auf.

Nutzung:
    python3 manage_leads.py list
    python3 manage_leads.py list --offen
    python3 manage_leads.py mark "Pizzeria San Marco" --entwurf
    python3 manage_leads.py mark "Pizzeria San Marco" --anfrage
    python3 manage_leads.py mark "Pizzeria San Marco" --anfrage false
    python3 manage_leads.py note "Pizzeria San Marco" "Chef bevorzugt Anruf ab 15 Uhr"
    python3 manage_leads.py delete "Pizzeria San Marco"

Ein Name reicht als Teilstring (Groß-/Kleinschreibung egal). Bei mehreren
Treffern wird nichts geändert, sondern die Kandidaten mit ihrer osm_id
angezeigt — dann per osm_id gezielt ansprechen.
"""

import argparse
import csv
import sys
from pathlib import Path

FIELDNAMES = [
    "name", "category", "score", "label",
    "entwurf_gebaut", "anfrage_geschickt", "notiz",
    "address", "phone", "website", "signals", "osm_id", "hinzugefuegt_am",
]

DEFAULT_MASTER = Path("output/leads_master.csv")
DEFAULT_DELETED = Path("output/deleted_ids.txt")


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Keine Lead-Liste gefunden unter {path}. Erst scraper.py laufen lassen.")
        sys.exit(1)
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save_rows(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def find_matches(rows: list[dict], query: str) -> list[dict]:
    query = query.strip()
    exact_id = [r for r in rows if r["osm_id"] == query]
    if exact_id:
        return exact_id
    q = query.lower()
    return [r for r in rows if q in r["name"].lower()]


def resolve_single(rows: list[dict], query: str) -> dict:
    matches = find_matches(rows, query)
    if not matches:
        print(f"Kein Treffer für '{query}'.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"Mehrere Treffer für '{query}', bitte genauer angeben oder osm_id nutzen:")
        for m in matches:
            print(f"  {m['name']}  id={m['osm_id']}")
        sys.exit(1)
    return matches[0]


def cmd_list(args):
    rows = load_rows(args.master)
    if args.offen:
        rows = [r for r in rows if r.get("anfrage_geschickt", "").lower() != "true"]
    rows.sort(key=lambda r: float(r["score"] or 0), reverse=True)
    for r in rows:
        flags = []
        if r.get("entwurf_gebaut", "").lower() == "true":
            flags.append("Entwurf✓")
        if r.get("anfrage_geschickt", "").lower() == "true":
            flags.append("Anfrage✓")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        website = r["website"] or "keine Website"
        print(f"{r['score']:>3} {r['label']:25s} {r['name']}{flag_str}  ({website})  id={r['osm_id']}")
    print(f"\n{len(rows)} Einträge.")


def cmd_mark(args):
    rows = load_rows(args.master)
    row = resolve_single(rows, args.query)
    value = "true" if args.value.lower() in ("true", "1", "ja", "yes") else "false"
    row[args.field] = value
    save_rows(args.master, rows)
    print(f"{row['name']}: {args.field} = {value}")


def cmd_note(args):
    rows = load_rows(args.master)
    row = resolve_single(rows, args.query)
    row["notiz"] = args.text
    save_rows(args.master, rows)
    print(f"{row['name']}: Notiz gespeichert.")


def cmd_delete(args):
    rows = load_rows(args.master)
    row = resolve_single(rows, args.query)
    rows = [r for r in rows if r["osm_id"] != row["osm_id"]]
    save_rows(args.master, rows)
    args.deleted.parent.mkdir(parents=True, exist_ok=True)
    with open(args.deleted, "a", encoding="utf-8") as f:
        f.write(row["osm_id"] + "\n")
    print(f"Gelöscht: {row['name']} (wird bei künftigen Scraper-Läufen nicht mehr aufgenommen).")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER, help="Pfad zur Lead-Liste")
    parser.add_argument("--deleted", type=Path, default=DEFAULT_DELETED, help="Pfad zur Ausschluss-Liste (gelöschte IDs)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Lead-Liste anzeigen")
    p_list.add_argument("--offen", action="store_true", help="Nur Einträge ohne 'Anfrage geschickt'")
    p_list.set_defaults(func=cmd_list)

    p_mark = sub.add_parser("mark", help="Entwurf/Anfrage-Status setzen")
    p_mark.add_argument("query", help="Firmenname (Teilstring) oder osm_id")
    group = p_mark.add_mutually_exclusive_group(required=True)
    group.add_argument("--entwurf", nargs="?", const="true", default=None, metavar="true|false", help="Website-Entwurf gebaut?")
    group.add_argument("--anfrage", nargs="?", const="true", default=None, metavar="true|false", help="Anfrage geschickt?")
    p_mark.set_defaults(func=cmd_mark)

    p_note = sub.add_parser("note", help="Notiz zu einem Eintrag setzen")
    p_note.add_argument("query")
    p_note.add_argument("text")
    p_note.set_defaults(func=cmd_note)

    p_delete = sub.add_parser("delete", help="Eintrag dauerhaft entfernen")
    p_delete.add_argument("query")
    p_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()

    if args.command == "mark":
        if args.entwurf is not None:
            args.field, args.value = "entwurf_gebaut", args.entwurf
        else:
            args.field, args.value = "anfrage_geschickt", args.anfrage

    args.func(args)


if __name__ == "__main__":
    main()
