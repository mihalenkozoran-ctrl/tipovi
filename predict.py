import json
import math

from db import get_conn

MAX_GOL = 10


def matrica(model, domacin, gost):
    i = model["timovi"][domacin]
    j = model["timovi"][gost]
    lam = math.exp(model["napad"][i] + model["odbrana"][j] + model["domaci"])
    mu = math.exp(model["napad"][j] + model["odbrana"][i])
    rho = model["rho"]

    P = [[0.0] * (MAX_GOL + 1) for _ in range(MAX_GOL + 1)]
    for x in range(MAX_GOL + 1):
        for y in range(MAX_GOL + 1):
            p = (math.exp(-lam) * lam ** x / math.factorial(x)) * \
                (math.exp(-mu) * mu ** y / math.factorial(y))
            if x == 0 and y == 0:
                p *= 1 - lam * mu * rho
            elif x == 0 and y == 1:
                p *= 1 + lam * rho
            elif x == 1 and y == 0:
                p *= 1 + mu * rho
            elif x == 1 and y == 1:
                p *= 1 - rho
            P[x][y] = p
    return P


def verovatnoce(P):
    p1 = pX = p2 = 0.0
    v15 = v25 = v35 = 0.0   # vise od 1.5 / 2.5 / 3.5 golova
    btts = 0.0
    for x in range(MAX_GOL + 1):
        for y in range(MAX_GOL + 1):
            p = P[x][y]
            if x > y:
                p1 += p
            elif x == y:
                pX += p
            else:
                p2 += p
            if x + y >= 2:
                v15 += p
            if x + y >= 3:
                v25 += p
            if x + y >= 4:
                v35 += p
            if x >= 1 and y >= 1:
                btts += p
    return {"1": p1, "X": pX, "2": p2,
            "1X": p1 + pX, "X2": pX + p2, "12": p1 + p2,
            "v15": v15, "v25": v25, "v35": v35,
            "btts": btts, "nbtts": 1 - btts}


def prognoziraj():
    with open("model.json", encoding="utf-8") as f:
        model = json.load(f)

    conn = get_conn()
    utakmice = conn.execute("""
        SELECT id, datum, liga, domacin, gost
        FROM fixtures
        WHERE odigrano = 0
        ORDER BY datum
    """).fetchall()
    conn.close()

    print(f"Neodigranih utakmica u bazi: {len(utakmice)}")
    print()
    print(f"{'Utakmica':38s} {'1':>4s} {'X':>4s} {'2':>4s} {'1X':>4s} {'X2':>4s} {'12':>4s} "
          f"{'V1.5':>5s} {'V2.5':>5s} {'V3.5':>5s} {'BTTS':>5s}")
    br = 0
    for u in utakmice:
        if u["domacin"] not in model["timovi"] or u["gost"] not in model["timovi"]:
            continue
        v = verovatnoce(matrica(model, u["domacin"], u["gost"]))
        br += 1
        ime = f'{u["domacin"]} - {u["gost"]}'
        print(f"{ime:38s} {v['1']*100:3.0f}% {v['X']*100:3.0f}% {v['2']*100:3.0f}% "
              f"{v['1X']*100:3.0f}% {v['X2']*100:3.0f}% {v['12']*100:3.0f}% "
              f"{v['v15']*100:4.0f}% {v['v25']*100:4.0f}% {v['v35']*100:4.0f}% "
              f"{v['btts']*100:4.0f}%")
    print(f"\nUkupno prognoza: {br}")


if __name__ == "__main__":
    prognoziraj()