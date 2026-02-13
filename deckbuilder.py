import tkinter as tk



root = tk.Tk()
root.title("Deck Builder")
root.geometry("900x600")

### Function to end turn
def end_turn():
    log.insert("end", "Turn Ended\n")
    log.see("end")





### Status Bar
status = tk.Label(root, text="HP:50 | Block:0 | Energy:0 | Enemy HP: 30")
status.pack(fill="x")

### Combat Log
log = tk.Text(root, height=20)
log.pack(fill="both", expand=True)

log.insert("end", "Game Started\n")

### Hand Area
hand_frame = tk.Frame(root)
hand_frame.pack(fill="x")

hand_label = tk.Label(hand_frame, text="Hand will go here")
hand_label.pack(pady=10)

### End Button
end_button = tk.Button(hand_frame, text="End Turn", command=end_turn)
end_button.pack(side="left",padx=10,pady=10)


root.mainloop()