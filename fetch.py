import requests
from datetime import date
from config import API_KEY, BASE_URL
from db import get_conn, init_db

HEADERS = {"x-apisports-key": API_KEY}

def fetch_today():
    today = date.today().isoformat()
    r = requests.get(f"{BASE_URL}/fixtures",
                     headers=HEADERS,
                     params={"date": today},
                     timeout=30)
    data = r.json()
    conn = get_conn()
    count = 0
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
        count += 1
    conn.commit()
    conn.close()
    print(f"Danas ({today}) ukupno utakmica: {count}")

if __name__ == "__main__":
    init_db()
    fetch_today()