import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tipovi.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS fixtures (
        id INTEGER PRIMARY KEY,
        datum TEXT,
        liga TEXT,
        domacin TEXT,
        gost TEXT,
        golovi_domacin INTEGER,
        golovi_gost INTEGER,
        status TEXT,
        odigrano INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS odds (
        fixture_id INTEGER,
        bet TEXT,
        value TEXT,
        kvota REAL,
        bookmaker INTEGER,
        UNIQUE(fixture_id, bet, value)
    );

    CREATE TABLE IF NOT EXISTS tips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id INTEGER,
        utakmica TEXT,
        tip TEXT,
        kvota REAL,
        verovatnoca REAL,
        value REAL,
        status TEXT DEFAULT 'OPEN',
        profit REAL,
        datum TEXT,
        UNIQUE(fixture_id, tip)
    );
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Baza kreirana/azurirana.")