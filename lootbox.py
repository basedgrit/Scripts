"""
Loot Box GUI (Tkinter) — single-file mini app (FLAIR EDITION)
Adds:
- Goofy (non-tech) loot items
- Canvas "reveal card" with rarity-themed background
- Sparkle suspense text during opening
- Confetti burst on Legendary
- Weighted loot table + reveal animation + inventory/history + stats + pity system

Run: python lootbox_gui.py
"""

from __future__ import annotations

import random
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Dict, List, Tuple


# -----------------------------
# Data model
# -----------------------------

RARITIES: Tuple[str, ...] = ("Common", "Rare", "Epic", "Legendary")

RARITY_STYLE: Dict[str, Dict[str, str]] = {
    "Common": {"fg": "#333333"},
    "Rare": {"fg": "#0b5394"},
    "Epic": {"fg": "#741b47"},
    "Legendary": {"fg": "#b45f06"},
}


@dataclass(frozen=True)
class LootItem:
    name: str
    rarity: str
    weight: int  # higher = more common


# Goofy, NOT tech-related
DEFAULT_LOOT: List[LootItem] = [
    # Common
    LootItem("Pocket Pebble (Perfectly Round)", "Common", 35),
    LootItem("Squeaky Feather of Mild Authority", "Common", 34),
    LootItem("Soggy Crouton (Still Confident)", "Common", 32),
    LootItem("Tiny Hat for a Very Small Mood", "Common", 30),
    LootItem("Jar of Suspicious Sparkles", "Common", 28),
    LootItem("Left Shoe That Smells Like Victory", "Common", 26),
    LootItem("Mystery Button (Do Not Press)", "Common", 24),
    LootItem("One (1) Dramatic Eyebrow", "Common", 24),

    # Rare
    LootItem("Coupon for One Free Compliment", "Rare", 18),
    LootItem("Unreasonably Fancy Spoon", "Rare", 17),
    LootItem("Cloak of Mild Inconvenience", "Rare", 15),
    LootItem("The Last Good Strawberry", "Rare", 14),
    LootItem("Bottle of Captured Giggles", "Rare", 13),

    # Epic
    LootItem("Crown of Crumbs (Royalty Adjacent)", "Epic", 8),
    LootItem("Glove of Unmatched Confidence", "Epic", 7),
    LootItem("Map to Somewhere Vaguely Important", "Epic", 6),
    LootItem("Whistle That Summons Absolutely Nothing", "Epic", 6),
    LootItem("Cape That Billows on Command", "Epic", 5),

    # Legendary
    LootItem("Golden Goose Feather (Certified Majestic)", "Legendary", 1),
    LootItem("The One True Lucky Charm", "Legendary", 1),
    LootItem("Sword of Extremely Polite Duels", "Legendary", 1),
]


# -----------------------------
# App
# -----------------------------

class LootBoxApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("Loot Box — Tkinter (Flair Edition)")
        self.minsize(920, 560)

        # State
        self.loot_table: List[LootItem] = list(DEFAULT_LOOT)
        self.total_opens: int = 0
        self.rarity_counts: Dict[str, int] = {r: 0 for r in RARITIES}
        self.opens_since_legendary: int = 0

        self.animating: bool = False
        self._reveal_after_id: str | None = None

        # Animation settings
        self.reveal_duration_ms = 1400
        self.reveal_tick_ms = 60

        # Pity settings
        self.pity_enabled = tk.BooleanVar(value=True)
        self.pity_guarantee_at = tk.IntVar(value=30)

        # Card visuals
        self.card_bg = "#f4f4f4"
        self.card_border = "#d0d0d0"

        self._build_ui()

    # -------------------------
    # UI
    # -------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # Left: reveal + controls
        left = ttk.Frame(self, padding=14)
        left.grid(row=0, column=0, sticky="nsew")
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        header = ttk.Frame(left)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Loot Box", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Click Open Box for a dramatic reveal (and questionable treasures).",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Reveal canvas "card" (color + effects)
        self.card_canvas = tk.Canvas(left, highlightthickness=0)
        self.card_canvas.grid(row=1, column=0, sticky="nsew")
        self.card_canvas.bind("<Configure>", lambda e: self._draw_card())

        # Text items on canvas
        self.title_id = self.card_canvas.create_text(
            0, 0, text="Ready to open!", font=("Segoe UI", 20, "bold"), fill="#1f1f1f"
        )
        self.rarity_id = self.card_canvas.create_text(
            0, 0, text="", font=("Segoe UI", 14, "bold"), fill="#333333"
        )
        self.sub_id = self.card_canvas.create_text(
            0, 0, text="Click Open Box ↓", font=("Segoe UI", 11), fill="#666666"
        )

        # Suspense bar
        self.progress = ttk.Progressbar(left, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        # Footer controls
        footer = ttk.Frame(left)
        footer.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)

        self.open_btn = ttk.Button(footer, text="Open Box", command=self.open_box)
        self.open_btn.grid(row=0, column=0, sticky="ew")

        # Pity controls row
        pity_row = ttk.Frame(left)
        pity_row.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        pity_row.columnconfigure(3, weight=1)

        ttk.Checkbutton(
            pity_row,
            text="Pity enabled (guarantee Legendary at)",
            variable=self.pity_enabled,
            command=self._refresh_status,
        ).grid(row=0, column=0, sticky="w")

        self.pity_spin = ttk.Spinbox(
            pity_row,
            from_=5,
            to=999,
            textvariable=self.pity_guarantee_at,
            width=6,
            command=self._refresh_status,
        )
        self.pity_spin.grid(row=0, column=1, sticky="w", padx=(6, 6))
        ttk.Label(pity_row, text="opens without Legendary").grid(row=0, column=2, sticky="w")

        # Status line
        self.status = ttk.Label(left, text="", font=("Segoe UI", 10))
        self.status.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        self._refresh_status()

        # Right: inventory + stats
        right = ttk.Frame(self, padding=14)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Inventory / History", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        # Listbox + scrollbar
        list_frame = ttk.Frame(right)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.history = tk.Listbox(list_frame, height=12, activestyle="none")
        self.history.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.history.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.history.configure(yscrollcommand=sb.set)

        # Stats box
        stats = ttk.Frame(right, padding=10, relief="groove")
        stats.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        stats.columnconfigure(1, weight=1)

        ttk.Label(stats, text="Session Stats", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6)
        )

        self.stats_total = ttk.Label(stats, text="Total opens: 0")
        self.stats_total.grid(row=1, column=0, columnspan=2, sticky="w")

        self.stats_pity = ttk.Label(stats, text="Opens since Legendary: 0")
        self.stats_pity.grid(row=2, column=0, columnspan=2, sticky="w", pady=(2, 6))

        self.stats_rarity = {}
        row = 3
        for r in RARITIES:
            lbl = ttk.Label(stats, text=f"{r}: 0")
            lbl.grid(row=row, column=0, columnspan=2, sticky="w", pady=1)
            self.stats_rarity[r] = lbl
            row += 1

        ttk.Button(right, text="Clear Session", command=self.clear_session).grid(
            row=3, column=0, sticky="ew", pady=(12, 0)
        )

        self._draw_card()
        self._update_stats_labels()

    # -------------------------
    # Card drawing & effects
    # -------------------------

    def _draw_card(self) -> None:
        c = self.card_canvas
        c.delete("card_bg")

        w = c.winfo_width()
        h = c.winfo_height()
        if w < 20 or h < 20:
            return

        pad = 12
        x0, y0, x1, y1 = pad, pad, w - pad, h - pad

        # Shadow
        c.create_rectangle(x0 + 4, y0 + 4, x1 + 4, y1 + 4,
                           fill="#000000", outline="", stipple="gray25", tags="card_bg")
        # Card
        c.create_rectangle(x0, y0, x1, y1,
                           fill=self.card_bg, outline=self.card_border, width=2, tags="card_bg")
        c.tag_lower("card_bg")
        # Subtle top highlight band
        c.create_rectangle(x0, y0, x1, y0 + (y1 - y0) * 0.18,
                           fill="#ffffff", outline="", stipple="gray50", tags="card_bg")

        # Place text centered
        cx = w // 2
        c.coords(self.title_id, cx, int(h * 0.40))
        c.coords(self.rarity_id, cx, int(h * 0.54))
        c.coords(self.sub_id, cx, int(h * 0.70))

    def _set_card_theme_for_rarity(self, rarity: str) -> None:
        themes = {
            "Common": ("#f4f4f4", "#d0d0d0"),
            "Rare": ("#e8f2ff", "#7aa7df"),
            "Epic": ("#f3e9ff", "#b17adf"),
            "Legendary": ("#fff2d6", "#e3a23b"),
        }
        self.card_bg, self.card_border = themes.get(rarity, ("#f4f4f4", "#d0d0d0"))
        self._draw_card()

    def _confetti(self) -> None:
        c = self.card_canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 80 or h < 80:
            return

        colors = ["#ff4d4d", "#ffd24d", "#4dff88", "#4dd2ff", "#b84dff", "#ff7ae6"]
        pieces = []
        for _ in range(70):
            x = random.randint(20, w - 20)
            y = random.randint(20, h - 20)
            size = random.randint(4, 10)
            dx = random.randint(-7, 7)
            dy = random.randint(3, 11)
            item = c.create_rectangle(
                x, y, x + size, y + size,
                fill=random.choice(colors), outline="",
                tags="fx"
            )
            pieces.append((item, dx, dy))

        steps = 20

        def animate(step: int = 0) -> None:
            for item, dx, dy in pieces:
                c.move(item, dx, dy + step // 3)
            if step < steps:
                self.after(35, animate, step + 1)
            else:
                c.delete("fx")

        animate()

    def _sparkle_text(self, base: str, ticks: int = 18) -> None:
        c = self.card_canvas
        dots = ["", ".", "..", "..."]
        sparkle = [" ✨", " 💥", " 🪄", " 🌟", " 🎉", " 🍀"]

        def loop(i: int = 0) -> None:
            if not self.animating:
                return
            text = f"{base}{dots[i % 4]}{random.choice(sparkle)}"
            c.itemconfigure(self.sub_id, text=text)
            if i < ticks:
                self.after(90, loop, i + 1)

        loop(0)

    def _rarity_drop_rate(self, rarity: str) -> float:
        weights = [i.weight for i in self.loot_table if i.weight > 0]
        total = sum(weights) if weights else 1
        r_total = sum(i.weight for i in self.loot_table if i.rarity == rarity and i.weight > 0)
        return (r_total / total) * 100.0

    # -------------------------
    # Mechanics
    # -------------------------

    def roll_item(self) -> LootItem:
        """Roll an item using weights, respecting pity if enabled."""
        if self.pity_enabled.get():
            threshold = max(1, int(self.pity_guarantee_at.get()))
            if self.opens_since_legendary >= threshold:
                legendaries = [i for i in self.loot_table if i.rarity == "Legendary"]
                return random.choice(legendaries)

        items = self.loot_table
        weights = [max(0, i.weight) for i in items]
        if sum(weights) == 0:
            return random.choice(items)
        return random.choices(items, weights=weights, k=1)[0]

    def open_box(self) -> None:
        if self.animating:
            return

        self.animating = True
        self.open_btn.state(["disabled"])
        self.progress.start(12)

        self._sparkle_text("Opening")

        final_item = self.roll_item()
        self._run_reveal_animation(final_item)

    def _run_reveal_animation(self, final_item: LootItem) -> None:
        ticks = max(1, self.reveal_duration_ms // self.reveal_tick_ms)

        flash_items = [random.choice(self.loot_table) for _ in range(ticks - 1)] + [final_item]

        def tick(idx: int) -> None:
            item = flash_items[idx]
            self._set_reveal(item, flashing=(idx != len(flash_items) - 1))

            if idx < len(flash_items) - 1:
                self._reveal_after_id = self.after(self.reveal_tick_ms, tick, idx + 1)
            else:
                self.after(120, self._finish_open, final_item)

        tick(0)

    def _finish_open(self, item: LootItem) -> None:
        self.progress.stop()
        self.animating = False
        self.open_btn.state(["!disabled"])
        self._reveal_after_id = None

        self.total_opens += 1
        self.rarity_counts[item.rarity] += 1

        if item.rarity == "Legendary":
            self.opens_since_legendary = 0
        else:
            self.opens_since_legendary += 1

        self.history.insert(0, f"{item.rarity}: {item.name}")
        self.history.selection_clear(0, tk.END)
        self.history.selection_set(0)
        self.history.activate(0)

        if item.rarity == "Legendary":
            self._confetti()

        self._update_stats_labels()
        self._refresh_status()

    def _set_reveal(self, item: LootItem, flashing: bool = False) -> None:
        c = self.card_canvas

        self._set_card_theme_for_rarity(item.rarity)

        if flashing:
            # show a random name while flashing (keeps it chaotic)
            name = random.choice(self.loot_table).name
            c.itemconfigure(self.title_id, text=name)
            c.itemconfigure(self.rarity_id, text=f"{item.rarity} …", fill=RARITY_STYLE.get(item.rarity, {}).get("fg", "#333333"))
            c.itemconfigure(self.sub_id, text=random.choice([
                "Rattling the box... (ominous)",
                "Shaking vigorously... for science",
                "Whispering to the loot spirits...",
                "Negotiating with fate...",
                "Please be shiny. Please be shiny.",
            ]))
        else:
            c.itemconfigure(self.title_id, text=item.name)
            c.itemconfigure(self.rarity_id, text=item.rarity, fill=RARITY_STYLE.get(item.rarity, {}).get("fg", "#333333"))

            rate = self._rarity_drop_rate(item.rarity)
            if item.rarity == "Legendary":
                c.itemconfigure(self.sub_id, text=f"ABSURD LUCK ACTIVATED • Legendary rarity ~{rate:.1f}%")
            else:
                c.itemconfigure(self.sub_id, text=f"Drop rate (rarity): ~{rate:.1f}%")

    # -------------------------
    # Session controls
    # -------------------------

    def clear_session(self) -> None:
        if self.animating:
            return

        self.total_opens = 0
        self.opens_since_legendary = 0
        self.rarity_counts = {r: 0 for r in RARITIES}
        self.history.delete(0, tk.END)

        self._set_card_theme_for_rarity("Common")
        self.card_canvas.itemconfigure(self.title_id, text="Ready to open!")
        self.card_canvas.itemconfigure(self.rarity_id, text="", fill="#333333")
        self.card_canvas.itemconfigure(self.sub_id, text="Click Open Box ↓")

        self._update_stats_labels()
        self._refresh_status()

    def _update_stats_labels(self) -> None:
        self.stats_total.configure(text=f"Total opens: {self.total_opens}")
        self.stats_pity.configure(text=f"Opens since Legendary: {self.opens_since_legendary}")
        for r in RARITIES:
            self.stats_rarity[r].configure(text=f"{r}: {self.rarity_counts.get(r, 0)}")

    def _refresh_status(self) -> None:
        if self.pity_enabled.get():
            threshold = max(1, int(self.pity_guarantee_at.get()))
            remaining = max(0, threshold - self.opens_since_legendary)
            self.status.configure(
                text=f"Pity: ON • Legendary guaranteed in {remaining} open(s) if no Legendary drops."
            )
        else:
            self.status.configure(text="Pity: OFF • Pure weighted randomness.")


if __name__ == "__main__":
    app = LootBoxApp()
    app.mainloop()
