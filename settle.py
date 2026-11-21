from db import get_conn, init_db

ISHODI = {
    "1": lambda x, y: x > y,
    "X": lambda x, y: x == y,
    "2": lambda x, y: x < y,
    "1X": lambda x, y: x >= y,
    "X2": lambda x, y: x <= y,
    "12": lambda x, y: x != y,
    "BTTS": lambda x, y: x >= 1 and y >= 1,
    "BTTS-N": lambda x, y: x == 0 or y == 0,
}


def pobijedio(tip, x, y):
    if tip.startswith("O"):
        return x + y >= int(float(tip[1:])) + 1
    if tip.startswith("U"):
        return x + y <= int(float(tip[1:]))
    return ISHODI[tip](x, y)


def main():
    conn = get_conn()
    otvoreni = conn.execute(
        "SELECT * FROM tips WHERE status='OPEN'").fetchall()
    razreseno = 0
    for t in otvoreni:
        m = conn.execute(
            "SELECT golovi_domacin, golovi_gost, odigrano FROM fixtures WHERE id=?",
            (t["fixture_id"],)).fetchone()
        if not m or not m["odigrano"]:
            continue
        x, y = m["golovi_domacin"], m["golovi_gost"]
        if pobijedio(t["tip"], x, y):
            status, profit = "WON", t["kvota"] - 1
        else:
            status, profit = "LOST", -1.0
        conn.execute("UPDATE tips SET status=?, profit=? WHERE id=?",
                     (status, profit, t["id"]))
        razreseno += 1
    conn.commit()
    conn.close()
    print(f"Razreseno: {razreseno} tiketa")


if __name__ == "__main__":
    init_db()
    main()