import json
import re
from datetime import date

from db import get_conn
from predict import matrica, verovatnoce

MIN_KVOTA = 1.40
MAX_KVOTA = 2.20
MIN_VALUE = 1.00      # prag za ulazak u knjigu
TOP_VALUE = 1.09      # prag za vrhunski razred (TOP)
MAX_GOL = 10


def preko(P, linija):
    prag = int(float(linija)) + 1
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


def trziste(oznaka):
    if oznaka in ("1", "X", "2"):
        return "MW"
    if oznaka in ("1X", "X2", "12"):
        return "DC"
    if oznaka.startswith("O") or oznaka.startswith("U"):
        return "OU"
    return "BTTS"


def main():
    with open("model.json", encoding="utf-8") as f:
        model = json.load(f)

    conn = get_conn()
    utakmice = conn.execute("""
        SELECT id, datum, liga, domacin, gost
        FROM fixtures WHERE odigrano = 0 ORDER BY datum
    """).fetchall()

    kandidati = []
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
                m = re.match(r"(Over|Under) (\d+\.[05])", value_s)
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
                kandidati.append((value, f"{u['domacin']} - {u['gost']}",
                                  oznaka, kvota, p, u["id"]))

    najbolji = {}
    for k in kandidati:
        key = (k[5], trziste(k[2]))
        if key not in najbolji or k[0] > najbolji[key][0]:
            najbolji[key] = k
    tiketi = sorted(najbolji.values(), reverse=True)

    novi = 0
    for value, ime, oznaka, kvota, p, fid in tiketi:
        cur = conn.execute("""
            INSERT OR IGNORE INTO tips
            (fixture_id, utakmica, tip, kvota, verovatnoca, value, datum)
            VALUES (?,?,?,?,?,?,?)
        """, (fid, ime, oznaka, kvota, p, value, date.today().isoformat()))
        novi += cur.rowcount
    conn.commit()
    conn.close()

    top = [t for t in tiketi if t[0] >= TOP_VALUE]
    ostalo = [t for t in tiketi if t[0] < TOP_VALUE]
    print(f"TOP ({len(top)}):")
    for t in top:
        print(f"  {t[1]:45s} {t[2]:>7s} {t[3]:.2f} {t[4]*100:4.0f}% {t[0]:.2f}")
    print(f"OSTALI ({len(ostalo)}):")
    for t in ostalo:
        print(f"  {t[1]:45s} {t[2]:>7s} {t[3]:.2f} {t[4]*100:4.0f}% {t[0]:.2f}")
    print(f"\nNovo zapamceno: {novi} | ukupno za danas: {len(tiketi)}")


if __name__ == "__main__":
    main()
