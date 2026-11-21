import json
import re
from datetime import date

from db import get_conn
from predict import matrica, verovatnoce

MIN_KVOTA = 1.40
MAX_KVOTA = 2.20
MIN_VALUE = 1.00
MAX_GOL = 10


def preko(P, linija):
    prag = int(linija) + 1
    s = 0.0
    for x in range(MAX_GOL + 1):
        for y in range(MAX_GOL + 1):
            if x + y >= prag:
                s += P[x][y]
    return s


def najbolje_kvote(conn, fid):
    redovi = conn.execute("""
        SELECT bet, value, MAX(kvota) AS kvota
        FROM odds WHERE fixture_id=? GROUP BY bet, value
    """, (fid,)).fetchall()
    return {(r["bet"], r["value"]): r["kvota"] for r in redovi}


def main():
    with open("model.json", encoding="utf-8") as f:
        model = json.load(f)

    conn = get_conn()
    utakmice = conn.execute("""
        SELECT id, datum, liga, domacin, gost
        FROM fixtures WHERE odigrano = 0 ORDER BY datum
    """).fetchall()

    tiketi = []
    novi = 0
    for u in utakmice:
        if u["domacin"] not in model["timovi"] or u["gost"] not in model["timovi"]:
            continue
        P = matrica(model, u["domacin"], u["gost"])
        v = verovatnoce(P)
        kvote = najbolje_kvote(conn, u["id"])

        prob = {
            ("Match Winner", "Home"): ("1", v["1"]),
            ("Match Winner", "Draw"): ("X", v["X"]),
            ("Match Winner", "Away"): ("2", v["2"]),
            ("Double Chance", "Home/Draw"): ("1X", v["1X"]),
            ("Double Chance", "Draw/Away"): ("X2", v["X2"]),
            ("Double Chance", "Home/Away"): ("12", v["12"]),
            ("Both Teams To Score", "Yes"): ("BTTS", v["btts"]),
            ("Both Teams To Score", "No"): ("BTTS-N", v["nbtts"]),
        }
        for (bet, value_s), kvota in kvote.items():
            if bet == "Over/Under":
                m = re.match(r"(Over|Under) (\d+\.\d)", value_s)
                if not m:
                    continue
                smer, linija = m.group(1), m.group(2)
                p_over = preko(P, linija)
                p = p_over if smer == "Over" else 1 - p_over
                oznaka = f"{smer[0]}{linija}"
            else:
                if (bet, value_s) not in prob:
                    continue
                oznaka, p = prob[(bet, value_s)]

            value = p * kvota
            if MIN_KVOTA <= kvota <= MAX_KVOTA and value >= MIN_VALUE:
                ime = f"{u['domacin']} - {u['gost']}"
                tiketi.append((value, ime, oznaka, kvota, p))
                cur = conn.execute("""
                    INSERT OR IGNORE INTO tips
                    (fixture_id, utakmica, tip, kvota, verovatnoca, value, datum)
                    VALUES (?,?,?,?,?,?,?)
                """, (u["id"], ime, oznaka, kvota, p, value,
                      date.today().isoformat()))
                novi += cur.rowcount

    conn.commit()
    conn.close()

    tiketi.sort(reverse=True)
    print(f"VALUE TIKETI ZA DANAS ({len(tiketi)}):")
    print(f"{'Utakmica':45s} {'Tip':>7s} {'Kvota':>6s} {'Model':>6s} {'Value':>6s}")
    for value, ime, oznaka, kvota, p in tiketi:
        print(f"{ime:45s} {oznaka:>7s} {kvota:6.2f} {p*100:5.0f}% {value:6.2f}")
    print(f"\nNovo zapamceno u bazu: {novi} tiketa")
    if not tiketi:
        print("Nema tiketa koji zadovoljavaju uslove.")


if __name__ == "__main__":
    main()