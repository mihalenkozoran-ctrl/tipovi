import requests
from datetime import date
from config import ODDS_KEY
from db import get_conn, init_db

SPORTS = [
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_seria_a",
    "soccer_germany_bundesliga", "soccer_france_ligue_one",
    "soccer_netherlands_eredivisie", "soccer_portugal_primeira_liga",
    "soccer_belgium_first_div", "soccer_turkey_super_league",
]


def norm(s):
    for x in (" fc", " cf", " afc", " united", "."):
        s = s.lower().replace(x, "")
    return " ".join(s.split())


def fetch():
    today = date.today().isoformat()
    conn = get_conn()
    utakmice = conn.execute(
        "SELECT id, domacin, gost FROM fixtures WHERE odigrano=0 AND substr(datum,1,10)=?",
        (today,)).fetchall()
    mapa = {(norm(u["domacin"]), norm(u["gost"])): u["id"] for u in utakmice}
    ukupno = 0
    for sport in SPORTS:
        r = requests.get(
            f"https://api.the-odds-api.com/v4/sports/{sport}/odds/",
            params={"apiKey": ODDS_KEY, "regions": "eu",
                    "markets": "h2h,totals", "oddsFormat": "decimal"},
            timeout=30)
        data = r.json()
        if isinstance(data, dict):
            print(sport, "GRESKA:", data.get("error") or data)
            continue
        for ev in data:
            fid = mapa.get((norm(ev["home_team"]), norm(ev["away_team"])))
            if not fid:
                print("Nema para:", ev["home_team"], "-", ev["away_team"])
                continue
            for bm in ev.get("bookmakers", []):
                for m in bm.get("markets", []):
                    bet = "Match Winner" if m["key"] == "h2h" else "Over/Under"
                    for o in m.get("outcomes", []):
                        if m["key"] == "h2h":
                            if o["name"] == ev["home_team"]:
                                value = "Home"
                            elif o["name"] == ev["away_team"]:
                                value = "Away"
                            else:
                                value = "Draw"
                        else:
                            p = o.get("point")
                            if p is None:
                                continue
                            value = f'{o["name"]} {p}'
                        conn.execute("""
                            INSERT INTO odds (fixture_id, bet, value, kvota, bookmaker)
                            VALUES (?,?,?,?,?)
                            ON CONFLICT(fixture_id, bet, value)
                            DO UPDATE SET kvota=excluded.kvota,
                                          bookmaker=excluded.bookmaker
                            WHERE excluded.kvota > odds.kvota
                        """, (fid, bet, value, float(o["price"]), bm["key"][:12]))
                        ukupno += 1
        conn.commit()
        print(sport, "gotovo")
    conn.close()
    print("Ukupno upisano:", ukupno)


if __name__ == "__main__":
    init_db()
    fetch()
