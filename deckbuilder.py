import tkinter as tk



root = tk.Tk()
root.title("Deck Builder")
root.geometry("900x600")

status = tk.Label(root, text="HP:50 | Block:0 | Energy:0 | Enemy HP: 30")

status.pack(fill="x")

root.mainloop()