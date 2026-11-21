import requests
from datetime import date
from config import API_KEY, BASE_URL
from db import get_conn, init_db

HEADERS = {"x-apisports-key": API_KEY}

ZANIMAJU_BETOVI = {
    "Match Winner",
    "Double Chance",
    "Both Teams To Score",
    "Over/Under",
}


def fetch_odds():
    today = date.today().isoformat()
    conn = get_conn()
    ukupno = 0
    page = 1
    while True:
        r = requests.get(f"{BASE_URL}/odds",
                         headers=HEADERS,
                         params={"date": today, "page": page},
                         timeout=30)
        data = r.json()
        if data.get("errors"):
            print("GRESKA:", data["errors"])
            break
        mecevi = data.get("response", [])
        if not mecevi:
            break
        for m in mecevi:
            fid = m["fixture"]["id"]
            postoji = conn.execute(
                "SELECT 1 FROM fixtures WHERE id=?", (fid,)).fetchone()
            if not postoji:
                continue
            for bm in m.get("bookmakers", []):
                for bet in bm.get("bets", []):
                    if bet.get("name") not in ZANIMAJU_BETOVI:
                        continue
                    for v in bet.get("values", []):
                        conn.execute("""
                            INSERT INTO odds (fixture_id, bet, value, kvota, bookmaker)
                            VALUES (?,?,?,?,?)
                            ON CONFLICT(fixture_id, bet, value)
                            DO UPDATE SET kvota=excluded.kvota,
                                          bookmaker=excluded.bookmaker
                            WHERE excluded.kvota > odds.kvota
                        """, (fid, bet["name"], v["value"],
                              float(v["odd"]), bm["id"]))
                        ukupno += 1
        conn.commit()
        print(f"Strana {page} obradjena")
        paging = data.get("paging", {})
        if page >= paging.get("total", 1):
            break
        page += 1
    conn.close()
    print(f"Ukupno upisano/azurirano kvota: {ukupno}")


if __name__ == "__main__":
    init_db()
    fetch_odds()