import json
import math
from datetime import datetime

import numpy as np
from scipy.optimize import minimize

from db import get_conn

XI = 0.0018          # koliko brzo "zaboravljamo" stare utakmice
REG = 0.1            # blaga kazna da model ne pretjera
MIN_UTAKMICA = 20    # tim mora imati barem 20 utakmica da udjie u trening


def ucitaj_utakmice():
    conn = get_conn()
    redovi = conn.execute("""
        SELECT domacin, gost, golovi_domacin, golovi_gost, datum
        FROM fixtures
        WHERE odigrano = 1
          AND golovi_domacin IS NOT NULL
          AND golovi_gost IS NOT NULL
    """).fetchall()
    conn.close()
    sve = [dict(r) for r in redovi]
    IZMJENE = {"Bayern München": "Bayern Munich"}
    for u in sve:
        u["domacin"] = IZMJENE.get(u["domacin"], u["domacin"])
        u["gost"] = IZMJENE.get(u["gost"], u["gost"])
    # zadrzi samo timove s dovoljno utakmica (izbaci jednokratne timove)
    broj = {}
    for u in sve:
        broj[u["domacin"]] = broj.get(u["domacin"], 0) + 1
        broj[u["gost"]] = broj.get(u["gost"], 0) + 1
    return [u for u in sve
            if broj[u["domacin"]] >= MIN_UTAKMICA and broj[u["gost"]] >= MIN_UTAKMICA]


def tezina(datum_str, danas):
    d = datetime.fromisoformat(datum_str.replace("Z", "+00:00"))
    razlika = (danas - d.replace(tzinfo=None)).days
    return math.exp(-XI * max(razlika, 0))


def tau_i_izvodi(x, y, lam, mu, rho):
    """Dixon-Coles korekcija za niske rezultate (0:0, 1:0, 0:1, 1:1)."""
    if x == 0 and y == 0:
        t = 1 - lam * mu * rho
        return t, -mu * rho / t, -lam * rho / t
    if x == 0 and y == 1:
        t = 1 + lam * rho
        return t, rho / t, 0.0
    if x == 1 and y == 0:
        t = 1 + mu * rho
        return t, 0.0, rho / t
    if x == 1 and y == 1:
        t = 1 - rho
        return t, 0.0, 0.0
    return 1.0, 0.0, 0.0


def f_i_grad(parametri, utakmice, timovi, tezine, n):
    napad = parametri[:n]
    odbrana = parametri[n:2 * n]
    domaci = parametri[2 * n]
    rho = parametri[2 * n + 1]

    f = REG * (napad.sum() ** 2 + odbrana.sum() ** 2)
    g_napad = np.full(n, 2 * REG * napad.sum())
    g_odbrana = np.full(n, 2 * REG * odbrana.sum())
    g_domaci = 0.0
    g_rho = 0.0

    for k, u in enumerate(utakmice):
        i = timovi[u["domacin"]]
        j = timovi[u["gost"]]
        x = u["golovi_domacin"]
        y = u["golovi_gost"]
        lam = math.exp(napad[i] + odbrana[j] + domaci)
        mu = math.exp(napad[j] + odbrana[i])

        t, dt_dl, dt_dm = tau_i_izvodi(x, y, lam, mu, rho)
        p = t * math.exp(-lam) * lam ** x / math.factorial(x) \
              * math.exp(-mu) * mu ** y / math.factorial(y)
        w = tezine[k]

        f -= w * math.log(max(p, 1e-12))

        # log-izvodi po A=log(lam) i B=log(mu)
        gA = x - lam + lam * dt_dl
        gB = y - mu + mu * dt_dm

        g_napad[i] -= w * gA
        g_odbrana[j] -= w * gA
        g_domaci -= w * gA
        g_napad[j] -= w * gB
        g_odbrana[i] -= w * gB

        # d(log p)/d rho
        if x == 0 and y == 0:
            dlog = -lam * mu / t
        elif x == 0 and y == 1:
            dlog = lam / t
        elif x == 1 and y == 0:
            dlog = mu / t
        elif x == 1 and y == 1:
            dlog = -1.0 / t
        else:
            dlog = 0.0
        g_rho -= w * dlog

    grad = np.concatenate([g_napad, g_odbrana, [g_domaci], [g_rho]])
    return f, grad


def treniraj():
    utakmice = ucitaj_utakmice()
    print(f"Ucitano {len(utakmice)} odigranih utakmica (poslije filtera)")

    imena = sorted({u["domacin"] for u in utakmice} | {u["gost"] for u in utakmice})
    timovi = {ime: i for i, ime in enumerate(imena)}
    n = len(imena)
    print(f"Pronadjeno {n} timova")

    danas = datetime.now()
    tezine = [tezina(u["datum"], danas) for u in utakmice]

    start = np.zeros(2 * n + 2)
    granice = [(None, None)] * (2 * n) + [(None, None), (-1.0, 1.0)]

    res = minimize(
        f_i_grad, start,
        args=(utakmice, timovi, tezine, n),
        method="L-BFGS-B",
        jac=True,
        bounds=granice,
        options={"maxiter": 500},
    )
    print(f"Optimizacija zavrsena: uspjesno={res.success}, "
          f"neg-log-verovatnoce={res.fun:.1f}")

    p = res.x
    model = {
        "timovi": timovi,
        "napad": p[:n].tolist(),
        "odbrana": p[n:2 * n].tolist(),
        "domaci": float(p[2 * n]),
        "rho": float(p[2 * n + 1]),
    }
    with open("model.json", "w", encoding="utf-8") as fajl:
        json.dump(model, fajl, ensure_ascii=False, indent=1)

    print(f"Faktor domaceg terena: {math.exp(p[2 * n]):.2f}x vise golova")
    print("\nNajjaci napadi (top 10):")
    for idx in np.argsort(p[:n])[::-1][:10]:
        print(f"  {imena[idx]:25s} {p[idx]:+.3f}")
    print("\nNajbolje odbrane (top 5):")
    for idx in np.argsort(p[n:2 * n])[:5]:
        print(f"  {imena[idx]:25s} {p[n + idx]:+.3f}")


if __name__ == "__main__":
    treniraj()