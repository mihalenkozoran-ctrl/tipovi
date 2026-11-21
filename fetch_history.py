import requests
from config import API_KEY, BASE_URL
from db import get_conn, init_db

HEADERS = {"x-apisports-key": API_KEY}

# ID-jevi liga: 39=Premier League, 140=La Liga, 135=Serie A, 78=Bundesliga, 61=Ligue 1
LIGE = [39, 140, 135, 78, 61]
SEZONE = ["2022", "2023", "2024"]

def fetch_history():
    conn = get_conn()
    ukupno = 0
    for liga in LIGE:
        for sezona in SEZONE:
            r = requests.get(f"{BASE_URL}/fixtures",
                             headers=HEADERS,
                             params={"league": liga, "season": sezona},
                             timeout=60)
            data = r.json()
            if data.get("errors"):
                print(f"LIGA {liga} SEZONA {sezona} — GREŠKA: {data['errors']}")
                continue
            n = 0
            for m in data.get("response", []):
                conn.execute("""
                    INSERT OR REPLACE INTO fixtures
                    (id, datum, liga, domacin, gost, golovi_domacin, golovi_gost, status, odigrano)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (
                    m["fixture"]["id"],
                    m["fixture"]["date"],
                    m["league"]["name"],
                    m["teams"]["home"]["name"],
                    m["teams"]["away"]["name"],
                    m["goals"]["home"],
                    m["goals"]["away"],
                    m["fixture"]["status"]["short"],
                    1 if m["fixture"]["status"]["short"] == "FT" else 0,
                ))
                n += 1
            conn.commit()
            print(f"Liga {liga}, sezona {sezona}: {n} utakmica")
            ukupno += n
    conn.close()
    print(f"UKUPNO u bazi: {ukupno} utakmica")

if __name__ == "__main__":
    init_db()
    fetch_history()