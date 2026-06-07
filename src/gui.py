"""One-window Tkinter UI for Wicked Respec (reset-only)."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from src.saves import find_saves, default_root
from src.engine import preview_respec, apply_respec
from src.respec import ATTRS

WARNING = ("Close No Rest For The Wicked COMPLETELY before respeccing - the game "
           "autosaves and will overwrite changes. On online realms the server may "
           "overwrite or flag edits. A verified backup is made before any change.")

class App(tk.Tk):
    def __init__(self, dict_bytes):
        super().__init__()
        self.dict_bytes = dict_bytes
        self.title("Wicked Respec - No Rest For The Wicked")
        self.geometry("560x580")
        self.saves = find_saves(default_root())
        self.save_var = tk.StringVar(value=self.saves[0] if self.saves else "")
        self.plan = None
        self._build()
        if self.saves:
            self.refresh()
        else:
            self.status.config(text="No saves auto-detected. Click Browse... to choose your .cerimal file.")

    def _build(self):
        ttk.Label(self, text=WARNING, wraplength=520, foreground="#a40000",
                  justify="left").pack(padx=12, pady=8, anchor="w")
        self.char_lbl = ttk.Label(self, text="Character: -",
                                   font=("Segoe UI", 12, "bold"))
        self.char_lbl.pack(padx=12, pady=(2, 4), anchor="w")
        row = ttk.Frame(self); row.pack(fill="x", padx=12)
        ttk.Label(row, text="Save:").pack(side="left")
        self.cmb = ttk.Combobox(row, values=self.saves, textvariable=self.save_var,
                                state="readonly", width=54)
        self.cmb.pack(side="left", fill="x", expand=True)
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(row, text="Browse...", command=self.browse).pack(side="left", padx=(6, 0))
        self.tree = ttk.Treeview(self, columns=("now", "after"), show="tree headings", height=10)
        self.tree.heading("#0", text="Attribute"); self.tree.heading("now", text="Now")
        self.tree.heading("after", text="After")
        self.tree.column("#0", width=190); self.tree.column("now", width=80, anchor="e")
        self.tree.column("after", width=80, anchor="e")
        self.tree.pack(fill="both", expand=True, padx=12, pady=8)
        self.refund = ttk.Label(self, text=""); self.refund.pack(anchor="w", padx=12)
        self.btn = ttk.Button(self, text="Create backup & Respec", command=self.do_respec)
        self.btn.pack(pady=10)
        self.status = ttk.Label(self, text="", wraplength=520); self.status.pack(anchor="w", padx=12)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        path = self.save_var.get()
        if not path:
            return
        try:
            with open(path, "rb") as f:
                plan, values, name = preview_respec(f.read(), self.dict_bytes)
        except Exception as e:
            self.char_lbl.config(text="Character: -")
            self.status.config(text=f"Could not read save: {e}"); return
        self.plan = plan
        self.char_lbl.config(text=f"Character: {name or 'Unknown'}")
        for a in ATTRS:
            if a in values:
                after = 10 if a in plan.attributes_reset else values[a]
                self.tree.insert("", "end", text=a, values=(values[a], after))
        self.refund.config(text=f"Points refunded: {plan.refunded}   "
                                "(the game returns these to your available pool on next load)")
        self.status.config(text="Ready. Nothing is written until you click the button.")

    def browse(self):
        path = filedialog.askopenfilename(
            title="Select a .cerimal save",
            initialdir=default_root(),
            filetypes=[("Wicked save", "*.cerimal"), ("All files", "*.*")])
        if not path:
            return
        vals = list(self.cmb["values"])
        if path not in vals:
            vals.append(path)
            self.cmb["values"] = vals
        self.save_var.set(path)
        self.refresh()

    def do_respec(self):
        path = self.save_var.get()
        if not path or self.plan is None:
            return
        if not self.plan.writes:
            messagebox.showinfo("Nothing to do", "All attributes are already at 10.")
            return
        if not messagebox.askyesno("Confirm respec",
                f"Reset {', '.join(self.plan.attributes_reset)} to 10 "
                f"(refunding {self.plan.refunded} points)?\n\n"
                "A verified backup is made first. Make sure the game is closed."):
            return
        try:
            plan = apply_respec(path, self.dict_bytes)
        except Exception as e:
            messagebox.showerror("Failed", str(e)); return
        messagebox.showinfo("Done",
            f"Respec complete. {plan.refunded} points refunded.\n"
            f"Backup: {plan.backup_path}\n\n"
            "Load the game to confirm your attributes are 10 and the points are available "
            "(try offline first).")
        self.refresh()

def run(dict_bytes):
    App(dict_bytes).mainloop()
