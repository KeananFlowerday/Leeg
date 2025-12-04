import sqlite3
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from main import (
    add_player,
    add_player_to_team,
    create_match,
    create_team,
    get_players,
    get_team_players,
    set_match_result,
    set_team_players,
)

DB = "league.db"

root = tk.Tk()
root.title("6-a-Side League")
root.geometry("1280x960")

#region FRAME SWITCHING
def switch(frame):
    frame.tkraise()

frames = [tk.Frame(root) for _ in range(6)]
for f in frames:
    f.grid(row=0, column=0, sticky="nsew")

add_player_frame, match_frame, team_pick_frame, set_result_frame, view_matches_frame, player_rank_frame  = frames
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)
#endregion

#region PAGE 1: ADD PLAYER
tk.Label(add_player_frame, text="Add Player", font=("Arial", 16)).pack(pady=10)
entry_name = tk.Entry(add_player_frame)
entry_full_name = tk.Entry(add_player_frame)
entry_name.pack(pady=5)
entry_full_name.pack(pady=5)

def add_player_ui():
    name = entry_name.get()
    full_name = entry_full_name.get()
    if not name:
        return
    add_player(name, full_name)
    entry_name.delete(0, tk.END)
    entry_full_name.delete(0, tk.END)
    messagebox.showinfo("Done", f"Player '{name}' added.")
    refresh_players()

tk.Button(add_player_frame, text="Add", command=add_player_ui).pack(pady=10)
tk.Button(add_player_frame, text="Go to Matches", command=lambda: switch(match_frame)).pack(pady=5)
tk.Button(add_player_frame, text="View Matches", command=lambda: [refresh_view_matches(), switch(view_matches_frame)]).pack(pady=5)
tk.Button(add_player_frame, text="Set Match Result", command=lambda: [refresh_matches(), switch(set_result_frame)]).pack(pady=5)
tk.Button(add_player_frame, text="Player Rankings",
          command=lambda: [refresh_player_rankings(), switch(player_rank_frame)]).pack(pady=5)
#endregion

#region PAGE 2: CREATE MATCH
tk.Label(match_frame, text="Create Match", font=("Arial", 16)).pack(pady=10)
match_date = tk.Entry(match_frame)
match_date.insert(0, str(date.today()))
match_date.pack(pady=5)

def start_match():
    m_id = create_match(match_date.get())
    begin_team_selection(m_id)

tk.Button(match_frame, text="Next: Pick Teams", command=start_match).pack(pady=20)
tk.Button(match_frame, text="Back", command=lambda: switch(add_player_frame)).pack()
#endregion

#region PAGE 3: TEAM SELECTION
tk.Label(team_pick_frame, text="Pick Teams", font=("Arial", 16)).pack(pady=10)

players_list = ttk.Treeview(team_pick_frame, columns=("id", "name", "elo"), show="headings", height=12)
players_list.heading("id", text="ID")
players_list.heading("name", text="Name")
players_list.heading("elo", text="ELO")
players_list.pack(pady=10)

team1, team2 = [], []

def refresh_players():
    players_list.delete(*players_list.get_children())
    for pid, name, rating in get_players():
        players_list.insert("", "end", values=(pid, name, round(rating)))

refresh_players()

def add_to_team(team):
    sel = players_list.focus()
    if not sel:
        return
    pid, name, rating = players_list.item(sel)["values"]
    if pid in team1 or pid in team2:
        messagebox.showwarning("Oops", "Player already selected.")
        return
    team.append(pid)
    update_team_labels()

def update_team_labels():
    def names(team):
        if not team:
            return []
        with sqlite3.connect(DB) as conn:
            return [name for (name,) in conn.execute(
                "SELECT name FROM players WHERE id IN (%s)" % ",".join("?"*len(team)), team
            )]
    lbl_team1.config(text="Team 1: " + ", ".join(names(team1)))
    lbl_team2.config(text="Team 2: " + ", ".join(names(team2)))

lbl_team1 = tk.Label(team_pick_frame, text="Team 1: []")
lbl_team1.pack()
lbl_team2 = tk.Label(team_pick_frame, text="Team 2: []")
lbl_team2.pack()

tk.Button(team_pick_frame, text="Add to Team 1", command=lambda: add_to_team(team1)).pack(pady=5)
tk.Button(team_pick_frame, text="Add to Team 2", command=lambda: add_to_team(team2)).pack(pady=5)

def finalize_teams():
    team1_id = create_team(current_match_id, None)
    team2_id = create_team(current_match_id, None)
    for p in team1:
        add_player_to_team(team1_id, p)
    for p in team2:
        add_player_to_team(team2_id, p)
    messagebox.showinfo("Done", "Teams saved. You can set the result later.")
    reset_team_selection()

tk.Button(team_pick_frame, text="Save Teams", command=finalize_teams).pack(pady=20)

def reset_team_selection():
    team1.clear()
    team2.clear()
    update_team_labels()
    switch(add_player_frame)

def begin_team_selection(match_id):
    global current_match_id
    current_match_id = match_id
    refresh_players()
    switch(team_pick_frame)
#endregion

#region PAGE 4: SET MATCH RESULT
tk.Label(set_result_frame, text="Set Match Result", font=("Arial", 16)).pack(pady=10)

match_list = ttk.Treeview(set_result_frame, columns=("id", "date"), show="headings", height=10)
match_list.heading("id", text="ID")
match_list.heading("date", text="Date")
match_list.pack(pady=10)

team_list = ttk.Treeview(set_result_frame, columns=("id", "players"), show="headings", height=5)
team_list.heading("id", text="ID")
team_list.heading("players", text="Players")
team_list.pack(pady=10)

def refresh_matches():
    match_list.delete(*match_list.get_children())
    with sqlite3.connect(DB) as conn:
        for mid, mdate in conn.execute("SELECT id, date FROM matches ORDER BY date"):
            match_list.insert("", "end", values=(mid, mdate))

def refresh_teams(event=None):
    sel = match_list.focus()
    if not sel:
        return
    match_id = match_list.item(sel)["values"][0]
    team_list.delete(*team_list.get_children())
    with sqlite3.connect(DB) as conn:
        teams = conn.execute("SELECT id FROM teams WHERE match_id = ?", (match_id,)).fetchall()
        for tid, in teams:
            players = [name for (name,) in conn.execute(
                "SELECT p.name FROM players p JOIN team_players tp ON p.id = tp.player_id WHERE tp.team_id = ?", (tid,)
            )]
            team_list.insert("", "end", values=(tid, ", ".join(players)))

match_list.bind("<<TreeviewSelect>>", refresh_teams)

def select_winner():
    match_sel = match_list.focus()
    team_sel = team_list.focus()
    if not match_sel or not team_sel:
        messagebox.showwarning("Oops", "Select a match and a team")
        return
    match_id = match_list.item(match_sel)["values"][0]
    winning_team_id = team_list.item(team_sel)["values"][0]
    set_match_result(match_id, winning_team_id)
    messagebox.showinfo("Done", "Match result set and ELO updated.")
    refresh_teams()

tk.Button(set_result_frame, text="Set Selected Team as Winner", command=select_winner).pack(pady=10)
tk.Button(set_result_frame, text="Back", command=lambda: switch(add_player_frame)).pack(pady=5)
#endregion

#region PAGE 5: VIEW MATCHES
view_matches_frame = tk.Frame(root)
view_matches_frame.grid(row=0, column=0, sticky="nsew")
# add hidden columns for team IDs
matches_list = ttk.Treeview(
    view_matches_frame,
    columns=("id", "date", "team1_names", "team2_names", "result", "team1_id", "team2_id"),
    show="headings",
    height=15
)
# visible columns
matches_list.heading("id", text="Match ID")
matches_list.heading("date", text="Date")
matches_list.heading("team1_names", text="Team 1 Players")
matches_list.heading("team2_names", text="Team 2 Players")
matches_list.heading("result", text="Result")

# hidden columns for internal use
matches_list.column("team1_id", width=0, stretch=False)
matches_list.column("team2_id", width=0, stretch=False)
matches_list.pack(pady=10, fill="both", expand=True)

def open_edit_team_players_popup():
    selected = matches_list.selection()
    if not selected:
        messagebox.showerror("Error", "Select a match first.")
        return

    match_values = matches_list.item(selected[0])["values"]
    match_id = match_values[0]
    match_date = match_values[1]
    team1_names = match_values[2]
    team2_names = match_values[3]
    result = match_values[4]
    team1_id = match_values[5]
    team2_id = match_values[6]
    
   

    if result not in (None, "Pending"):
     messagebox.showerror("Error", "Cannot edit players after match result is set.")
     return

    
    # choose which team to edit
    win = tk.Toplevel(root)
    win.title("Select Team")
    win.geometry("250x120")

    ttk.Button(win, text=f"Edit Team {team1_names}", command=lambda: open_team_editor(team1_id, win)).pack(pady=10)
    ttk.Button(win, text=f"Edit Team {team2_names}", command=lambda: open_team_editor(team2_id, win)).pack(pady=10)

def open_team_editor(team_id, parent_win): 
    parent_win.destroy()

    win = tk.Toplevel(root)
    win.title(f"Edit Team {team_id}")
    win.geometry("500x400")

    # get data
    all_players = get_players()         
    current_players = get_team_players(team_id)
    current_ids = {p[0] for p in current_players}

    # UI lists
    left_list = tk.Listbox(win, selectmode=tk.MULTIPLE)
    right_list = tk.Listbox(win, selectmode=tk.MULTIPLE)

    for p in all_players:
        if p[0] not in current_ids:
            left_list.insert(tk.END, f"{p[0]} - {p[1]}")

    for p in current_players:
        right_list.insert(tk.END, f"{p[0]} - {p[1]}")

    left_list.pack(side="left", fill="both", expand=True, padx=10, pady=10)
    right_list.pack(side="right", fill="both", expand=True, padx=10, pady=10)

    # move buttons
    def add():
        for index in left_list.curselection()[::-1]:
            item = left_list.get(index)
            left_list.delete(index)
            right_list.insert(tk.END, item)

    def remove():
        for index in right_list.curselection()[::-1]:
            item = right_list.get(index)
            right_list.delete(index)
            left_list.insert(tk.END, item)

    ttk.Button(win, text=">>", command=add).place(relx=0.47, rely=0.3)
    ttk.Button(win, text="<<", command=remove).place(relx=0.47, rely=0.5)

    # save
    def save():
        new_ids = []
        for i in range(right_list.size()):
            pid = int(right_list.get(i).split(" - ")[0])
            new_ids.append(pid)

        set_team_players(team_id, new_ids)
        win.destroy()
        messagebox.showinfo("Saved", "Team players updated successfully.")

    ttk.Button(win, text="Save", command=save).pack(pady=10)

tk.Button(view_matches_frame, text="Back", command=lambda: switch(add_player_frame)).pack(pady=10)
edit_players_btn = ttk.Button(view_matches_frame, text="Edit Team Players", command=open_edit_team_players_popup)
edit_players_btn.pack(pady=5)

def refresh_view_matches():
    matches_list.delete(*matches_list.get_children())  # this is the Treeview in view_matches_frame
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, date FROM matches ORDER BY date")
        for match_id, match_date in cur.fetchall():
            # get teams
            cur.execute("SELECT id, is_winner FROM teams WHERE match_id = ?", (match_id,))
            teams = cur.fetchall()
            if len(teams) == 2:
                t1_id, t1_win = teams[0]
                t2_id, t2_win = teams[1]
                # get player names
                t1_players = [name for (name,) in conn.execute(
                    "SELECT p.name FROM players p JOIN team_players tp ON p.id = tp.player_id WHERE tp.team_id = ?", (t1_id,)
                )]
                t2_players = [name for (name,) in conn.execute(
                    "SELECT p.name FROM players p JOIN team_players tp ON p.id = tp.player_id WHERE tp.team_id = ?", (t2_id,)
                )]
                # determine result
                if t1_win is None:
                    result = "Pending"
                else:
                    result = "Team 1 Win" if t1_win else "Team 2 Win"
                matches_list.insert("", "end", values=(match_id, match_date, ", ".join(t1_players), ", ".join(t2_players), result,t1_id, t2_id))
            else:
                matches_list.insert("", "end", values=(match_id, match_date, "", "", "Pending",t1_id,t2_id))


#endregion

#region PAGE 6: PLAYER RANKINGS
player_rank_frame = tk.Frame(root)
player_rank_frame.grid(row=0, column=0, sticky="nsew")
tk.Label(player_rank_frame, text="Player Rankings", font=("Arial", 16)).pack(pady=10)

player_tree = ttk.Treeview(player_rank_frame, columns=("id", "name", "rating"), show="headings", height=20)
player_tree.heading("id", text="ID")
player_tree.heading("name", text="Name")
player_tree.heading("rating", text="Rating")
player_tree.pack(pady=10, fill="both", expand=True)

tk.Button(player_rank_frame, text="Back", command=lambda: switch(add_player_frame)).pack(pady=10)

def refresh_player_rankings():
    player_tree.delete(*player_tree.get_children())
    players = get_players()  # returns (id, name, rating)
    # sort descending by rating
    players.sort(key=lambda x: x[2], reverse=True)
    for pid, name, rating in players:
        player_tree.insert("", "end", values=(pid, name, round(rating)))
#endregion



#region START APP
switch(add_player_frame)
root.mainloop()
#endregion