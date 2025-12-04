import math
import sqlite3

DB = "league.db"

#region PLAYER FUNCTIONS

def add_player(name, full_name=None):
    full = full_name if full_name else name
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT INTO players (name, full_name) VALUES (?, ?)",
            (name, full)
        )

def get_players():
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, rating FROM players ORDER BY name")
        return cur.fetchall()
#endregion

#region MATCH + TEAM CREATION

def create_match(date):
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO matches (date) VALUES (?)", (date,))
        return cur.lastrowid

def create_team(match_id, is_winner):
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO teams (match_id, is_winner) VALUES (?, ?)",
            (match_id, is_winner)
        )
        return cur.lastrowid

def add_player_to_team(team_id, player_id):
    with sqlite3.connect(DB) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO team_players (team_id, player_id) VALUES (?, ?)",
            (team_id, player_id)
        )

def set_match_result(match_id, winning_team_id):
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        # mark winner
        cur.execute("UPDATE teams SET is_winner = 1 WHERE id = ?", (winning_team_id,))
        # mark loser
        cur.execute("UPDATE teams SET is_winner = 0 WHERE match_id = ? AND id != ?", (match_id, winning_team_id))

        # get player IDs
        winners = [pid for (pid,) in cur.execute(
            "SELECT player_id FROM team_players WHERE team_id = ?", (winning_team_id,)
        )]
        losers = [pid for (pid,) in cur.execute(
            "SELECT player_id FROM team_players WHERE team_id != ? AND team_id IN (SELECT id FROM teams WHERE match_id = ?)",
            (winning_team_id, match_id)
        )]

        update_glicko2(winners, losers, conn, cur)

def get_team_players(team_id):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
        SELECT players.id, players.name
        FROM players
        JOIN team_players ON players.id = team_players.player_id
        WHERE team_players.team_id = ?
        ORDER BY players.name
    """, (team_id,))

    result = c.fetchall()
    conn.close()
    return result

def set_team_players(team_id, player_ids):
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # delete old
    c.execute("DELETE FROM team_players WHERE team_id = ?", (team_id,))

    # insert new
    for pid in player_ids:
        c.execute(
            "INSERT INTO team_players (team_id, player_id) VALUES (?, ?)",
            (team_id, pid)
        )

    conn.commit()
    conn.close()

#endregion

#region SIMPLE ELO

TAU = 0.5  # Glicko-2 recommended constant


def g(phi):
    return 1 / math.sqrt(1 + 3 * phi * phi / math.pi**2)


def E(mu, mu_j, phi_j):
    return 1 / (1 + math.exp(-g(phi_j) * (mu - mu_j)))


def to_mu(rating):
    return (rating - 1500) / 173.7178


def to_phi(rd):
    return rd / 173.7178


def from_mu(mu):
    return mu * 173.7178 + 1500


def from_phi(phi):
    return phi * 173.7178

# Iterative function for volatility update
def _f(x, delta, phi, v, sigma, tau):
    exp_x = math.exp(x)
    num = exp_x * (delta**2 - phi**2 - v - exp_x)
    den = 2 * (phi**2 + v + exp_x)**2
    return num / den - (x - math.log(sigma**2)) / tau**2

def _update_volatility(delta, phi, sigma, v, tau=TAU):
    a = math.log(sigma**2)
    eps = 1e-6

    # Initial bounds
    A = a
    B = None
    if delta**2 > phi**2 + v:
        B = math.log(delta**2 - phi**2 - v)
    else:
        k = 1
        while _f(a - k * tau, delta, phi, v, sigma, tau) < 0:
            k += 1
        B = a - k * tau

    fA = _f(A, delta, phi, v, sigma, tau)
    fB = _f(B, delta, phi, v, sigma, tau)

    while abs(B - A) > eps:
        C = A + (A - B) * fA / (fB - fA)
        fC = _f(C, delta, phi, v, sigma, tau)
        if fC * fB < 0:
            A = B
            fA = fB
        else:
            fA = fA / 2
        B = C
        fB = fC
    return math.exp(A / 2)

def update_glicko2(winners, losers, conn=None, cur=None):
    if not winners or not losers:
        return

    close_conn = False
    if conn is None or cur is None:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        close_conn = True

    all_players = winners + losers

    # Load all relevant players
    q = f"SELECT id, rating, rd, vol FROM players WHERE id IN ({','.join(['?']*len(all_players))})"
    rows = cur.execute(q, all_players).fetchall()
    players = {pid: {'rating': r, 'rd': rd, 'vol': vol} for pid, r, rd, vol in rows}

    # Separate winners and losers
    winner_objs = [players[pid] for pid in winners]
    loser_objs = [players[pid] for pid in losers]

    # For each player, update against each opponent
    for pid, player in players.items():
        mu = to_mu(player['rating'])
        phi = to_phi(player['rd'])
        sigma = player['vol']

        opponents = []
        scores = []
        if pid in winners:
            # opponents are losers
            for opp in loser_objs:
                opponents.append((to_mu(opp['rating']), to_phi(opp['rd'])))
                scores.append(1)  # win
        else:
            # opponents are winners
            for opp in winner_objs:
                opponents.append((to_mu(opp['rating']), to_phi(opp['rd'])))
                scores.append(0)  # loss

        # Step 1: compute v
        v = 0
        for (mu_j, phi_j), score in zip(opponents, scores):
            E_ij = E(mu, mu_j, phi_j)
            v += (g(phi_j)**2) * E_ij * (1 - E_ij)
        v = 1 / v

        # Step 2: compute delta
        delta = 0
        for (mu_j, phi_j), score in zip(opponents, scores):
            delta += g(phi_j) * (score - E(mu, mu_j, phi_j))
        delta *= v

        # Step 3: update volatility
        sigma_prime = _update_volatility(delta, phi, sigma, v, TAU)

        # Step 4: update phi*
        phi_star = math.sqrt(phi**2 + sigma_prime**2)

        # Step 5: new phi
        phi_prime = 1 / math.sqrt(1 / phi_star**2 + 1 / v)

        # Step 6: new mu
        mu_prime = mu + phi_prime**2 * sum(
            g(phi_j) * (score - E(mu, mu_j, phi_j)) for (mu_j, phi_j), score in zip(opponents, scores)
        )

        # Step 7: convert back
        new_rating = from_mu(mu_prime)
        new_rd = from_phi(phi_prime)
        new_vol = sigma_prime

        # Save
        cur.execute("UPDATE players SET rating=?, rd=?, vol=? WHERE id=?", (new_rating, new_rd, new_vol, pid))

    if close_conn:
        conn.commit()
        conn.close()

#endregion