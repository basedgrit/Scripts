import tkinter as tk
import random


root = tk.Tk()
root.title("Deck Builder")
root.geometry("900x600")

state = {"player_hp": 50, "player_block": 0, "player_energy": 3, "enemy_hp": 30, "turn": 1, "enemy_damage": 7,"mode":"combat", "reward_open": False,
        "deck":["Strike","Strike","Strike","Strike","Strike","Defend","Defend","Defend","Defend","Defend"], "draw_pile":[], "hand":[], "discard_pile":[]}
STRIKE_COST = 1
STRIKE_DAMAGE = 6
DEFEND_COST = 1
DEFEND_BLOCK = 5
card_costs = {"Strike": STRIKE_COST, "Defend": DEFEND_COST, "Big Strike": 2, "Shield Up": 1, "Heal": 1, "Zap": 0, "Gamble": 0}
rewards = ["Big Strike", "Shield Up", "Heal", "Zap", "Gamble"]


def update_status():
    text = f"HP:{state['player_hp']} | Block:{state['player_block']} | Energy:{state['player_energy']} | Enemy HP: {state['enemy_hp']}"
    status.config(text=text)

### Helper Function (Do not need to repeat log inserting)
def log_line(message):
    log.insert("end", message + "\n")
    log.see("end")

def get_cost(card):
    if card == "Strike":
        return STRIKE_COST
    elif card == "Defend":
        return DEFEND_COST
    else:
        return 0

### Turn Loop
def end_turn():
    log_line("Player ends turn.")
    state["discard_pile"].extend(state["hand"])
    state["hand"].clear()
    enemy_attack()
    start_new_turn()
    draw_cards(5)
    render_hand()
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


def draw_cards(n):
    for _ in range(n):
        if not state["draw-pile"]:
            state["draw-pile"] = state["discard_pile"].copy()
            state["discard_pile"].clear()
            random.shuffle(state["draw-pile"])
            if not state["draw-pile"]:
                log_line("No cards left to draw!")
                return
        card = state["draw-pile"].pop()
        state["hand"].append(card)
        log_line(f"Player draws {card}.")

def render_hand():
    for widget in hand_frame.winfo_children():
        if widget not in [hand_label, strike_button, defend_button, end_button]:
            widget.destroy()
    for index, card in enumerate(state["hand"]):
        card_button = tk.Button(hand_frame, text=card + " (1)", command=lambda c=card, i=index: play_card(c, i))
        card_button.pack(side="left", padx=5, pady=5)
        if state["player_energy"] < get_cost(card):
            card_button.config(state="disabled")
    

def play_card(card, index):
    if state["player_energy"] < STRIKE_COST and card == "Strike":
        log_line("Not enough energy to play Strike!")
        return
    if state["player_energy"] < DEFEND_COST and card == "Defend":
        log_line("Not enough energy to play Defend!")
        return
    if card == "Strike":
        play_strike()
    elif card == "Defend":
        play_defend()
    else:
        log_line(f"Unknown card: {card}")
        return
    state["discard_pile"].append(state["hand"].pop(index)) ##TODO: FIX
    render_hand()

    if state["enemy_hp"] <= 0:
        log_line("Enemy defeated!")
        state["mode"] = "reward"
        show_rewards()

def setup_combat():
    state["draw_pile"], state["hand"] = [], []
    state["draw-pile"] = state["deck"].copy()

    random.shuffle(state["draw-pile"])

    state["enemy_hp"] = 30
    start_new_turn()
    draw_cards(5)
    render_hand()
    update_status()

def show_rewards():
    state["hand"].clear()
    log_line("Choose a reward card:")
    for reward in rewards:
        reward_button = tk.Button(hand_frame, text=reward, command=lambda r=reward: choose_reward(r))
        reward_button.pack(side="left", padx=5, pady=5)
    

def choose_reward(reward, popup):
    state["deck"].append(reward)
    log_line(f"Player chooses reward: {reward}")
    state["mode"] = "combat"
    popup.destroy()
    state["reward_open"] = False
    setup_combat()


def open_reward_popup():
    if state["reward_open"]:
        return
    else:
        state["reward_open"] = True
        popup = tk.Toplevel(root)
        popup.title("Choose Your Reward")
        popup.geometry("420x220")

        popup.transient(root)
        popup.grab_set()
        tk.Label(popup, text="Choose a reward card:").pack(pady=10)
        rewards_to_show = random.sample(rewards, 3)
        for reward in rewards_to_show:
            tk.Button(popup, text=reward, command=lambda r=reward: choose_reward(r,popup)).pack(side="left", padx=5, pady=5)

        popup.protocol("WM_DELETE_WINDOW", lambda: on_closing())
def on_closing():
    ##disable closing if reward popup is open
    if state["reward_open"]:
        log_line("Please choose a reward before closing.")
    else:
        root.destroy()
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


###Defend Button
defend_button = tk.Button(hand_frame, text="Defend (1)", command=play_defend)

### End Button
end_button = tk.Button(hand_frame, text="End Turn", command=end_turn)
end_button.pack(side="left",padx=10,pady=10)

setup_combat()
root.mainloop()