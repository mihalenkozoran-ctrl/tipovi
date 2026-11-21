import json
import re

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from db import get_conn
from predict import matrica, verovatnoce
from tiketi import preko, najbolje_kvote

app = FastAPI()

MIN_KVOTA = 1.40
MAX_KVOTA = 2.20
MIN_VALUE = 1.00

PAGE = """<!DOCTYPE html>
<html lang="bs">
<head>
<meta charset="utf-8">
<title>Tipovi — model</title>
<style>
 body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; padding: 20px; }
 h1 { font-size: 22px; }
 h2 { font-size: 18px; margin-top: 30px; color: #4ade80; }
 table { border-collapse: collapse; width: 100%; margin-top: 12px; }
 th, td { padding: 8px 10px; text-align: center; border-bottom: 1px solid #1e293b; }
 th { background: #1e293b; font-size: 13px; }
 td.ime { text-align: left; font-weight: bold; }
 tr:hover { background: #16213b; }
 tr.tip td { background: #14532d; }
 .jac { color: #4ade80; font-weight: bold; }
 .plus { color: #4ade80; font-weight: bold; }
 .minus { color: #f87171; font-weight: bold; }
</style>
</head>
<body>
<h1>⚽ Value tiketi <span style="color:#4ade80">({broj_tiketa})</span></h1>
<table>
<tr><th>Utakmica</th><th>Tip</th><th>Kvota</th><th>Model</th><th>Value</th></tr>
{tiketi}
</table>

<h2>📊 Statistika ({zatvoreno} tiketa razreseno)</h2>
<table>
<tr><th>Tiketa</th><th>Pogodaka</th><th>Promasaja</th><th>Procenat</th><th>Profit (uniti)</th><th>ROI</th></tr>
{ukupno}
</table>
<table>
<tr><th>Tip</th><th>Tiketa</th><th>Pogodaka</th><th>Procenat</th><th>Profit</th><th>ROI</th></tr>
{po_tipu}
</table>

<h2>Sve utakmice ({broj_mec})</h2>
<table>
<tr><th>Liga</th><th>Utakmica</th><th>1</th><th>X</th><th>2</th>
<th>1X</th><th>X2</th><th>12</th><th>V1.5</th><th>V2.5</th><th>V3.5</th><th>BTTS</th></tr>
{mecevi}
</table>
</body>
</html>"""


def statistika(conn):
    uk = conn.execute("""
        SELECT COUNT(*) n,
               SUM(CASE WHEN status='WON' THEN 1 ELSE 0 END) won,
               SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) lost,
               SUM(CASE WHEN status IN ('WON','LOST') THEN profit ELSE 0 END) profit
        FROM tips
    """).fetchone()
   

def statistika(conn):
    uk = conn.execute("""
        SELECT COUNT(*) n,
               SUM(CASE WHEN status='WON' THEN 1 ELSE 0 END) won,
               SUM(CASE WHEN status='LOST' THEN 1 ELSE 0 END) lost,
               SUM(CASE WHEN status IN ('WON','LOST') THEN profit ELSE 0 END) profit
        FROM tips
    """).fetchone()
    po_tipu = conn.execute("""
        SELECT tip, COUNT(*) n,
               SUM(CASE WHEN status='WON' THEN 1 ELSE 0 END) won,
               SUM(CASE WHEN status IN ('WON','LOST') THEN profit ELSE 0 END) profit
        FROM tips WHERE status IN ('WON','LOST')
        GROUP BY tip ORDER BY profit DESC
    """).fetchall()
    return uk, po_tipu


def svi_podaci():
    with open("model.json", encoding="utf-8") as f:
        model = json.load(f)

    conn = get_conn()
    utakmice = conn.execute("""
        SELECT id, datum, liga, domacin, gost
        FROM fixtures WHERE odigrano = 0 ORDER BY datum
    """).fetchall()

    tiketi = []
    mecevi = []
    for u in utakmice:
        if u["domacin"] not in model["timovi"] or u["gost"] not in model["timovi"]:
            continue
        P = matrica(model, u["domacin"], u["gost"])
        v = verovatnoce(P)
        kvote = najbolje_kvote(conn, u["id"])
        ime = f"{u['domacin']} — {u['gost']}"

        celije = "".join(f"<td>{round(v[k] * 100)}%</td>"
                         for k in ["1", "X", "2", "1X", "X2", "12", "v15", "v25", "v35", "btts"])
        mecevi.append(f"<tr><td style='color:#94a3b8;font-size:12px'>{u['liga']}</td>"
                      f"<td class='ime'>{ime}</td>{celije}</tr>")

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
                tiketi.append((value, ime, oznaka, kvota, p))

    uk, po_tipu = statistika(conn)
    conn.close()
    tiketi.sort(reverse=True)
    return tiketi, mecevi, uk, po_tipu
@app.get("/", response_class=HTMLResponse)
def pocetna():
    tiketi, mecevi, uk, po_tipu = svi_podaci()

    redovi_t = ""
    for value, ime, oznaka, kvota, p in tiketi:
        redovi_t += (f"<tr class='tip'><td class='ime'>{ime}</td><td>{oznaka}</td>"
                     f"<td>{kvota:.2f}</td><td>{round(p*100)}%</td>"
                     f"<td class='jac'>{value:.2f}</td></tr>")
    if not redovi_t:
        redovi_t = "<tr><td colspan='5'>Danas nema tiketa.</td></tr>"

    zatvoreno = (uk["won"] or 0) + (uk["lost"] or 0)
    profit = uk["profit"] or 0
    if zatvoreno:
        procenat = uk["won"] / zatvoreno * 100
        roi = profit / zatvoreno * 100
    else:
        procenat = roi = 0
    klasa = "plus" if profit >= 0 else "minus"
    ukupno = (f"<tr><td>{zatvoreno}</td><td>{uk['won'] or 0}</td><td>{uk['lost'] or 0}</td>"
              f"<td>{procenat:.0f}%</td><td class='{klasa}'>{profit:+.1f}</td>"
              f"<td class='{klasa}'>{roi:+.1f}%</td></tr>")

    redovi_p = ""
    for r in po_tipu:
        p = r["profit"] or 0
        k = "plus" if p >= 0 else "minus"
        redovi_p += (f"<tr><td class='ime'>{r['tip']}</td><td>{r['n']}</td>"
                     f"<td>{r['won']}</td><td>{r['won']/r['n']*100:.0f}%</td>"
                     f"<td class='{k}'>{p:+.1f}</td>"
                     f"<td class='{k}'>{p/r['n']*100:+.0f}%</td></tr>")
    if not redovi_p:
        redovi_p = "<tr><td colspan='6'>Jos nema razresenih tiketa.</td></tr>"

    return (PAGE.replace("{broj_tiketa}", str(len(tiketi)))
                .replace("{tiketi}", redovi_t)
                .replace("{zatvoreno}", str(zatvoreno))
                .replace("{ukupno}", ukupno)
                .replace("{po_tipu}", redovi_p)
                .replace("{broj_mec}", str(len(mecevi)))
                .replace("{mecevi}", "".join(mecevi)))