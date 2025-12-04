import sqlite3

def create_db():
    conn = sqlite3.connect("league.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        full_name TEXT NOT NULL,
        rating REAL DEFAULT 1500.0,
        rd REAL DEFAULT 350.0,
        vol REAL DEFAULT 0.06
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        is_winner BOOLEAN,
        FOREIGN KEY(match_id) REFERENCES matches(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_players (
        team_id INTEGER,
        player_id INTEGER,
        FOREIGN KEY(team_id) REFERENCES teams(id),
        FOREIGN KEY(player_id) REFERENCES players(id)
    )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_db()
