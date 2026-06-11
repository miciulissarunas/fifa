#!/usr/bin/env python3
"""
Paima FIFA Pasaulio cempionato 2026 siandienos ir rytdienos rungtynes
is football-data.org (v4) ir surašo i assets/wc/matches.json tokiu
formatu, kokio tikisi generatoriaus puslapis:

    [ { "left": "<teamId>", "right": "<teamId>", "datetime": "YYYY-MM-DDTHH:MM" }, ... ]

- left/right = komandu id is puslapio TEAMS saraso
- datetime  = vietinis (TZ_NAME) laikas be zonos zymes

Reikia API rakto (nemokamas football-data.org). Skriptas ji ima is
FOOTBALL_DATA_TOKEN arba (jei to nera) is APISPORTS_KEY - tad gali tiesiog
pakeisti esamo secret'o APISPORTS_KEY REIKSME i football-data.org rakta,
ir workflow keisti nereikes.

Laiko zona: TZ_NAME (numatyta Europe/Vilnius - Lietuvos auditorijai).
"""

import os
import re
import sys
import json
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

# ---- Konfiguracija -------------------------------------------------
API_KEY  = (os.environ.get("FOOTBALL_DATA_TOKEN")
            or os.environ.get("APISPORTS_KEY") or "").strip()
TZ_NAME  = os.environ.get("TZ_NAME", "Europe/Vilnius").strip()
COMP     = os.environ.get("COMP_CODE", "WC")  # football-data Pasaulio cempionato kodas
OUT_PATH = os.environ.get("OUT_PATH", "assets/wc/matches.json")
BASE_URL = "https://api.football-data.org/v4/competitions/{comp}/matches"

# ---- Komandu pavadinimu -> id atvaizdis ----------------------------
ALIASES = {
    "algeria":      ["Algeria"],
    "england":      ["England"],
    "argentina":    ["Argentina"],
    "australia":    ["Australia"],
    "austria":      ["Austria"],
    "belgium":      ["Belgium"],
    "bolivia":      ["Bolivia"],
    "brazil":       ["Brazil"],
    "denmark":      ["Denmark"],
    "ivory-coast":  ["Ivory Coast", "Cote d'Ivoire", "Cote d`Ivoire"],
    "egypt":        ["Egypt"],
    "ecuador":      ["Ecuador"],
    "ghana":        ["Ghana"],
    "iran":         ["Iran", "Iran Islamic Republic", "IR Iran"],
    "iraq":         ["Iraq"],
    "spain":        ["Spain"],
    "italy":        ["Italy"],
    "usa":          ["USA", "United States", "United States of America"],
    "jamaica":      ["Jamaica"],
    "japan":        ["Japan"],
    "cameroon":     ["Cameroon"],
    "canada":       ["Canada"],
    "qatar":        ["Qatar"],
    "colombia":     ["Colombia"],
    "dr-congo":     ["DR Congo", "Congo DR", "Democratic Republic of Congo", "Congo Democratic Republic"],
    "costa-rica":   ["Costa Rica"],
    "croatia":      ["Croatia"],
    "morocco":      ["Morocco"],
    "mexico":       ["Mexico"],
    "new-zealand":  ["New Zealand"],
    "nigeria":      ["Nigeria"],
    "norway":       ["Norway"],
    "netherlands":  ["Netherlands", "Holland"],
    "panama":       ["Panama"],
    "paraguay":     ["Paraguay"],
    "south-korea":  ["South Korea", "Korea Republic", "Republic of Korea", "Korea"],
    "portugal":     ["Portugal"],
    "france":       ["France"],
    "saudi-arabia": ["Saudi Arabia"],
    "senegal":      ["Senegal"],
    "serbia":       ["Serbia"],
    "switzerland":  ["Switzerland"],
    "tunisia":      ["Tunisia"],
    "turkiye":      ["Turkiye", "Turkey"],
    "ukraine":      ["Ukraine"],
    "uruguay":      ["Uruguay"],
    "uzbekistan":   ["Uzbekistan"],
    "germany":      ["Germany"],
    "bosnia-herzegovina": ["Bosnia and Herzegovina", "Bosnia & Herzegovina", "Bosnia-Herzegovina", "Bosnia"],
    "cape-verde":   ["Cape Verde", "Cabo Verde", "Cape Verde Islands"],
    "curacao":      ["Curacao", "Curaçao"],
    "czechia":      ["Czechia", "Czech Republic"],
    "haiti":        ["Haiti"],
    "jordan":       ["Jordan"],
    "scotland":     ["Scotland"],
    "south-africa": ["South Africa"],
    "sweden":       ["Sweden"],
}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s.lower())


NAME_TO_ID = {}
for team_id, names in ALIASES.items():
    for n in names:
        NAME_TO_ID[norm(n)] = team_id


def map_team(team):
    if not team:
        return None
    for key in ("name", "shortName", "tla"):
        val = team.get(key)
        if val:
            tid = NAME_TO_ID.get(norm(val))
            if tid:
                return tid
    return None


def fetch_matches(date_from, date_to):
    headers = {"X-Auth-Token": API_KEY}
    url = BASE_URL.format(comp=COMP)
    params = {"dateFrom": date_from, "dateTo": date_to}
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=25)
            if r.status_code == 200:
                return r.json().get("matches", []) or []
            print("  HTTP " + str(r.status_code) + ": " + r.text[:200], file=sys.stderr)
            if r.status_code in (429, 403):
                time.sleep(6)
        except Exception as e:
            print("  Uzklausos klaida: " + str(e), file=sys.stderr)
        time.sleep(2)
    return []


def main():
    if not API_KEY:
        print("KLAIDA: truksta API rakto (FOOTBALL_DATA_TOKEN arba APISPORTS_KEY).", file=sys.stderr)
        sys.exit(1)

    tz = ZoneInfo(TZ_NAME)
    now = datetime.now(tz)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    date_from = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_to   = (tomorrow + timedelta(days=1)).strftime("%Y-%m-%d")

    matches = fetch_matches(date_from, date_to)
    print("API grazino " + str(len(matches)) + " rungtyniu lange " + date_from + ".." + date_to)

    out = []
    unmapped = set()

    for m in matches:
        iso = m.get("utcDate")
        if not iso:
            continue
        try:
            dt_utc = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        dt_local = dt_utc.astimezone(tz)
        if dt_local.date() not in (today, tomorrow):
            continue

        home = m.get("homeTeam") or {}
        away = m.get("awayTeam") or {}
        left = map_team(home)
        right = map_team(away)
        if home.get("name") and not left:
            unmapped.add(home.get("name"))
        if away.get("name") and not right:
            unmapped.add(away.get("name"))
        if not (left and right):
            continue

        out.append({
            "left": left,
            "right": right,
            "datetime": dt_local.strftime("%Y-%m-%dT%H:%M"),
        })

    out.sort(key=lambda x: (x["datetime"], x["left"], x["right"]))

    print("Siandien (" + str(today) + ") ir rytoj (" + str(tomorrow) + "): atrinkta " + str(len(out)) + " rungtyniu")
    if unmapped:
        print("ISPEJIMAS: neatpazintos komandos (praleistos): " + ", ".join(sorted(unmapped)), file=sys.stderr)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Irasyta " + str(len(out)) + " rungtyniu -> " + OUT_PATH)


if __name__ == "__main__":
    main()
