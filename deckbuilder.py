import tkinter as tk



root = tk.Tk()
root.title("Deck Builder")
root.geometry("900x600")

state = {"player_hp": 50, "player_block": 0, "player_energy": 3, "enemy_hp": 30, "turn": 1, "enemy_damage": 7}

STRIKE_COST = 1
STRIKE_DAMAGE = 6
DEFEND_COST = 1
DEFEND_BLOCK = 5

def update_status():
    text = f"HP:{state['player_hp']} | Block:{state['player_block']} | Energy:{state['player_energy']} | Enemy HP: {state['enemy_hp']}"
    status.config(text=text)

### Helper Function (Do not need to repeat log inserting)
def log_line(message):
    log.insert("end", message + "\n")
    log.see("end")


### Turn Loop
def end_turn():
    log_line("Player ends turn.")
    enemy_attack()
    start_new_turn()
    update_status()

def enemy_attack():
    damage = state["enemy_damage"]
    block = state["player_block"]
    absorbed = min(block, damage)
    state["player_block"] -= absorbed
    leftover = damage - absorbed
    state["player_hp"] -= leftover

    log_line(f"Enemy attacks for {damage} damage! Block absorbs {absorbed}. Player takes {leftover} damage.")

def start_new_turn():
    state["turn"] += 1
    state["player_energy"] = 3
    state["player_block"] = 0
    log_line(f"--- Turn {state['turn']} ---")

def play_strike():
    if state["player_energy"] < STRIKE_COST:
        log_line("Not enough energy to play Strike!")
        return
    state["player_energy"] -= STRIKE_COST
    state["enemy_hp"] -= STRIKE_DAMAGE
    log_line(f"Player plays Strike for {STRIKE_DAMAGE} damage!")
    if state["enemy_hp"] <= 0:
        log_line("Enemy defeated!")
    update_status()

def play_defend():
    if state["player_energy"] < DEFEND_COST:
        log_line("Not enough energy to play Defend!")
        return
    state["player_block"] += DEFEND_BLOCK
    state["player_energy"] -= DEFEND_COST
    log_line(f"Player plays Defend and gains {DEFEND_BLOCK} block!")
    update_status()

### Status Bar
status = tk.Label(root, text="Loading...")
status.pack(fill="x")
update_status()

### Combat Log
log = tk.Text(root, height=20)
log.pack(fill="both", expand=True)

log.insert("end", "Game Started\n")

### Hand Area
hand_frame = tk.Frame(root)
hand_frame.pack(fill="x")

hand_label = tk.Label(hand_frame, text="Hand will go here")
hand_label.pack(pady=10)

###Strike Button
strike_button = tk.Button(hand_frame, text="Strike (1)", command=play_strike)
strike_button.pack(side="left", padx=10, pady=10)

###Defend Button
defend_button = tk.Button(hand_frame, text="Defend (1)", command=play_defend)
defend_button.pack(side="left", padx=10, pady=10)
### End Button
end_button = tk.Button(hand_frame, text="End Turn", command=end_turn)
end_button.pack(side="left",padx=10,pady=10)


root.mainloop()